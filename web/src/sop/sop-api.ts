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
  create: (
    body: { request: string; attachmentId?: string; sopId?: string },
    signal?: AbortSignal,
  ) => json<AgentTask>("/tasks", body, signal),
  confirm: (task: AgentTask, signal?: AbortSignal) =>
    json<AgentTask>(
      `/tasks/${encodeURIComponent(task.id)}/confirm`,
      { revision: task.revision, planHash: task.planHash },
      signal,
    ),
  feedback: (task: AgentTask, message: string, signal?: AbortSignal) =>
    json<AgentTask>(
      `/tasks/${encodeURIComponent(task.id)}/feedback`,
      { revision: task.revision, message },
      signal,
    ),
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
