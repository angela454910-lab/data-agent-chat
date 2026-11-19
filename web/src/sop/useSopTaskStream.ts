import { useEffect, useRef, useState } from "react";
import { SopTaskStreamController } from "./sop-task-stream";
import type { AgentTask } from "./sop-api";

interface Options {
  onTask: (task: AgentTask) => void;
  onSettled: (task: AgentTask) => void;
  onUncertain: () => void;
}

export function useSopTaskStream(options: Options) {
  const [activeId, setActiveId] = useState<string | null>(() =>
    new URLSearchParams(window.location.search).get("task"),
  );
  const [task, setTask] = useState<AgentTask | null>(null);
  const [taskLoading, setTaskLoading] = useState(false);
  const [connectionIssue, setConnectionIssue] = useState("");
  const [reconnecting, setReconnecting] = useState(false);
  const callbacksRef = useRef(options);
  callbacksRef.current = options;
  const controllerRef = useRef<SopTaskStreamController | null>(null);
  if (!controllerRef.current) {
    controllerRef.current = new SopTaskStreamController({
      onSelection: (id, initial) => { setActiveId(id); setTask(initial); },
      onTask: (next) => { setTask(next); callbacksRef.current.onTask(next); },
      onLoading: setTaskLoading,
      onIssue: (message, retrying) => { setConnectionIssue(message); setReconnecting(retrying); },
      onSettled: (next) => callbacksRef.current.onSettled(next),
      onUncertain: () => callbacksRef.current.onUncertain(),
    });
  }
  const stream = controllerRef.current;

  useEffect(() => {
    stream.select(new URLSearchParams(window.location.search).get("task"));
    const onPopState = () => stream.select(new URLSearchParams(window.location.search).get("task"));
    window.addEventListener("popstate", onPopState);
    return () => { window.removeEventListener("popstate", onPopState); stream.disconnect(); };
  }, [stream]);

  useEffect(() => {
    const url = new URL(window.location.href);
    if (activeId) url.searchParams.set("task", activeId);
    else url.searchParams.delete("task");
    window.history.replaceState(null, "", url);
  }, [activeId]);

  return { activeId, task, taskLoading, connectionIssue, reconnecting, stream };
}
