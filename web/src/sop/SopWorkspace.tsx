import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowLeft,
  ArrowRight,
  Bot,
  Check,
  CheckCircle2,
  ChevronDown,
  Circle,
  Clock3,
  Download,
  FileSpreadsheet,
  GitBranch,
  History,
  Layers3,
  LoaderCircle,
  MessageSquare,
  Paperclip,
  Plus,
  RefreshCw,
  Send,
  ShieldCheck,
  Workflow,
  X,
  AlertCircle,
  Database,
  BookOpen,
} from "lucide-react";
import { isTaskActive, sopApi } from "./sop-api";
import type {
  AgentRun,
  AgentSpec,
  AgentTask,
  Attachment,
  Capability,
  SavedSop,
} from "./sop-api";
import "./sop.css";

const STATUS_LABELS: Record<string, string> = {
  planning: "规划中",
  analyzing: "团队分析中",
  awaiting_confirmation: "等待你确认",
  executing: "执行中",
  succeeded: "已完成",
  failed: "失败",
  pending: "待开始",
  running: "处理中",
  completed: "已完成",
  unknown: "结果待核实",
};

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "操作失败，请稍后重试。";
}

function formatTime(value?: string): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleString("zh-CN", {
        month: "numeric",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
}

function displayValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function Status({ status }: { status: string }) {
  const running = isTaskActive(status) || status === "running";
  const Icon = running
    ? LoaderCircle
    : status === "succeeded" || status === "completed"
      ? CheckCircle2
      : status === "failed"
        ? AlertCircle
        : status === "awaiting_confirmation"
          ? Clock3
          : Circle;
  return (
    <span className={`sop-status sop-status-${status}`}>
      <Icon size={12} className={running ? "sop-spin" : undefined} />
      {STATUS_LABELS[status] || status}
    </span>
  );
}

function DataTable({
  rows,
  columnLabels = {},
  formatCell = displayValue,
}: {
  rows: Record<string, unknown>[];
  columnLabels?: Record<string, string>;
  formatCell?: (value: unknown, column: string) => string;
}) {
  const columns = [...new Set(rows.flatMap((row) => Object.keys(row)))].slice(
    0,
    12,
  );
  if (!columns.length) return <p className="sop-muted">没有数据行</p>;
  return (
    <div className="sop-table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{columnLabels[column] || column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 200).map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column}>{formatCell(row[column], column)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 200 ? (
        <p className="sop-table-note">共 {rows.length} 行，预览前 200 行。</p>
      ) : null}
    </div>
  );
}

