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
  onPersistMessages?: (sessionId: string, messages: ChatMessage[]) => void;
  activeSessionIdRef: React.MutableRefObject<string | null>;
}

interface StreamState {
  agentMsgId: string;
  accumulated: string;
  messages: ChatMessage[];
}

export function useChat({
  onThinkingStart,
  onThinkingEnd,
  onPersistMessages,
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
  const onPersistMessagesRef = useRef(onPersistMessages);
  onPersistMessagesRef.current = onPersistMessages;

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

    activeStreamsRef.current.set(sid, {
      agentMsgId,
      accumulated: '',
      messages: fullMessages,
    });

    if (sid === activeSessionIdRef.current) {
      setMessages(fullMessages);
      setLoading(true);
    }

    onThinkingStartRef.current?.(sid);
    onPersistMessagesRef.current?.(sid, fullMessages);

    await sendChatStream(content, {
      onChunk: (chunk) => {
        const stream = activeStreamsRef.current.get(sid);
        if (!stream) return;
        stream.accumulated += chunk;
        stream.messages = stream.messages.map(m =>
          m.id === agentMsgId ? { ...m, content: stream.accumulated, loading: false } : m,
        );
        onPersistMessagesRef.current?.(sid, stream.messages);
        syncActiveSession(sid, stream.messages);
      },
      onStep: (step: ThinkingStep) => {
        const stream = activeStreamsRef.current.get(sid);
        if (!stream) return;
        stream.messages = stream.messages.map(m =>
          m.id === agentMsgId ? { ...m, steps: [...m.steps, step] } : m,
        );
        onPersistMessagesRef.current?.(sid, stream.messages);
        syncActiveSession(sid, stream.messages);
      },
      onDone: () => {
        const stream = activeStreamsRef.current.get(sid);
        if (stream) {
          stream.messages = stream.messages.map(m =>
            m.id === agentMsgId ? { ...m, loading: false } : m,
          );
          onPersistMessagesRef.current?.(sid, stream.messages);
          if (sid === activeSessionIdRef.current) {
            setMessages(stream.messages);
            setLoading(false);
          }
          activeStreamsRef.current.delete(sid);
        }
        onThinkingEndRef.current?.(sid, 'done');
      },
      onError: (err) => {
        const stream = activeStreamsRef.current.get(sid);
        if (stream) {
          stream.messages = stream.messages.map(m =>
            m.id === agentMsgId ? { ...m, content: `Error: ${err}`, loading: false } : m,
          );
          onPersistMessagesRef.current?.(sid, stream.messages);
          if (sid === activeSessionIdRef.current) {
            setMessages(stream.messages);
            setLoading(false);
          }
          activeStreamsRef.current.delete(sid);
        }
        onThinkingEndRef.current?.(sid, 'error');
      },
    });
  }, [activeSessionIdRef, syncActiveSession]);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  const loadMessages = useCallback((msgs: ChatMessage[]) => {
    setMessages(msgs);
  }, []);

  return { messages, loading, sendMessage, clearMessages, loadMessages, setMessages, setLoading };
}
