"""SSE proxy boundary tests with a controlled upstream, no model credentials."""
import asyncio
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

spec = importlib.util.spec_from_file_location("sop_stream_under_test", Path(__file__).parents[1] / "app" / "sop.py")
sop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sop)
RealAsyncClient = httpx.AsyncClient


class Chunks(httpx.AsyncByteStream):
    def __init__(self, parts, fail=False):
        self.parts = parts
        self.fail = fail
        self.closed = False

    async def __aiter__(self):
        for part in self.parts:
            yield part
        if self.fail:
            raise httpx.ReadError("fixture disconnected")

    async def aclose(self):
        self.closed = True


class StreamingProxyTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(sop.router)
        self.client = TestClient(app)
        self.frames = [b': heartbeat\n\n',
                       b'id: 1\nevent: task.snapshot\ndata: {"id":"task-one","status":"planning","revision":1}\n\n',
                       b'id: 2\nevent: task.waiting_confirmation\ndata: {"id":"task-one","status":"awaiting_confirmation","revision":2}\n\n']

    def upstream(self, handler):
        return patch.object(sop.httpx, "AsyncClient", side_effect=lambda **kwargs: RealAsyncClient(
            transport=httpx.MockTransport(handler), timeout=kwargs.get("timeout"), trust_env=False))

    def headers(self):
        return patch.object(sop, "_service_headers", return_value={"Authorization": "Bearer fixture",
                           "X-Project-ID": "project-one", "X-Actor-ID": "actor-one"})

    def test_stream_accept_negotiation(self):
        for accept, expected in (("application/json", False),
                                 ("text/event-stream; q=0", False),
                                 ("text/event-stream; q=bad", False),
                                 ("application/json, text/event-stream; q=0.8", True)):
            with self.subTest(accept=accept):
                request = Request({"type": "http", "headers": [(b"accept", accept.encode())]})
                self.assertEqual(sop._wants_stream(request), expected)

    def test_post_stream_forwards_scope_and_converts_attachment_reference(self):
        stream = Chunks(self.frames)
        requests = []

        async def handler(request):
            requests.append(request)
            return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, stream=stream)

        class Attachments:
            def attachment(self, scope, file_id):
                return {"id": file_id, "name": "input.csv"}

        with self.headers(), self.upstream(handler), patch.object(sop, "_store", return_value=Attachments()):
            response = self.client.post("/api/sop/tasks", json={"request": "inspect", "attachmentId": "file-one"},
                                        headers={"Accept": "text/event-stream"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b''.join(self.frames))
        self.assertEqual(response.headers["x-accel-buffering"], "no")
        self.assertIn("no-transform", response.headers["cache-control"])
        self.assertTrue(stream.closed)
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(request.headers["authorization"], "Bearer fixture")
        self.assertEqual(request.headers["x-actor-id"], "actor-one")
        self.assertEqual(request.headers["accept"], "text/event-stream")
        self.assertEqual(request.url.path, "/v1/personal-agent/tasks")
        self.assertEqual(json.loads(request.content)["context"]["attachmentId"], "file-one")

    def test_resume_uses_get_events_and_preserves_frames(self):
        stream = Chunks(self.frames)
        requests = []

        async def handler(request):
            requests.append(request)
            return httpx.Response(200, headers={"Content-Type": "text/event-stream; charset=utf-8"}, stream=stream)

        with self.headers(), self.upstream(handler):
            response = self.client.get("/api/sop/tasks/task-one/events")
        self.assertEqual(response.content, b''.join(self.frames))
        self.assertEqual(requests[0].method, "GET")
        self.assertEqual(requests[0].url.path, "/v1/personal-agent/tasks/task-one/events")
        self.assertTrue(stream.closed)

    def test_confirm_and_feedback_stream_without_changing_payload(self):
        for action, payload in (("confirm", {"revision": 2, "planHash": "approved-hash"}),
                                ("feedback", {"revision": 2, "message": "new scope"})):
            requests = []

            async def handler(request):
                requests.append(request)
                return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, stream=Chunks(self.frames))

            with self.headers(), self.upstream(handler):
                response = self.client.post(f"/api/sop/tasks/task-one/{action}", json=payload,
                                            headers={"Accept": "text/event-stream"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json.loads(requests[0].content), payload)
            self.assertTrue(requests[0].url.path.endswith("/" + action))

    def test_conflict_is_json_before_stream_headers(self):
        async def handler(request):
            return httpx.Response(409, json={"error": "stale revision"})

        with self.headers(), self.upstream(handler):
            response = self.client.post("/api/sop/tasks/task-one/confirm", json={"revision": 1, "planHash": "old"},
                                        headers={"Accept": "text/event-stream"})
        self.assertEqual(response.status_code, 409)
        self.assertIn("application/json", response.headers["content-type"])
        self.assertEqual(response.json()["detail"], "stale revision")

    def test_wrong_upstream_content_type_is_not_relayed_as_sse(self):
        async def handler(request):
            return httpx.Response(202, json={"id": "task-one"})

        with self.headers(), self.upstream(handler):
            response = self.client.get("/api/sop/tasks/task-one/events")
        self.assertEqual(response.status_code, 502)

    def test_disconnect_closes_upstream_and_does_not_reissue_post(self):
        stream = Chunks(self.frames[:2], fail=True)
        requests = []

        async def handler(request):
            requests.append(request)
            return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, stream=stream)

        with self.headers(), self.upstream(handler):
            response = self.client.post("/api/sop/tasks", json={"request": "inspect"}, headers={"Accept": "text/event-stream"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b''.join(self.frames[:2]))
        self.assertEqual(len(requests), 1)
        self.assertTrue(stream.closed)

    def test_abandoning_response_iterator_releases_subscription(self):
        stream = Chunks(self.frames)

        async def handler(request):
            return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, stream=stream)

        async def consume_first():
            response = await sop._stream_service("GET", "/tasks/task-one/events")
            await anext(response.body_iterator)
            await response.body_iterator.aclose()

        with self.headers(), self.upstream(handler):
            asyncio.run(consume_first())
        self.assertTrue(stream.closed)


if __name__ == "__main__":
    unittest.main()
