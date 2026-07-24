import { useState, useCallback, useRef } from 'react';
import type { ChatMessage, ThinkingStep } from '../types';
import { sendChatStream } from '../lib/api';

let idCounter = 0;
function nextId() {
  return `msg-${Date.now()}-${++idCounter}`;
}

interface UseChatOptions {
  onThinkingStart?: (sessionId: string) => void;
  onThinkingEnd?: (sessionId: string, status: 'done' | 'error') => void;
  onStreamComplete?: (sessionId: string) => void;
  activeSessionIdRef: React.MutableRefObject<string | null>;
}

interface StreamState {
  agentMsgId: string;
  accumulated: string;
  messages: ChatMessage[];
  controller: AbortController;
}

export function useChat({
  onThinkingStart,
  onThinkingEnd,
  onStreamComplete,
  activeSessionIdRef,
}: UseChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);

  const messagesRef = useRef<ChatMessage[]>([]);
  messagesRef.current = messages;

  const onThinkingStartRef = useRef(onThinkingStart);
  onThinkingStartRef.current = onThinkingStart;
  const onThinkingEndRef = useRef(onThinkingEnd);
  onThinkingEndRef.current = onThinkingEnd;
  const onStreamCompleteRef = useRef(onStreamComplete);
  onStreamCompleteRef.current = onStreamComplete;

  const activeStreamsRef = useRef<Map<string, StreamState>>(new Map());

  const syncActiveSession = useCallback(
    (sid: string, msgs: ChatMessage[]) => {
      if (sid === activeSessionIdRef.current) {
        setMessages(msgs);
      }
    },
    [activeSessionIdRef],
  );

  const sendMessage = useCallback(async (content: string, sessionId?: string) => {
    const sid = sessionId || activeSessionIdRef.current;
    if (!sid) return;

    const userMsg: ChatMessage = {
      id: nextId(),
      role: 'user',
      content,
      timestamp: Date.now(),
      steps: [],
    };

    const agentMsgId = nextId();
    const agentMsg: ChatMessage = {
      id: agentMsgId,
      role: 'agent',
      content: '',
      timestamp: Date.now(),
      loading: true,
      steps: [],
    };

    const existing = activeStreamsRef.current.get(sid);
    const baseMessages = existing
      ? existing.messages
      : sid === activeSessionIdRef.current
        ? messagesRef.current
        : [];
    const fullMessages = [...baseMessages, userMsg, agentMsg];

    const controller = new AbortController();
    activeStreamsRef.current.set(sid, {
      agentMsgId,
      accumulated: '',
      messages: fullMessages,
      controller,
    });

    if (sid === activeSessionIdRef.current) {
      setMessages(fullMessages);
      setLoading(true);
    }

    onThinkingStartRef.current?.(sid);

    await sendChatStream(content, sid, {
      onChunk: (chunk) => {
        const stream = activeStreamsRef.current.get(sid);
        if (!stream) return;
        stream.accumulated += chunk;
        stream.messages = stream.messages.map(m =>
          m.id === agentMsgId ? { ...m, content: stream.accumulated, loading: false } : m,
        );
        syncActiveSession(sid, stream.messages);
      },
      onStep: (step: ThinkingStep) => {
        const stream = activeStreamsRef.current.get(sid);
        if (!stream) return;
        stream.messages = stream.messages.map(m =>
          m.id === agentMsgId ? { ...m, steps: [...m.steps, step] } : m,
        );
        syncActiveSession(sid, stream.messages);
      },
      onDone: () => {
        const stream = activeStreamsRef.current.get(sid);
        if (stream) {
          stream.messages = stream.messages.map(m =>
            m.id === agentMsgId ? { ...m, loading: false } : m,
          );
          if (sid === activeSessionIdRef.current) {
            setMessages(stream.messages);
            setLoading(false);
          }
          activeStreamsRef.current.delete(sid);
        }
        onThinkingEndRef.current?.(sid, 'done');
        onStreamCompleteRef.current?.(sid);
      },
      onError: (err) => {
        const stream = activeStreamsRef.current.get(sid);
        if (stream) {
          stream.messages = stream.messages.map(m =>
            m.id === agentMsgId ? { ...m, content: `Error: ${err}`, loading: false } : m,
          );
          if (sid === activeSessionIdRef.current) {
            setMessages(stream.messages);
            setLoading(false);
          }
          activeStreamsRef.current.delete(sid);
        }
        onThinkingEndRef.current?.(sid, 'error');
      },
    }, controller.signal).catch((e: any) => {
      // Aborted (e.g. the session was deleted mid-flight): tear down silently
      // without surfacing an error to the user.
      if (e?.name === 'AbortError') {
        activeStreamsRef.current.delete(sid);
        return;
      }
      const stream = activeStreamsRef.current.get(sid);
      if (stream) {
        stream.messages = stream.messages.map(m =>
          m.id === agentMsgId ? { ...m, content: `Error: ${e?.message ?? 'network error'}`, loading: false } : m,
        );
        if (sid === activeSessionIdRef.current) {
          setMessages(stream.messages);
          setLoading(false);
        }
        activeStreamsRef.current.delete(sid);
      }
      onThinkingEndRef.current?.(sid, 'error');
    });
  }, [activeSessionIdRef, syncActiveSession]);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  const loadMessages = useCallback((msgs: ChatMessage[]) => {
    if (!Array.isArray(msgs)) return;
    setMessages(msgs);
  }, []);

  const isStreaming = useCallback(
    (sid: string) => activeStreamsRef.current.has(sid),
    [],
  );

  // When switching back to a session whose turn is still streaming in the
  // background, restore its live in-progress messages instead of showing the
  // stale backend snapshot (which has no partial answer yet).
  const restoreStream = useCallback((sid: string) => {
    const stream = activeStreamsRef.current.get(sid);
    if (!stream) return false;
    setMessages(stream.messages);
    setLoading(true);
    return true;
  }, []);

  // Disconnect an in-flight turn (used when its session is deleted). Aborts
  // the fetch and drops the in-memory stream state without surfacing an error.
  const abortStream = useCallback((sid: string) => {
    const stream = activeStreamsRef.current.get(sid);
    if (!stream) return;
    stream.controller.abort();
    activeStreamsRef.current.delete(sid);
    if (sid === activeSessionIdRef.current) {
      setLoading(false);
    }
  }, [activeSessionIdRef]);

  return { messages, loading, sendMessage, clearMessages, loadMessages, setMessages, setLoading, isStreaming, restoreStream, abortStream };
}
