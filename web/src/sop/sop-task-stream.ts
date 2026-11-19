import { isTaskActive, isTaskStopEvent, sopApi, SopApiError } from "./sop-api";
import type { AgentTask, CreateTaskInput, TaskEventListener, TaskStreamEvent } from "./sop-api";

type Transport = Pick<typeof sopApi, "events" | "create" | "confirm" | "feedback">;
type Operation = (listener: TaskEventListener, signal: AbortSignal) => Promise<void>;

export interface TaskStreamCallbacks {
  onSelection: (id: string | null, initial: AgentTask | null) => void;
  onTask: (task: AgentTask) => void;
  onLoading: (loading: boolean) => void;
  onIssue: (message: string, reconnecting: boolean) => void;
  onSettled: (task: AgentTask) => void;
  onUncertain: () => void;
}

export class SopTaskRecoveryError extends Error {
  name = "SopTaskRecoveryError";
}

interface FirstSnapshot {
  resolve: (task: AgentTask) => void;
  reject: (error: Error) => void;
}

interface Subscription {
  controller: AbortController;
  taskId: string | null;
  revision: number;
  latest: AgentTask | null;
  attempts: number;
  received: boolean;
  first?: FirstSnapshot;
  retryTimer?: ReturnType<typeof setTimeout>;
}

function aborted(): DOMException {
  return new DOMException("实时订阅已切换。", "AbortError");
}

/** Owns one subscription; state changes never create additional subscriptions. */
export class SopTaskStreamController {
  private transport: Transport;
  private callbacks: TaskStreamCallbacks;
  private current: Subscription | null = null;
  private displayed: AgentTask | null = null;
  private settledRevisions = new Map<string, string>();
  private retryDelays: number[];

  constructor(
    callbacks: TaskStreamCallbacks,
    transport: Transport = sopApi,
    retryDelays = [1000, 2000, 4000, 8000, 15000],
  ) {
    this.callbacks = callbacks;
    this.transport = transport;
    this.retryDelays = retryDelays;
  }

  private stop() {
    const subscription = this.current;
    this.current = null;
    if (!subscription) return;
    subscription.controller.abort();
    if (subscription.retryTimer) clearTimeout(subscription.retryTimer);
    subscription.first?.reject(aborted());
    subscription.first = undefined;
  }

  disconnect() {
    // Cancel the browser subscription only. The service continues the task.
    this.stop();
  }

  select(id: string | null) {
    this.stop();
    const initial = id && this.displayed?.id === id ? this.displayed : null;
    this.displayed = initial;
    this.callbacks.onSelection(id, initial);
    this.callbacks.onIssue("", false);
    this.callbacks.onLoading(id !== null && !initial);
    if (id) this.watch(id, initial);
  }

  reconnect(id: string | null) {
    if (!id) return;
    this.stop();
    this.callbacks.onIssue("正在重新连接任务…", true);
    this.callbacks.onLoading(this.displayed?.id !== id);
    this.watch(id, this.displayed?.id === id ? this.displayed : null);
  }

  create(input: CreateTaskInput): Promise<AgentTask> {
    return this.mutate(null, (listener, signal) => this.transport.create(input, listener, signal));
  }

  confirm(task: AgentTask): Promise<AgentTask> {
    return this.mutate(task, (listener, signal) => this.transport.confirm(task, listener, signal));
  }

  feedback(task: AgentTask, message: string): Promise<AgentTask> {
    return this.mutate(task, (listener, signal) => this.transport.feedback(task, message, listener, signal));
  }

  private mutate(initial: AgentTask | null, operation: Operation): Promise<AgentTask> {
    this.stop();
    // A click may still carry the previous React render's revision. Keep the
    // newer displayed snapshot, but send the original approval revision so
    // the service can reject an out-of-date decision instead of upgrading it.
    const visible = initial && this.displayed?.id === initial.id && this.displayed.revision > initial.revision
      ? this.displayed : initial;
    this.displayed = visible;
    this.callbacks.onSelection(visible?.id ?? null, visible);
    this.callbacks.onIssue("", false);
    this.callbacks.onLoading(visible === null);
    const subscription: Subscription = {
      controller: new AbortController(), taskId: visible?.id ?? null,
      revision: visible?.revision ?? -1, latest: visible, attempts: 0, received: false,
    };
    const first = new Promise<AgentTask>((resolve, reject) => {
      subscription.first = { resolve, reject };
    });
    this.current = subscription;
    void this.consume(subscription, operation, true);
    return first;
  }

  private watch(id: string, initial: AgentTask | null) {
    const subscription: Subscription = {
      controller: new AbortController(), taskId: id,
      revision: initial?.revision ?? -1, latest: initial, attempts: 0, received: false,
    };
    this.current = subscription;
    void this.consume(subscription, (listener, signal) => this.transport.events(id, listener, signal), false);
  }

