const { test } = require("node:test");
const assert = require("node:assert/strict");
const { join } = require("node:path");
const { createSseParser } = require(join(process.env.SOP_STREAM_TEST_BUILD, "sop-sse.js"));
const { sopApi, SopApiError } = require(join(process.env.SOP_STREAM_TEST_BUILD, "sop-api.js"));
const { SopTaskStreamController } = require(join(process.env.SOP_STREAM_TEST_BUILD, "sop-task-stream.js"));

function makeTask(id = "task-one", revision = 1, status = "analyzing") {
  return { id, revision, status, request: "核对新清单中的商品", planHash: "hash", createdAt: "2026-11-19T00:00:00Z", updatedAt: "2026-11-19T00:00:00Z" };
}

function frame(event, task) {
  return `id: ${task.revision}\nevent: ${event}\ndata: ${JSON.stringify(task)}\n\n`;
}

function fixture(t) {
  const operations = [];
  const updates = [];
  const selections = [];
  const settled = [];
  const issues = [];
  let uncertain = 0;
  const operation = (kind, id, listener, signal) => new Promise((resolve, reject) => {
    const entry = { kind, id, signal, emit: (event, task) => listener({ event, task }), finish: resolve, fail: reject };
    operations.push(entry);
    signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true });
  });
  const transport = {
    events: (id, listener, signal) => operation("events", id, listener, signal),
    create: (_body, listener, signal) => operation("create", null, listener, signal),
    confirm: (task, listener, signal) => operation("confirm", task.id, listener, signal),
    feedback: (task, _message, listener, signal) => operation("feedback", task.id, listener, signal),
  };
  const controller = new SopTaskStreamController({
    onSelection: (id, task) => selections.push({ id, task }),
    onTask: (task) => updates.push(task),
    onLoading: () => {},
    onIssue: (message, reconnecting) => issues.push({ message, reconnecting }),
    onSettled: (task) => settled.push(task),
    onUncertain: () => { uncertain += 1; },
  }, transport, [1, 2]);
  t.after(() => controller.disconnect());
  return { controller, operations, updates, selections, settled, issues, get uncertain() { return uncertain; } };
}

async function until(predicate) {
  const deadline = Date.now() + 500;
  while (!predicate()) {
    if (Date.now() > deadline) assert.fail("condition not reached");
    await new Promise(resolve => setTimeout(resolve, 2));
  }
}

test("SSE framing handles arbitrary CRLF boundaries, comments, BOM and multiline data", () => {
  const events = [];
  const parser = createSseParser(event => events.push(event));
  const input = "\uFEFF: heartbeat\r\nid: 7\r\nevent: task.snapshot\r\ndata: first\r\ndata: second\r\n\r\n: ignored\n\ndata: plain\n\n";
  for (const character of input) parser.push(character);
  parser.finish();
  assert.deepEqual(events, [
    { event: "task.snapshot", id: "7", data: "first\nsecond" },
    { event: "message", id: "7", data: "plain" },
  ]);
});

test("SSE framing supports lone CR and discards incomplete final frame", () => {
  const events = [];
  const parser = createSseParser(event => events.push(event));
  parser.push("id: 9\revent: task.updated\rdata: complete\r\rdata: incomplete");
  parser.finish();
  assert.deepEqual(events, [{ event: "task.updated", id: "9", data: "complete" }]);
});

test("stream transport decodes split UTF-8, requests SSE, and cancels at final marker", async (t) => {
  const originalFetch = global.fetch;
  t.after(() => { global.fetch = originalFetch; });
  let cancelled = false;
  let init;
  global.fetch = async (_url, options) => {
    init = options;
    const bytes = new TextEncoder().encode(frame("task.snapshot", makeTask()) + frame("task.waiting_confirmation", makeTask("task-one", 2, "awaiting_confirmation")));
    return new Response(new ReadableStream({
      start(controller) { for (const byte of bytes) controller.enqueue(new Uint8Array([byte])); },
      cancel() { cancelled = true; },
    }), { headers: { "Content-Type": "text/event-stream; charset=utf-8" } });
  };
  const events = [];
  await sopApi.events("task-one", event => events.push(event), new AbortController().signal);
  assert.equal(init.method, "GET");
  assert.equal(init.headers.Accept, "text/event-stream");
  assert.equal(events[0].task.request, "核对新清单中的商品");
  assert.equal(events[1].event, "task.waiting_confirmation");
  assert.equal(cancelled, true);
});

test("stream mutations preserve JSON validation errors", async (t) => {
  const originalFetch = global.fetch;
  t.after(() => { global.fetch = originalFetch; });
  let init;
  global.fetch = async (_url, options) => {
    init = options;
    return new Response(JSON.stringify({ error: "方案已更新，请重新核对" }), { status: 409, headers: { "Content-Type": "application/json" } });
  };
  await assert.rejects(sopApi.confirm(makeTask(), () => assert.fail("no event expected"), new AbortController().signal), error => error instanceof SopApiError && error.status === 409 && error.message === "方案已更新，请重新核对");
  assert.equal(init.method, "POST");
  assert.equal(init.headers.Accept, "text/event-stream");
  assert.deepEqual(JSON.parse(init.body), { revision: 1, planHash: "hash" });
});