function StructuredDetails({ value }: { value: unknown }) {
  return (
    <details className="sop-structured-details">
      <summary>
        结构化明细
        <ChevronDown size={12} />
      </summary>
      <pre className="sop-json">{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

function ResultText({ text }: { text: string }) {
  return (
    <div className="sop-result-markdown markdown-content">
      <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml>
        {text}
      </ReactMarkdown>
    </div>
  );
}

function ResultView({ value }: { value: unknown }) {
  if (value == null) return null;
  if (typeof value === "string") return <ResultText text={value} />;
  if (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every(
      (row) => row !== null && typeof row === "object" && !Array.isArray(row),
    )
  ) {
    return <DataTable rows={value as Record<string, unknown>[]} />;
  }
  if (typeof value === "object" && !Array.isArray(value)) {
    const object = value as Record<string, unknown>;
    const summary = typeof object.summary === "string" ? object.summary : "";
    const tableKey = ["items", "changes", "rows", "results", "products"].find(
      (key) => Array.isArray(object[key]),
    );
    const remaining = Object.fromEntries(
      Object.entries(object).filter(
        ([key]) => key !== "summary" && key !== tableKey,
      ),
    );
    return (
      <>
        {summary ? <ResultText text={summary} /> : null}
        {tableKey ? <ResultView value={object[tableKey]} /> : null}
        {Object.keys(remaining).length > 0 ? (
          <StructuredDetails value={remaining} />
        ) : null}
      </>
    );
  }
  return <StructuredDetails value={value} />;
}

function TaskSummary({ task }: { task: AgentTask }) {
  const names = new Map(
    (task.plan?.agents ?? []).map((agent) => [agent.id, agent.name]),
  );
  const summaries = (task.runs ?? []).flatMap((run) => {
    if (!run.output || typeof run.output !== "object") return [];
    const output = run.output as { summary?: unknown };
    return typeof output.summary === "string" && output.summary.trim()
      ? [{ run, summary: output.summary }]
      : [];
  });
  if (!summaries.length) return null;
  return (
    <section className="sop-section sop-team-summaries">
      <div className="sop-section-title">
        <MessageSquare size={16} />
        <h2>团队结论</h2>
      </div>
      {summaries.map(({ run, summary }, index) => (
        <article className="sop-summary-card" key={`${run.agentId}-${index}`}>
          <div>
            <Bot size={15} />
            <strong>{names.get(run.agentId) || run.agentId}</strong>
            <Status status={run.status} />
          </div>
          <ResultText text={summary} />
        </article>
      ))}
    </section>
  );
}

const LISTING_COLUMN_LABELS: Record<string, string> = {
  sku: "商品编码",
  name: "商品名称",
  channel: "渠道",
  region: "区域",
  oldStatus: "当前状态",
  newStatus: "调整后状态",
  actualStatus: "实际状态",
  expectedVersion: "数据版本",
  reason: "依据",
  matched: "对账一致",
};

function listingCell(value: unknown, column: string): string {
  if (["oldStatus", "newStatus", "actualStatus"].includes(column)) {
    if (value === "listed") return "上架";
    if (value === "unlisted") return "下架";
  }
  return displayValue(value);
}

function TaskChangeList({ task }: { task: AgentTask }) {
  const names = new Map(
    (task.plan?.agents ?? []).map((agent) => [agent.id, agent.name]),
  );
  // Only display rows returned by successful backend preflight calls. Agent
  // prose is never interpreted as an approved or executable change list.
  const previews = (task.runs ?? []).flatMap((run) =>
    (run.toolCalls ?? []).flatMap((call) => {
      if (
        call.name !== "preview_listing_changes" ||
        call.status !== "succeeded" ||
        !call.result ||
        typeof call.result !== "object"
      )
        return [];
      const result = call.result as Record<string, unknown>;
      if (
        !Array.isArray(result.items) ||
        !result.items.every(
          (item) =>
            item !== null && typeof item === "object" && !Array.isArray(item),
        )
      )
        return [];
      return [
        {
          call,
          agentId: run.agentId,
          result,
          rows: result.items as Record<string, unknown>[],
        },
      ];
    }),
  );
  if (!previews.length) return null;
  return (
    <section className="sop-section sop-change-list">
      <div className="sop-section-title">
        <FileSpreadsheet size={16} />
        <h2>本次变更清单</h2>
        <span className="sop-change-source">来自后台预检结果</span>
      </div>
      {previews.map(({ call, agentId, result, rows }, index) => (
        <div
          className="sop-change-preview"
          key={call.id || `${agentId}-${index}`}
        >
          <div className="sop-change-preview-heading">
            <span>
              {previews.length > 1 ? `预检方案 ${index + 1} · ` : ""}
              {names.get(agentId) || agentId}
            </span>
            <strong>{rows.length} 项变更</strong>
          </div>
          {rows.length ? (
            <DataTable
              rows={rows}
              columnLabels={LISTING_COLUMN_LABELS}
              formatCell={listingCell}
            />
          ) : (
            <p className="sop-muted">本次预检未产生变更项。</p>
          )}
          <StructuredDetails
            value={Object.fromEntries(
              Object.entries(result).filter(([key]) => key !== "items"),
            )}
          />
        </div>
      ))}
    </section>
  );
}

function AgentCard({
  agent,
  run,
  names,
  awaiting,
}: {
  agent: AgentSpec;
  run?: AgentRun;
  names: Map<string, string>;
  awaiting: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const status = run?.status || "pending";
  return (
    <article className={`sop-agent-card sop-agent-${status}`}>
      <button
        className="sop-agent-head"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
      >
        <span className="sop-agent-avatar">
          <Bot size={18} />
        </span>
        <span className="sop-agent-heading">
          <strong>{agent.name}</strong>
          <span>{agent.phase === "execution" ? "确认后执行" : "方案分析"}</span>
        </span>
        {awaiting && agent.phase === "execution" && !run ? (
          <span className="sop-muted sop-small">待确认</span>
        ) : (
          <Status status={status} />
        )}
        <ChevronDown size={14} className={expanded ? "sop-chevron-open" : ""} />
      </button>
      <p className="sop-agent-purpose">{agent.purpose}</p>
      {(agent.dependsOn?.length ?? 0) > 0 ? (
        <div className="sop-agent-deps">
          <GitBranch size={12} />
          依赖 {agent.dependsOn.map((id) => names.get(id) || id).join("、")}
        </div>
      ) : null}
      {expanded ? (
        <div className="sop-agent-details">
          <div>
            <span className="sop-field-label">工作指令</span>
            <p>{agent.instructions}</p>
          </div>
          {agent.outputContract ? (
            <div>
              <span className="sop-field-label">交付要求</span>
              <p>{agent.outputContract}</p>
            </div>
          ) : null}
          <div>
            <span className="sop-field-label">可用工具</span>
            <div className="sop-tool-tags">
              {agent.tools?.length ? (
                agent.tools.map((tool) => <code key={tool}>{tool}</code>)
              ) : (
                <span className="sop-muted">无需工具</span>
              )}
            </div>
          </div>
          {run?.output != null ? (
            <div>
              <span className="sop-field-label">执行结果</span>
              <ResultView value={run.output} />
            </div>
          ) : null}
          {run?.error ? <p className="sop-inline-error">{run.error}</p> : null}
        </div>
      ) : null}
    </article>
  );
}

function TaskResults({ task }: { task: AgentTask }) {
  const runs = task.runs ?? [];
  const results = runs.filter(
    (run) =>
      run.output != null || run.error || (run.toolCalls?.length ?? 0) > 0,
  );
  if (!results.length) return null;
  const names = new Map(
    (task.plan?.agents ?? []).map((agent) => [agent.id, agent.name]),
  );
  return (
    <details className="sop-section sop-team-records">
      <summary>
        <Layers3 size={16} />
        <span>团队产物与操作记录</span>
        <span className="sop-muted">{results.length} 份产物 · 展开查看</span>
        <ChevronDown size={14} />
      </summary>
      <div className="sop-results-list">
        {results.map((run, index) => (
          <details className="sop-result-card" key={`${run.agentId}-${index}`}>
            <summary>
              <span>
                <Bot size={15} />
                {names.get(run.agentId) || run.agentId}
              </span>
              <Status status={run.status} />
              <ChevronDown size={14} />
            </summary>
            <div className="sop-result-body">
              <ResultView value={run.output} />
              {run.error ? (
                <p className="sop-inline-error">{run.error}</p>
              ) : null}
              {(run.toolCalls ?? []).map((call, callIndex) => (
                <details
                  className="sop-tool-result"
                  key={call.id || `${call.name}-${callIndex}`}
                  open={
                    call.name === "preview_listing_changes" &&
                    call.status === "succeeded" &&
                    call.result != null
                  }
                >
                  <summary>
                    <code>{call.name}</code>
                    <span className="sop-muted">
                      {call.effect === "write" ? "写入" : "读取"} ·{" "}
                      {STATUS_LABELS[call.status] || call.status}
                    </span>
                    <ChevronDown size={12} />
                  </summary>
                  <div className="sop-tool-result-body">
                    <span className="sop-field-label">输入</span>
                    <ResultView value={call.arguments} />
                    {call.result != null ? (
                      <>
                        <span className="sop-field-label">返回结果</span>
                        <ResultView value={call.result} />
                      </>
                    ) : null}
                    {call.error ? (
                      <p className="sop-inline-error">{call.error}</p>
                    ) : null}
                  </div>
                </details>
              ))}
            </div>
          </details>
        ))}
      </div>
    </details>
  );
}

export default function SopWorkspace() {
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [sops, setSops] = useState<SavedSop[]>([]);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [activeId, setActiveId] = useState<string | null>(() =>
    new URLSearchParams(window.location.search).get("task"),
  );
  const [task, setTask] = useState<AgentTask | null>(null);
  const [taskLoading, setTaskLoading] = useState(false);
  const [request, setRequest] = useState("");
  const [feedback, setFeedback] = useState("");
  const [attachment, setAttachment] = useState<Attachment | null>(null);
  const [selectedSopId, setSelectedSopId] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [service, setService] = useState<"checking" | "ready" | "unavailable">(
    "checking",
  );
  const [sidebarTab, setSidebarTab] = useState<"tasks" | "sops">("tasks");
  const [refreshKey, setRefreshKey] = useState(0);
  const [resourcesLoading, setResourcesLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const requestRef = useRef<HTMLTextAreaElement>(null);
  const mutationRef = useRef<AbortController | null>(null);
  const activeIdRef = useRef(activeId);
  activeIdRef.current = activeId;
  const mountedRef = useRef(true);
  const resourceGenerationRef = useRef(0);

  const refreshResources = useCallback(async (signal?: AbortSignal) => {
    const generation = ++resourceGenerationRef.current;
    setResourcesLoading(true);
    const results = await Promise.allSettled([
      sopApi.tasks(signal),
      sopApi.sops(signal),
      sopApi.capabilities(signal),
      sopApi.health(signal),
    ]);
    if (
      signal?.aborted ||
      !mountedRef.current ||
      generation !== resourceGenerationRef.current
    )
      return;
    const [taskResult, sopResult, capabilityResult, healthResult] = results;
    if (taskResult.status === "fulfilled")
      setTasks((current) => {
        const known = new Map(current.map((item) => [item.id, item]));
        return (taskResult.value.tasks ?? []).map((item) => {
          const existing = known.get(item.id);
          return existing && existing.revision > item.revision
            ? existing
            : item;
        });
      });
    if (sopResult.status === "fulfilled") setSops(sopResult.value.sops ?? []);
    if (capabilityResult.status === "fulfilled")
      setCapabilities(capabilityResult.value.tools ?? []);
    const problem = results.find((result) => result.status === "rejected");
    if (
      healthResult.status === "fulfilled" &&
      healthResult.value.ok !== false &&
      taskResult.status === "fulfilled" &&
      capabilityResult.status === "fulfilled"
    ) {
      setService("ready");
    } else setService("unavailable");
    if (problem?.status === "rejected") setError(errorText(problem.reason));
    else if (
      healthResult.status === "fulfilled" &&
      healthResult.value.ok === false
    )
      setError(healthResult.value.error || "SOP 服务尚未就绪。");
    setResourcesLoading(false);
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    const controller = new AbortController();
    void refreshResources(controller.signal);
    return () => {
      mountedRef.current = false;
      controller.abort();
      mutationRef.current?.abort();
    };
  }, [refreshResources]);

  useEffect(() => {
    const onPopState = () =>
      setActiveId(new URLSearchParams(window.location.search).get("task"));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    const url = new URL(window.location.href);
    if (activeId) url.searchParams.set("task", activeId);
    else url.searchParams.delete("task");
    window.history.replaceState(null, "", url);
  }, [activeId]);

  useEffect(() => {
    setTask(null);
    setFeedback("");
    if (!activeId) {
      setTaskLoading(false);
      return;
    }
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let previousStatus: string | undefined;
    let attempts = 0;
    setTaskLoading(true);
    const load = async () => {
      try {
        const next = await sopApi.task(activeId, controller.signal);
        if (controller.signal.aborted) return;
        attempts = 0;
        setTask(next);
        setTaskLoading(false);
        setTasks((current) =>
          [next, ...current.filter((item) => item.id !== next.id)].sort(
            (left, right) => right.createdAt.localeCompare(left.createdAt),
          ),
        );
        if (
          previousStatus &&
          previousStatus !== next.status &&
          !isTaskActive(next.status)
        )
          void refreshResources(controller.signal);
        previousStatus = next.status;
        if (isTaskActive(next.status))
          timer = setTimeout(() => {
            void load();
          }, 1500);
      } catch (cause) {
        if (controller.signal.aborted) return;
        setTaskLoading(false);
        setError(errorText(cause));
        // Short reconnect window while a task is running; settled tasks have no poller.
        if (isTaskActive(previousStatus) && attempts < 3) {
          attempts += 1;
          timer = setTimeout(() => {
            void load();
          }, attempts * 2000);
        }
      }
    };
    void load();
    return () => {
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [activeId, refreshKey, refreshResources]);

  const beginMutation = (name: string): AbortController => {
    mutationRef.current?.abort();
    const controller = new AbortController();
    mutationRef.current = controller;
    setPending(name);
    setError("");
    setNotice("");
    return controller;
  };

  const finishMutation = (controller: AbortController) => {
    if (
      mutationRef.current === controller &&
      !controller.signal.aborted &&
      mountedRef.current
    )
      setPending(null);
  };

  const createTask = async (event: FormEvent) => {
    event.preventDefault();
    if (!request.trim() || pending) return;
    const controller = beginMutation("create");
    const initialSelection = activeIdRef.current;
    try {
      const next = await sopApi.create(
        {
          request: request.trim(),
          ...(attachment ? { attachmentId: attachment.id } : {}),
          ...(selectedSopId ? { sopId: selectedSopId } : {}),
        },
        controller.signal,
      );
      if (controller.signal.aborted || !mountedRef.current) return;
      setTasks((current) => [
        next,
        ...current.filter((item) => item.id !== next.id),
      ]);
      if (activeIdRef.current === initialSelection) {
        setActiveId(next.id);
        setTask(next);
      }
      setRequest("");
      setAttachment(null);
      setSelectedSopId("");
      void refreshResources(controller.signal);
    } catch (cause) {
      if (!controller.signal.aborted) setError(errorText(cause));
    } finally {
      finishMutation(controller);
    }
  };

  const mutateTask = async (action: "confirm" | "feedback") => {
    if (!task || pending || task.status !== "awaiting_confirmation") return;
    if (action === "feedback" && !feedback.trim()) return;
    if (action === "confirm" && questions.length > 0) return;
    const target = task;
    const controller = beginMutation(action);
    try {
      const next =
        action === "confirm"
          ? await sopApi.confirm(target, controller.signal)
          : await sopApi.feedback(target, feedback.trim(), controller.signal);
      if (controller.signal.aborted || !mountedRef.current) return;
      if (activeIdRef.current === target.id) {
        setTask(next);
        setFeedback("");
        setRefreshKey((value) => value + 1);
      }
      void refreshResources(controller.signal);
    } catch (cause) {
      if (!controller.signal.aborted) {
        setError(errorText(cause));
        // A stale approval is never retried. Load the new revision for review.
        if (activeIdRef.current === target.id)
          setRefreshKey((value) => value + 1);
      }
    } finally {
      finishMutation(controller);
    }
  };

  const upload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || pending) return;
    if (!/\.(csv|xlsx)$/i.test(file.name)) {
      setError("请选择 .csv 或 .xlsx 格式的清单。");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError("文件大小不能超过 5 MB。");
      return;
    }
    const controller = beginMutation("upload");
    try {
      const result = await sopApi.upload(file, controller.signal);
      if (!controller.signal.aborted && mountedRef.current)
        setAttachment(result);
    } catch (cause) {
      if (!controller.signal.aborted) setError(errorText(cause));
    } finally {
      finishMutation(controller);
    }
  };

  const setupDemo = async () => {
    if (pending) return;
    const controller = beginMutation("demo");
    try {
      const result = await sopApi.setupDemo(controller.signal);
      if (!controller.signal.aborted && mountedRef.current)
        setNotice(
          `演示商品已准备，共 ${result.products?.length ?? 0} 项。可下载示例清单，上传后提交任务。`,
        );
    } catch (cause) {
      if (!controller.signal.aborted) setError(errorText(cause));
    } finally {
      finishMutation(controller);
    }
  };

  const newTask = (sop?: SavedSop) => {
    setActiveId(null);
    setTask(null);
    setFeedback("");
    setRequest("");
    setAttachment(null);
    setError("");
    setNotice("");
    setSelectedSopId(sop?.id || "");
    requestRef.current?.focus();
  };
  const selectedSop = sops.find((sop) => sop.id === selectedSopId);
  const agents = task?.plan?.agents ?? [];
  const names = useMemo(
    () => new Map(agents.map((agent) => [agent.id, agent.name])),
    [agents],
  );
  const runs = useMemo(
    () => new Map((task?.runs ?? []).map((run) => [run.agentId, run])),
    [task?.runs],
  );
  const sourceSop = sops.find((sop) => sop.id === task?.sourceSopId);
  const canConfirm = task?.status === "awaiting_confirmation";
  const questions = [
    ...new Set(
      (task?.runs ?? []).flatMap((run) => {
        if (!run.output || typeof run.output !== "object") return [];
        const output = run.output as { questions?: unknown };
        return Array.isArray(output.questions)
          ? output.questions.filter(
              (question): question is string =>
                typeof question === "string" && question.trim().length > 0,
            )
          : [];
      }),
    ),
  ];

  return (
    <div className="sop-workspace">
      <aside className="sop-sidebar">
        <a className="sop-back" href="/">
          <ArrowLeft size={15} />
          Data Agent<span>返回数据对话</span>
        </a>
        <button className="sop-new-task" onClick={() => newTask()}>
          <Plus size={17} />
          新任务
        </button>
        <div
          className="sop-sidebar-tabs"
          role="tablist"
          aria-label="任务与流程"
        >
          <button
            id="sop-task-tab"
            role="tab"
            aria-selected={sidebarTab === "tasks"}
            aria-controls="sop-sidebar-list"
            onClick={() => setSidebarTab("tasks")}
          >
            <History size={14} />
            任务
          </button>
          <button
            id="sop-library-tab"
            role="tab"
            aria-selected={sidebarTab === "sops"}
            aria-controls="sop-sidebar-list"
            onClick={() => setSidebarTab("sops")}
          >
            <BookOpen size={14} />
            SOP <span>{sops.length}</span>
          </button>
        </div>
        <div
          id="sop-sidebar-list"
          className="sop-sidebar-list"
          role="tabpanel"
          aria-labelledby={
            sidebarTab === "tasks" ? "sop-task-tab" : "sop-library-tab"
          }
        >
          {sidebarTab === "tasks" ? (
            tasks.length ? (
              tasks.map((item) => (
                <button
                  key={item.id}
                  className={`sop-history-item ${activeId === item.id ? "is-active" : ""}`}
                  onClick={() => {
                    setError("");
                    setNotice("");
                    setActiveId(item.id);
                  }}
                >
                  <span className="sop-history-title">
                    {item.plan?.name || item.request}
                  </span>
                  <span className="sop-history-meta">
                    <Status status={item.status} />
                    <time>{formatTime(item.createdAt)}</time>
                  </span>
                </button>
              ))
            ) : (
              <div className="sop-sidebar-empty">
                <MessageSquare size={23} />
                <p>还没有任务</p>
                <span>提出需求后，团队和进度会保存在这里。</span>
              </div>
            )
          ) : sops.length ? (
            sops.map((sop) => (
              <div className="sop-saved-card" key={sop.id}>
                <div>
                  <Workflow size={15} />
                  <strong>{sop.name}</strong>
                  <span>v{sop.version}</span>
                </div>
                <p>{sop.description}</p>
                <span className="sop-muted sop-small">
                  {sop.plan?.agents?.length ?? 0} 个角色 ·{" "}
                  {formatTime(sop.createdAt)}
                </span>
                <button onClick={() => newTask(sop)}>
                  用于新任务
                  <ArrowRight size={13} />
                </button>
              </div>
            ))
          ) : (
            <div className="sop-sidebar-empty">
              <Workflow size={23} />
              <p>还没有保存的 SOP</p>
              <span>确认方案后，角色定义与流程将保存供下次复用。</span>
            </div>
          )}
        </div>
        <div className="sop-sidebar-footer">
          <span className={`sop-service-dot ${service}`} />
          <span>
            {service === "ready"
              ? "服务已连接"
              : service === "checking"
                ? "检查服务连接"
                : "服务连接待检查"}
          </span>
          <button
            aria-label="刷新服务与任务列表"
            disabled={resourcesLoading}
            onClick={() => {
              setError("");
              void refreshResources();
            }}
          >
            <RefreshCw
              size={13}
              className={resourcesLoading ? "sop-spin" : undefined}
            />
          </button>
        </div>
      </aside>

      <main className="sop-main">
        <header className="sop-page-header">
          <div>
            <span className="sop-page-icon">
              <Workflow size={20} />
            </span>
            <div>
              <h1>SOP Agent</h1>
              <p>从一次需求，形成下一次可复用的协作流程</p>
            </div>
          </div>
          <span className="sop-demo-badge">
            <Database size={13} />
            商品模拟环境
          </span>
        </header>
        <div className="sop-mobile-navigation">
          <a href="/">
            <ArrowLeft size={13} />
            数据对话
          </a>
          <button onClick={() => newTask()}>
            <Plus size={13} />
            新任务
          </button>
          <select
            aria-label="选择历史任务"
            value={activeId || ""}
            onChange={(event) => setActiveId(event.target.value || null)}
          >
            <option value="">历史任务</option>
            {tasks.map((item) => (
              <option key={item.id} value={item.id}>
                {item.plan?.name || item.request}
              </option>
            ))}
          </select>
          <select
            aria-label="选择已保存的 SOP"
            value={selectedSopId}
            onChange={(event) => {
              const sop = sops.find((item) => item.id === event.target.value);
              if (sop) newTask(sop);
              else setSelectedSopId("");
            }}
          >
            <option value="">复用 SOP</option>
            {sops.map((sop) => (
              <option key={sop.id} value={sop.id}>
                {sop.name} · v{sop.version}
              </option>
            ))}
          </select>
        </div>
        <div className="sop-environment-note">
          <ShieldCheck size={15} />
          <span>
            商品数据与上下架操作使用演示后台；角色规划和子 Agent
            分析由实际配置的模型完成。
          </span>
          <button
            disabled={pending !== null}
            onClick={() => {
              void setupDemo();
            }}
          >
            {pending === "demo" ? (
              <LoaderCircle size={13} className="sop-spin" />
            ) : (
              <Database size={13} />
            )}
            准备演示数据
          </button>
          <a href="/api/sop/demo.csv" download>
            <Download size={13} />
            示例清单
          </a>
        </div>
        {error ? (
          <div className="sop-alert sop-alert-error" role="alert">
            <AlertCircle size={17} />
            <div>
              <strong>暂时无法完成操作</strong>
              <p>{error}</p>
            </div>
            <button aria-label="关闭错误提示" onClick={() => setError("")}>
              <X size={15} />
            </button>
          </div>
        ) : null}
        {notice ? (
          <div className="sop-alert sop-alert-success" role="status">
            <CheckCircle2 size={17} />
            <p>{notice}</p>
            <button aria-label="关闭提示" onClick={() => setNotice("")}>
              <X size={15} />
            </button>
          </div>
        ) : null}
        <div className={`sop-content ${task ? "has-task" : ""}`}>
          <div className="sop-conversation">
            <div className="sop-conversation-scroll">
              {taskLoading && !task ? (
                <div className="sop-loading" role="status">
                  <LoaderCircle size={20} className="sop-spin" />
                  正在读取任务…
                </div>
              ) : task ? (
                <>
                  <div className="sop-request-message">
                    <span className="sop-field-label">你的需求</span>
                    <p>{task.request}</p>
                    <time>{formatTime(task.createdAt)}</time>
                  </div>
                  <div className="sop-plan-intro">
                    <div className="sop-section-title">
                      <Workflow size={17} />
                      <h2>{task.plan?.name || "Planner 正在组织团队"}</h2>
                      <Status status={task.status} />
                    </div>
                    {task.plan?.description ? (
                      <p>{task.plan.description}</p>
                    ) : (
                      <p className="sop-muted">
                        正在结合需求与项目工具，自主设计角色及任务依赖。
                      </p>
                    )}
                    {task.sourceSopId ? (
                      <div className="sop-reuse-note">
                        <BookOpen size={14} />
                        复用 {sourceSop?.name || task.sourceSopId}
                        {sourceSop ? ` · v${sourceSop.version}` : ""}{" "}
                        的角色定义与流程
                      </div>
                    ) : null}
                  </div>
                  {task.error ? (
                    <div className="sop-task-failure" role="alert">
                      <AlertCircle size={18} />
                      <div>
                        <strong>任务未完成</strong>
                        <p>{task.error}</p>
                        <span>
                          已完成的步骤保留在下方。可检查服务配置后提交新任务。
                        </span>
                      </div>
                    </div>
                  ) : null}
                  {task.feedback?.length ? (
                    <details className="sop-feedback-history">
                      <summary>
                        <MessageSquare size={14} />
                        已提交的补充说明（{task.feedback.length}）
                        <ChevronDown size={13} />
                      </summary>
                      <ResultView value={task.feedback} />
                    </details>
                  ) : null}
                  <TaskSummary task={task} />
                  <TaskChangeList task={task} />
                  <TaskResults task={task} />
                  {canConfirm ? (
                    <section className="sop-confirm-card">
                      <div>
                        <span className="sop-confirm-icon">
                          <ShieldCheck size={20} />
                        </span>
                        <div>
                          <h2>请确认本次方案</h2>
                          <p>
                            核对上方团队结论、变更清单和团队执行步骤。确认后将保存
                            SOP，并按当前方案执行模拟后台操作。
                          </p>
                        </div>
                      </div>
                      {questions.length > 0 ? (
                        <div className="sop-open-questions">
                          <strong>团队需要你补充以下信息</strong>
                          <ul>
                            {questions.map((question) => (
                              <li key={question}>{question}</li>
                            ))}
                          </ul>
                          <p>请在下方回答后提交，Planner 会更新方案。</p>
                        </div>
                      ) : null}
                      <label htmlFor="sop-feedback">
                        需要调整？把补充要求交给 Planner
                      </label>
                      <textarea
                        id="sop-feedback"
                        value={feedback}
                        onChange={(event) => setFeedback(event.target.value)}
                        placeholder="例如：排除整箱商品，仅处理华东渠道。"
                        rows={3}
                        disabled={pending !== null}
                      />
                      <div className="sop-confirm-actions">
                        <button
                          className="sop-button"
                          disabled={pending !== null || !feedback.trim()}
                          onClick={() => {
                            void mutateTask("feedback");
                          }}
                        >
                          {pending === "feedback" ? (
                            <LoaderCircle size={14} className="sop-spin" />
                          ) : (
                            <MessageSquare size={14} />
                          )}
                          补充并重新规划
                        </button>
                        <button
                          className="sop-button sop-button-primary"
                          disabled={
                            pending !== null ||
                            !task.planHash ||
                            feedback.trim().length > 0 ||
                            questions.length > 0
                          }
                          onClick={() => {
                            void mutateTask("confirm");
                          }}
                        >
                          {pending === "confirm" ? (
                            <LoaderCircle size={14} className="sop-spin" />
                          ) : (
                            <Check size={15} />
                          )}
                          确认方案并执行
                        </button>
                      </div>
                      {feedback.trim() ? (
                        <p className="sop-confirm-hint">
                          请先提交补充要求，查看更新后的方案再确认。
                        </p>
                      ) : null}
                    </section>
                  ) : null}
                  {task.sopId ? (
                    <div className="sop-completion-note">
                      <BookOpen size={17} />
                      <div>
                        <strong>SOP 已保存</strong>
                        <p>
                          角色定义与流程已保留，可在左侧 SOP 中用于下一次任务。
                        </p>
                      </div>
                      <button
                        onClick={() => {
                          setSidebarTab("sops");
                          const sop = sops.find(
                            (item) => item.id === task.sopId,
                          );
                          if (sop) newTask(sop);
                          else setNotice("请刷新 SOP 列表后选择已保存的流程。");
                        }}
                      >
                        复用流程
                        <ArrowRight size={14} />
                      </button>
                    </div>
                  ) : null}
                  {isTaskActive(task.status) ? (
                    <div className="sop-running-note" role="status">
                      <LoaderCircle size={15} className="sop-spin" />
                      <span>
                        {task.status === "planning"
                          ? "Planner 正在规划角色与依赖…"
                          : task.status === "analyzing"
                            ? "子 Agent 正在分析并调用项目工具…"
                            : "正在执行已确认的步骤…"}
                        关闭页面不会取消已提交的任务。
                      </span>
                    </div>
                  ) : null}
                </>
              ) : (
                <div className="sop-empty-state">
                  <div className="sop-empty-icon">
                    <Workflow size={30} />
                  </div>
                  <h2>把需求交给一个会组建团队的 Agent</h2>
                  <p>
                    Planner
                    根据任务创建角色，团队先分析，你确认后执行；处理方式保存成
                    SOP，供下一次直接复用。
                  </p>
                  <div className="sop-scenario-steps">
                    <div>
                      <span>01</span>
                      <strong>提出需求</strong>
                      <p>输入目标，按需附上商品清单。</p>
                    </div>
                    <div>
                      <span>02</span>
                      <strong>团队协作与确认</strong>
                      <p>查看动态角色、分析产物，补充或确认。</p>
                    </div>
                    <div>
                      <span>03</span>
                      <strong>保存并复用 SOP</strong>
                      <p>下次换一份清单，沿用已保存的流程。</p>
                    </div>
                  </div>
                  <button
                    className="sop-example"
                    onClick={() => {
                      setRequest(
                        "请根据附件中的操作要求处理商品上下架，先核对商品、渠道和当前状态，发现冲突时请说明，确认后再执行。",
                      );
                      requestRef.current?.focus();
                    }}
                  >
                    试试：按 Excel 清单处理商品上下架
                    <ArrowRight size={15} />
                  </button>
                  {capabilities.length > 0 ? (
                    <div className="sop-capabilities">
                      <span>
                        项目提供 {capabilities.length} 项工具，角色由 Planner
                        按需创建
                      </span>
                      <div>
                        {capabilities.map((tool) => (
                          <span key={tool.name}>
                            {tool.name}
                            <small>
                              {tool.effect === "write" ? "确认后写入" : "读取"}
                            </small>
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              )}
            </div>
            <form
              className="sop-composer"
              onSubmit={(event) => {
                void createTask(event);
              }}
            >
              {selectedSop ? (
                <div className="sop-selected-sop">
                  <BookOpen size={14} />
                  <span>
                    复用 {selectedSop.name} · v{selectedSop.version}
                  </span>
                  <button
                    type="button"
                    aria-label="取消指定 SOP"
                    onClick={() => setSelectedSopId("")}
                  >
                    <X size={14} />
                  </button>
                </div>
              ) : null}
              {attachment ? (
                <div className="sop-attachment">
                  <FileSpreadsheet size={19} />
                  <div>
                    <strong>{attachment.name}</strong>
                    <span>
                      {attachment.rowCount} 行 · {attachment.columns.join("、")}
                    </span>
                  </div>
                  <button
                    type="button"
                    disabled={pending !== null}
                    aria-label="移除附件"
                    onClick={() => setAttachment(null)}
                  >
                    <X size={15} />
                  </button>
                </div>
              ) : null}
              {attachment?.preview?.length ? (
                <details className="sop-attachment-preview">
                  <summary>
                    查看清单预览
                    <ChevronDown size={12} />
                  </summary>
                  <DataTable rows={attachment.preview.slice(0, 5)} />
                </details>
              ) : null}
              <textarea
                ref={requestRef}
                aria-label="任务需求"
                value={request}
                onChange={(event) => setRequest(event.target.value)}
                placeholder={
                  task
                    ? "提出一个新任务，或在 SOP 中选择流程复用…"
                    : "描述你希望完成的事情，可附上 Excel 或 CSV 清单…"
                }
                rows={3}
                disabled={pending === "create"}
                maxLength={16000}
                onKeyDown={(event) => {
                  if (
                    (event.metaKey || event.ctrlKey) &&
                    event.key === "Enter"
                  ) {
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
              />
              <div className="sop-composer-bottom">
                <div>
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".csv,.xlsx"
                    hidden
                    onChange={(event) => {
                      void upload(event);
                    }}
                  />
                  <button
                    type="button"
                    className="sop-upload-button"
                    disabled={pending !== null}
                    onClick={() => fileRef.current?.click()}
                  >
                    {pending === "upload" ? (
                      <LoaderCircle size={15} className="sop-spin" />
                    ) : (
                      <Paperclip size={16} />
                    )}
                    <span>
                      {pending === "upload" ? "正在解析" : "添加清单"}
                    </span>
                  </button>
                  <span className="sop-composer-hint">
                    CSV / XLSX · 最大 5 MB
                  </span>
                </div>
                <button
                  type="submit"
                  className="sop-send-button"
                  disabled={!request.trim() || pending !== null}
                >
                  {pending === "create" ? (
                    <LoaderCircle size={16} className="sop-spin" />
                  ) : (
                    <Send size={15} />
                  )}
                  <span>提交任务</span>
                </button>
              </div>
            </form>
            <p className="sop-bottom-note">
              每次复用都会处理本次输入，并重新确认具体变更。⌘ / Ctrl + Enter
              提交
            </p>
          </div>
          {task ? (
            <aside className="sop-team-panel">
              <div className="sop-team-header">
                <div>
                  <Bot size={17} />
                  <h2>本次协作团队</h2>
                </div>
                <span>{agents.length} 个角色</span>
              </div>
              <p className="sop-team-description">
                {task.sourceSopId
                  ? "角色来自已保存的 SOP，每次任务使用新的执行实例。"
                  : "以下角色与分工由 Planner 根据本次需求生成。"}
              </p>
              {agents.length ? (
                <div className="sop-agent-list">
                  {agents.map((agent) => (
                    <AgentCard
                      key={`${task.id}-${agent.id}`}
                      agent={agent}
                      run={runs.get(agent.id)}
                      names={names}
                      awaiting={!!canConfirm}
                    />
                  ))}
                </div>
              ) : (
                <div className="sop-team-loading">
                  <LoaderCircle size={18} className="sop-spin" />
                  <span>正在设计角色与任务依赖</span>
                </div>
              )}
              {task.plan?.matchHints?.length ? (
                <div className="sop-match-hints">
                  <span className="sop-field-label">流程适用线索</span>
                  <div>
                    {task.plan.matchHints.map((hint) => (
                      <span key={hint}>{hint}</span>
                    ))}
                  </div>
                </div>
              ) : null}
            </aside>
          ) : null}
        </div>
      </main>
    </div>
  );
}
