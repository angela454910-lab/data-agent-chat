import { createSseParser } from "./sop-sse";
import type { ServerSentEvent } from "./sop-sse";

export interface AgentSpec {
  id: string;
  name: string;
  purpose: string;
  instructions: string;
  tools: string[];
  dependsOn: string[];
  phase: "analysis" | "execution";
  outputContract: string;
}

export interface AgentPlan {
  name: string;
  description: string;
  matchHints: string[];
  agents: AgentSpec[];
}

export interface AgentToolCall {
  id: string;
  name: string;
  arguments: unknown;
  result?: unknown;
  effect: string;
  status: string;
  error?: string;
}

export interface AgentRun {
  agentId: string;
  status: string;
  output?: unknown;
  toolCalls?: AgentToolCall[];
  error?: string;
}

export type TaskStatus =
  | "planning"
  | "analyzing"
  | "awaiting_confirmation"
  | "executing"
  | "succeeded"
  | "failed";

export interface AgentTask {
  id: string;
  request: string;
  context?: unknown;
  sourceSopId?: string;
  status: TaskStatus;
  revision: number;
  planHash: string;
  plan?: AgentPlan;
  runs?: AgentRun[];
  feedback?: unknown[];
  sopId?: string;
  error?: string;
  createdAt: string;
  updatedAt: string;
  approvedAt?: string;
}

export interface SavedSop {
  id: string;
  name: string;
  description: string;
  matchHints?: string[];
  plan: AgentPlan;
  version: number;
  createdAt: string;
}

export interface Attachment {
  id: string;
  name: string;
  rowCount: number;
  columns: string[];
  preview: Record<string, unknown>[];
}

export interface Capability {
  name: string;
  description: string;
  effect: "read" | "write";
}

export class SopApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "SopApiError";
    this.status = status;
  }
}

const BASE = "/api/sop";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      credentials: "same-origin",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new SopApiError(
      "无法连接服务，请确认 Data Agent 后端和 SopAgent 服务已启动。",
      0,
    );
  }
  const contentType = response.headers.get("content-type") || "";
  const data: unknown = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    if (typeof data === "object" && data !== null) {
      const value = data as { error?: unknown; detail?: unknown };
      const detail = value.error ?? value.detail;
      if (typeof detail === "string") message = detail;
    }
    throw new SopApiError(message, response.status);
  }
  if (!contentType.includes("application/json")) {
    throw new SopApiError(
      "SOP 接口未就绪，请确认后端已加载 SOP 路由。",
      response.status,
    );
  }
  return data as T;
}