test("creation keeps its POST stream and does not subscribe again after the first snapshot", async (t) => {
  const f = fixture(t);
  const first = f.controller.create({ request: "new task" });
  f.operations[0].emit("task.snapshot", makeTask());
  assert.equal((await first).id, "task-one");
  assert.deepEqual(f.operations.map(item => item.kind), ["create"]);
  f.operations[0].emit("task.updated", makeTask("task-one", 2));
  f.operations[0].emit("task.waiting_confirmation", makeTask("task-one", 3, "awaiting_confirmation"));
  assert.deepEqual(f.updates.map(item => item.revision), [1, 2, 3]);
  assert.equal(f.operations[0].signal.aborted, true);
  assert.equal(f.settled.length, 1);
});

test("old revisions, other task IDs, and callbacks from a replaced stream are ignored", async (t) => {
  const f = fixture(t);
  f.controller.select("task-one");
  const old = f.operations[0];
  old.emit("task.snapshot", makeTask("task-one", 3));
  old.emit("task.updated", makeTask("task-one", 2));
  old.emit("task.updated", makeTask("unrelated", 50));
  f.controller.select("task-two");
  const next = f.operations[1];
  old.emit("task.succeeded", makeTask("task-one", 9, "succeeded"));
  next.emit("task.snapshot", makeTask("task-two", 1));
  assert.deepEqual(f.updates.map(item => [item.id, item.revision]), [["task-one", 3], ["task-two", 1]]);
  assert.equal(f.settled.length, 0);
  assert.equal(old.signal.aborted, true);
});

test("known-task disconnect reconnects only to GET events and never repeats a mutation", async (t) => {
  const f = fixture(t);
  const outcome = f.controller.confirm(makeTask("task-one", 3, "awaiting_confirmation")).then(() => null, error => error);
  f.operations[0].fail(new TypeError("connection lost"));
  assert.match((await outcome).message, /不会自动重复提交/);
  await until(() => f.operations.length === 2);
  assert.deepEqual(f.operations.map(item => item.kind), ["confirm", "events"]);
  f.operations[1].emit("task.snapshot", makeTask("task-one", 4, "executing"));
  f.operations[1].emit("task.succeeded", makeTask("task-one", 5, "succeeded"));
  assert.equal(f.settled.length, 1);
});

test("lost creation response reports uncertainty and refreshes lists without retrying POST", async (t) => {
  const f = fixture(t);
  const outcome = f.controller.create({ request: "new task" }).then(() => null, error => error);
  f.operations[0].fail(new TypeError("connection lost"));
  assert.match((await outcome).message, /提交结果不确定/);
  await new Promise(resolve => setTimeout(resolve, 8));
  assert.equal(f.operations.length, 1);
  assert.equal(f.uncertain, 1);
});

test("navigating away cancels the subscription without settling/cancelling the task", async (t) => {
  const f = fixture(t);
  const outcome = f.controller.create({ request: "new task" }).then(() => null, error => error);
  f.controller.select(null);
  assert.equal((await outcome).name, "AbortError");
  assert.equal(f.operations[0].signal.aborted, true);
  assert.equal(f.settled.length, 0);
  assert.deepEqual(f.operations.map(item => item.kind), ["create"]);
});

test("a duplicate final revision refreshes lists once, including when re-opened", async (t) => {
  const f = fixture(t);
  const completed = makeTask("task-one", 4, "succeeded");
  f.controller.select(completed.id);
  f.operations[0].emit("task.snapshot", completed);
  f.operations[0].emit("task.succeeded", completed);
  f.operations[0].emit("task.succeeded", completed);
  f.controller.select(completed.id);
  f.operations[1].emit("task.snapshot", completed);
  f.operations[1].emit("task.succeeded", completed);
  assert.equal(f.settled.length, 1);
});

test("a lost POST stream after its snapshot resumes by GET and rejects late callbacks from that request", async (t) => {
  const f = fixture(t);
  const first = f.controller.create({ request: "new task" });
  const post = f.operations[0];
  post.emit("task.snapshot", makeTask("task-one", 2));
  await first;
  post.fail(new TypeError("connection lost"));
  await until(() => f.operations.length === 2);
  post.emit("task.updated", makeTask("task-one", 99));
  f.operations[1].emit("task.snapshot", makeTask("task-one", 3));
  f.operations[1].emit("task.waiting_confirmation", makeTask("task-one", 4, "awaiting_confirmation"));
  assert.deepEqual(f.operations.map(item => item.kind), ["create", "events"]);
  assert.deepEqual(f.updates.map(item => item.revision), [2, 3, 4]);
});

test("recovering the same task never replaces a newer displayed revision with a stale snapshot", async (t) => {
  const f = fixture(t);
  f.controller.select("task-one");
  f.operations[0].emit("task.snapshot", makeTask("task-one", 5, "awaiting_confirmation"));
  f.operations[0].emit("task.waiting_confirmation", makeTask("task-one", 5, "awaiting_confirmation"));
  const outcome = f.controller.confirm(makeTask("task-one", 3, "awaiting_confirmation")).then(() => null, error => error);
  assert.equal(f.selections.at(-1).task.revision, 5);
  f.operations[1].fail(new SopApiError("stale revision", 409));
  assert.equal((await outcome).status, 409);
  assert.equal(f.operations[2].kind, "events");
  f.operations[2].emit("task.snapshot", makeTask("task-one", 4, "awaiting_confirmation"));
  f.operations[2].emit("task.snapshot", makeTask("task-one", 6, "awaiting_confirmation"));
  f.operations[2].emit("task.waiting_confirmation", makeTask("task-one", 6, "awaiting_confirmation"));
  assert.deepEqual(f.updates.map(item => item.revision), [5, 6]);
});
