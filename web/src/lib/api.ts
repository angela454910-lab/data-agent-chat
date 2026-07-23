import type { SchemaTable, HealthResponse, ThinkingStep, Session, SessionSummary } from '../types';

const BASE = '';

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${BASE}/api/health`);
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}

export async function fetchSchema(): Promise<SchemaTable[]> {
  const res = await fetch(`${BASE}/api/schema`);
  if (!res.ok) throw new Error('Failed to fetch schema');
  const data = await res.json();
  return data.tables;
}

export async function fetchSessions(): Promise<SessionSummary[]> {
  const res = await fetch(`${BASE}/api/sessions`);
  if (!res.ok) throw new Error('Failed to fetch sessions');
  const data = await res.json();
  return data.sessions;
}

export async function fetchSession(id: string): Promise<Session> {
  const res = await fetch(`${BASE}/api/sessions/${id}`);
  if (!res.ok) throw new Error('Failed to fetch session');
  return res.json();
}

export async function deleteSessionApi(id: string): Promise<void> {
  const res = await fetch(`${BASE}/api/sessions/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete session');
}

export interface StreamCallbacks {
  onChunk: (text: string) => void;
  onStep: (step: ThinkingStep) => void;
  onDone: () => void;
  onError: (err: string) => void;
}

let stepCounter = 0;

export async function sendChatStream(
  message: string,
  sessionId: string,
  callbacks: StreamCallbacks,
): Promise<void> {
  const res = await fetch(`${BASE}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  if (!res.ok) {
    callbacks.onError(`HTTP ${res.status}`);
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) {
    callbacks.onError('No response body');
    return;
  }

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const payload = line.slice(6).trim();
      if (payload === '[DONE]') {
        callbacks.onDone();
        return;
      }
      try {
        const data = JSON.parse(payload);

        if (data.type === 'answer' || data.type === 'sub_answer') {
          callbacks.onChunk(data.content);
        } else if (data.type === 'tool_call') {
          callbacks.onStep({
            id: `step-${++stepCounter}`,
            type: 'tool_call',
            label: `调用工具: ${data.tool}`,
            detail: data.input,
            timestamp: Date.now(),
          });
        } else if (data.type === 'tool_result') {
          callbacks.onStep({
            id: `step-${++stepCounter}`,
            type: 'tool_result',
            label: `${data.tool} 返回结果`,
            detail: data.output,
            timestamp: Date.now(),
          });
        } else if (data.type === 'error') {
          callbacks.onError(data.content);
        }
      } catch {
        // skip malformed JSON
      }
    }
  }
  callbacks.onDone();
}
