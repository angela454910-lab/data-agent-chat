"""Business-boundary tests; use a temporary DB and never call a real model."""
import asyncio
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

spec = importlib.util.spec_from_file_location("sop_under_test", Path(__file__).parents[1] / "app" / "sop.py")
sop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sop)


class ListingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = sop.ListingStore(Path(self.tmp.name) / "business.db")
        self.scope = ("listing-demo", "local-demo-user")
        self.store.setup_demo()

    def tearDown(self):
        self.tmp.cleanup()

    def preview(self, task="task-1"):
        return self.store.preview(self.scope, task, {"items": [{"sku": "DEMO-WINE-001", "channel": "经销商", "region": "华东", "status": "unlisted"}]})

    def test_execution_is_idempotent_and_read_back_is_real(self):
        plan = self.preview()
        with self.assertRaises(HTTPException):
            self.store.verify(self.scope, "task-1", plan["planId"])
        first = self.store.execute(self.scope, "task-1", plan["planId"])
        self.assertEqual(first, self.store.execute(self.scope, "task-1", plan["planId"]))
        product = self.store.query({"sku": "DEMO-WINE-001", "region": "华东"})["products"][0]
        self.assertEqual(product["version"], 2)
        self.assertTrue(self.store.verify(self.scope, "task-1", plan["planId"])["verified"])

    def test_readback_mismatch_cannot_be_reported_as_success(self):
        plan = self.preview()
        self.store.execute(self.scope, "task-1", plan["planId"])
        with self.store.db() as db:
            db.execute("UPDATE products SET status='listed' WHERE sku='DEMO-WINE-001' AND region='华东'")
        with self.assertRaises(HTTPException) as error:
            self.store.verify(self.scope, "task-1", plan["planId"])
        self.assertEqual(error.exception.status_code, 409)

    def test_stale_plan_does_not_overwrite_new_state(self):
        first, stale = self.preview(), self.preview("task-2")
        self.store.execute(self.scope, "task-1", first["planId"])
        with self.assertRaises(HTTPException) as error:
            self.store.execute(self.scope, "task-2", stale["planId"])
        self.assertEqual(error.exception.status_code, 409)

    def test_files_and_plans_are_scoped(self):
        file = self.store.save_attachment(self.scope, "demo.csv", [{"sku": "001"}])
        with self.assertRaises(HTTPException):
            self.store.attachment(("another", "actor"), file["id"])
        plan = self.preview()
        with self.assertRaises(HTTPException):
            self.store.execute(self.scope, "other-task", plan["planId"])

    def test_csv_preserves_codes_and_source_rows(self):
        rows = sop._parse_file("file.csv", "商品编码,操作\n00123,下架\n".encode())
        self.assertEqual(rows, [{"商品编码": "00123", "操作": "下架", "_row": 2}])
        with self.assertRaises(HTTPException):
            sop._parse_file("bad.csv", b"sku,sku\n1,2\n")

    def test_xlsx_preserves_source_rows(self):
        from openpyxl import Workbook
        workbook = Workbook()
        workbook.active.append(["sku", "action"])
        workbook.active.append(["001", "unlist"])
        buffer = io.BytesIO()
        workbook.save(buffer)
        self.assertEqual(sop._parse_file("file.xlsx", buffer.getvalue())[0]["sku"], "001")

    def test_approval_must_bind_preview_and_frozen_revision(self):
        plan = self.preview()
        task = {"status": "executing", "approvedAt": "now", "approvedRevision": 4,
                "revision": 8, "planHash": "frozen", "plan": {"agents": [{"id": "analysis", "phase": "analysis"}]},
                "runs": [{"agentId": "analysis", "status": "succeeded", "toolCalls": [
                    {"name": "preview_listing_changes", "status": "succeeded", "result": plan}]}]}
        body = sop.ToolInput(taskId="task-1", callId="call-1", arguments={"planId": plan["planId"]},
                             approval={"taskId": "task-1", "revision": 4, "planHash": "frozen"})
        with patch.object(sop, "_service", AsyncMock(return_value=task)), patch.object(sop, "_store", return_value=self.store):
            asyncio.run(sop._authorize_execution(body, self.scope, plan["planId"]))
            body.approval["revision"] = 8
            with self.assertRaises(HTTPException):
                asyncio.run(sop._authorize_execution(body, self.scope, plan["planId"]))
            body.approval["revision"] = 4
            task["runs"] = []
            with self.assertRaises(HTTPException):
                asyncio.run(sop._authorize_execution(body, self.scope, plan["planId"]))


class GatewayTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(sop.router)
        app.include_router(sop.gateway)
        self.client = TestClient(app)

    def test_gateway_is_closed_without_token_or_with_wrong_scope(self):
        with patch.dict(os.environ, {"SOP_AGENT_GATEWAY_TOKEN": "secret"}):
            self.assertEqual(self.client.get("/internal/sop/capabilities").status_code, 401)
            self.assertEqual(self.client.get("/internal/sop/capabilities", headers={"Authorization": "Bearer secret"}).status_code, 403)
            response = self.client.get("/internal/sop/capabilities", headers={"Authorization": "Bearer secret", "X-Project-ID": sop._scope()[0], "X-Actor-ID": sop._scope()[1]})
            self.assertEqual(response.status_code, 200)

    def test_cross_site_browser_cannot_trigger_model_or_mutation(self):
        with patch.object(sop, "_service", AsyncMock()) as service:
            response = self.client.post("/api/sop/tasks", json={"request": "hello"},
                                        headers={"Origin": "https://untrusted.example"})
            self.assertEqual(response.status_code, 403)
            service.assert_not_called()

    def test_browser_cannot_inject_internal_scope(self):
        with patch.object(sop, "_service", AsyncMock(return_value={"id": "new-task"})) as request:
            response = self.client.post("/api/sop/tasks", json={"request": "hello", "projectId": "other", "actorId": "admin"})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("projectId", request.call_args.args[2])
            self.assertNotIn("actorId", request.call_args.args[2])


if __name__ == "__main__":
    unittest.main()