  private accept(subscription: Subscription, event: TaskStreamEvent) {
    if (this.current !== subscription || subscription.controller.signal.aborted) return;
    const next = event.task;
    if (subscription.taskId && subscription.taskId !== next.id) return;
    if (next.revision < subscription.revision) return;
    const changed = !subscription.latest || next.revision > subscription.revision;
    subscription.taskId = next.id;
    subscription.revision = next.revision;
    subscription.latest = changed ? next : subscription.latest;
    subscription.received = true;
    if (changed) subscription.attempts = 0;
    this.callbacks.onIssue("", false);
    this.callbacks.onLoading(false);
    if (this.displayed?.id !== next.id) {
      this.callbacks.onSelection(next.id, next);
    }
    if (changed || this.displayed?.id !== next.id) {
      this.displayed = next;
      this.callbacks.onTask(next);
    }
    subscription.first?.resolve(subscription.latest ?? next);
    subscription.first = undefined;
    if (isTaskStopEvent(event.event)) this.settle(subscription);
  }

  private settle(subscription: Subscription) {
    if (this.current !== subscription || !subscription.latest) return;
    const task = subscription.latest;
    this.current = null;
    subscription.controller.abort();
    if (subscription.retryTimer) clearTimeout(subscription.retryTimer);
    this.callbacks.onLoading(false);
    this.callbacks.onIssue("", false);
    const revision = `${task.revision}:${task.status}`;
    if (this.settledRevisions.get(task.id) !== revision) {
      this.settledRevisions.set(task.id, revision);
      if (this.settledRevisions.size > 200) {
        const oldest = this.settledRevisions.keys().next().value;
        if (oldest) this.settledRevisions.delete(oldest);
      }
      this.callbacks.onSettled(task);
    }
  }

  private async consume(subscription: Subscription, operation: Operation, mutation: boolean) {
    const controller = subscription.controller;
    subscription.received = false;
    const ownsRequest = () => this.current === subscription && subscription.controller === controller && !controller.signal.aborted;
    try {
      await operation((event) => {
        if (ownsRequest()) this.accept(subscription, event);
      }, controller.signal);
      if (!ownsRequest()) return;
      // A terminal snapshot is sufficient even if its final marker was lost.
      if (subscription.received && subscription.latest && !isTaskActive(subscription.latest.status)) {
        this.settle(subscription);
        return;
      }
      throw new SopApiError("SOP 实时连接意外结束。", 0);
    } catch (cause) {
      if (!ownsRequest()) return;
      if (subscription.received && subscription.latest && !isTaskActive(subscription.latest.status) && !mutation) {
        this.settle(subscription);
        return;
      }
      const error = cause instanceof Error ? cause : new Error("SOP 实时连接中断。");
      const rejected = error instanceof SopApiError && error.status >= 400 && error.status < 500 && ![408, 429].includes(error.status);
      if (rejected) {
        subscription.first?.reject(error);
        subscription.first = undefined;
        this.current = null;
        subscription.controller.abort();
        this.callbacks.onLoading(false);
        if (mutation && subscription.taskId) {
          // Refresh after a stale/invalid mutation without submitting it again.
          this.watch(subscription.taskId, subscription.latest);
        } else if (!mutation) this.callbacks.onIssue(error.message, false);
        return;
      }
      if (!subscription.taskId) {
        const uncertain = new Error("尚未收到任务编号，提交结果不确定。已刷新任务列表，请先查找已创建的任务，避免重复提交。");
        subscription.first?.reject(uncertain);
        subscription.first = undefined;
        this.current = null;
        subscription.controller.abort();
        this.callbacks.onLoading(false);
        this.callbacks.onIssue(uncertain.message, false);
        this.callbacks.onUncertain();
        return;
      }
      // POST is never repeated. Once the task ID is known, only the read-only
      // events endpoint can recover state after a lost request/stream response.
      subscription.first?.reject(new SopTaskRecoveryError("实时连接中断，正在恢复任务状态；本次操作不会自动重复提交。"));
      subscription.first = undefined;
      if (subscription.attempts >= this.retryDelays.length) {
        this.current = null;
        this.callbacks.onLoading(false);
        this.callbacks.onIssue("实时连接未能恢复。请点击“重新连接任务”继续查看，后台任务不会因此取消。", false);
        return;
      }
      const delay = this.retryDelays[subscription.attempts++];
      this.callbacks.onIssue("实时连接中断，正在恢复任务状态…", true);
      subscription.controller.abort();
      subscription.retryTimer = setTimeout(() => {
        if (this.current !== subscription) return;
        subscription.controller = new AbortController();
        void this.consume(subscription, (listener, signal) => this.transport.events(subscription.taskId!, listener, signal), false);
      }, delay);
    }
  }
}