function json<T>(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<T> {
  return request<T>(path, {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export type TaskEventName =
  | "task.snapshot"
  | "task.updated"
  | "task.waiting_confirmation"
  | "task.succeeded"
  | "task.failed";

export interface TaskStreamEvent {
  event: TaskEventName;
  task: AgentTask;
}

export type TaskEventListener = (event: TaskStreamEvent) => void;

export interface CreateTaskInput {
  request: string;
  attachmentId?: string;
  sopId?: string;
}

export const isTaskStopEvent = (event: TaskEventName): boolean =>
  event === "task.waiting_confirmation" ||
  event === "task.succeeded" ||
  event === "task.failed";

function taskEvent(frame: ServerSentEvent): TaskStreamEvent | null {
  if (frame.event === "error") {
    let message = "SOP 实时连接发生错误。";
    try {
      const value = JSON.parse(frame.data) as { error?: string; message?: string };
      message = value.error || value.message || message;
    } catch {
      // Never display a raw gateway or proxy response as product content.
    }
    throw new SopApiError(message, 0);
  }
  if (![
    "task.snapshot", "task.updated", "task.waiting_confirmation",
    "task.succeeded", "task.failed",
  ].includes(frame.event)) return null;
  let task: AgentTask;
  try {
    task = JSON.parse(frame.data) as AgentTask;
  } catch {
    throw new SopApiError("SOP 实时事件格式错误，正在恢复任务状态。", 0);
  }
  if (
    !task || typeof task.id !== "string" || !task.id ||
    !Number.isSafeInteger(task.revision) || task.revision < 0 ||
    !["planning", "analyzing", "awaiting_confirmation", "executing", "succeeded", "failed"].includes(task.status)
  ) throw new SopApiError("SOP 实时事件缺少有效任务状态。", 0);
  const finalStatuses: Record<string, string> = {
    "task.waiting_confirmation": "awaiting_confirmation",
    "task.succeeded": "succeeded",
    "task.failed": "failed",
  };
  const expected = finalStatuses[frame.event];
  if (expected && task.status !== expected) {
    throw new SopApiError("SOP 实时停点与任务状态不一致。", 0);
  }
  return { event: frame.event as TaskEventName, task };
}

/** Consume exactly one request stream. Reconnect policy belongs to its owner. */
async function streamTask(
  path: string,
  onEvent: TaskEventListener,
  signal: AbortSignal,
  body?: unknown,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      method: body === undefined ? "GET" : "POST",
      credentials: "same-origin",
      signal,
      headers: {
        Accept: "text/event-stream",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new SopApiError("无法连接 SOP 实时服务。", 0);
  }
  const contentType = response.headers.get("content-type")?.toLowerCase() || "";
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    if (contentType.includes("application/json")) {
      try {
        const value = await response.json() as { error?: unknown; detail?: unknown };
        const detail = value.error ?? value.detail;
        if (typeof detail === "string") message = detail;
      } catch {
        // Keep the HTTP status if a gateway returned malformed JSON.
      }
    } else {
      await response.body?.cancel();
    }
    throw new SopApiError(message, response.status);
  }
  if (!contentType.includes("text/event-stream") || !response.body) {
    await response.body?.cancel();
    throw new SopApiError("SOP 服务未返回实时事件流，请检查服务版本。", 0);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let stopped = false;
  const parser = createSseParser((frame) => {
    if (stopped) return;
    const event = taskEvent(frame);
    if (!event) return;
    if (isTaskStopEvent(event.event)) stopped = true;
    onEvent(event);
  });
  try {
    while (!stopped) {
      const { value, done } = await reader.read();
      if (done) {
        parser.push(decoder.decode());
        parser.finish();
        if (!stopped) throw new SopApiError("SOP 实时连接意外结束。", 0);
        break;
      }
      parser.push(decoder.decode(value, { stream: true }));
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export const sopApi = {
  health: (signal?: AbortSignal) =>
    request<{ ok?: boolean; service?: string; error?: string }>("/health", {
      signal,
    }),
  capabilities: (signal?: AbortSignal) =>
    request<{ tools: Capability[] }>("/capabilities", { signal }),
  tasks: (signal?: AbortSignal) =>
    request<{ tasks: AgentTask[] }>("/tasks", { signal }),
  task: (id: string, signal?: AbortSignal) =>
    request<AgentTask>(`/tasks/${encodeURIComponent(id)}`, { signal }),
  sops: (signal?: AbortSignal) =>
    request<{ sops: SavedSop[] }>("/sops", { signal }),
  events: (id: string, onEvent: TaskEventListener, signal: AbortSignal) =>
    streamTask(`/tasks/${encodeURIComponent(id)}/events`, onEvent, signal),
  create: (body: CreateTaskInput, onEvent: TaskEventListener, signal: AbortSignal) =>
    streamTask("/tasks", onEvent, signal, body),
  confirm: (task: AgentTask, onEvent: TaskEventListener, signal: AbortSignal) =>
    streamTask(`/tasks/${encodeURIComponent(task.id)}/confirm`, onEvent, signal, {
      revision: task.revision, planHash: task.planHash,
    }),
  feedback: (task: AgentTask, message: string, onEvent: TaskEventListener, signal: AbortSignal) =>
    streamTask(`/tasks/${encodeURIComponent(task.id)}/feedback`, onEvent, signal, {
      revision: task.revision, message,
    }),
  setupDemo: (signal?: AbortSignal) =>
    json<{ products: unknown[] }>("/demo/setup", {}, signal),
  upload: (file: File, signal?: AbortSignal) =>
    request<Attachment>(
      `/attachments?filename=${encodeURIComponent(file.name)}`,
      {
        method: "POST",
        signal,
        headers: { "Content-Type": "application/octet-stream" },
        body: file,
      },
    ),
};

export const isTaskActive = (status?: string): boolean =>
  status === "planning" || status === "analyzing" || status === "executing";
