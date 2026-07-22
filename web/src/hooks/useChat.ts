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

export function useChat({
  onThinkingStart,
  onThinkingEnd,
  onPersistMessages,
  activeSessionIdRef,
}: UseChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);

  // Keep messages in a ref so stream callbacks can always read the latest state
  const messagesRef = useRef<ChatMessage[]>([]);
  messagesRef.current = messages;

  // Store callbacks in refs to avoid stale closures in stream callbacks
  const onThinkingStartRef = useRef(onThinkingStart);
  onThinkingStartRef.current = onThinkingStart;
  const onThinkingEndRef = useRef(onThinkingEnd);
  onThinkingEndRef.current = onThinkingEnd;
  const onPersistMessagesRef = useRef(onPersistMessages);
  onPersistMessagesRef.current = onPersistMessages;

  // Track which session triggered the current stream
  const thinkingSessionIdRef = useRef<string | null>(null);
  // Track the full message list for the thinking session (survives session switches)
  const thinkingMessagesRef = useRef<ChatMessage[]>([]);

  const sendMessage = useCallback(async (content: string, sessionId?: string) => {
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

    // Build the full message list for the thinking session from the current messages
    const currentMessages = messagesRef.current;
    const fullMessages = [...currentMessages, userMsg, agentMsg];
    thinkingMessagesRef.current = fullMessages;

    setMessages(prev => [...prev, userMsg, agentMsg]);
    setLoading(true);

    // Track which session is thinking
    const sid = sessionId || activeSessionIdRef.current;
    thinkingSessionIdRef.current = sid;
    if (sid) {
      onThinkingStartRef.current?.(sid);
      // Persist initial messages so the session has the user message immediately
      onPersistMessagesRef.current?.(sid, fullMessages);
    }

    let accumulated = '';

    await sendChatStream(content, {
      onChunk: (chunk) => {
        accumulated += chunk;
        // Update the thinking session's messages (always, even if session switched)
        thinkingMessagesRef.current = thinkingMessagesRef.current.map(m =>
          m.id === agentMsgId ? { ...m, content: accumulated, loading: false } : m,
        );
        if (thinkingSessionIdRef.current) {
          onPersistMessagesRef.current?.(thinkingSessionIdRef.current, thinkingMessagesRef.current);
        }
        // Also update the UI state (no-op if session switched since agentMsgId won't exist)
        setMessages(prev =>
          prev.map(m =>
            m.id === agentMsgId ? { ...m, content: accumulated, loading: false } : m,
          ),
        );
      },
      onStep: (step: ThinkingStep) => {
        // Update the thinking session's messages (always, even if session switched)
        thinkingMessagesRef.current = thinkingMessagesRef.current.map(m =>
          m.id === agentMsgId ? { ...m, steps: [...m.steps, step] } : m,
        );
        if (thinkingSessionIdRef.current) {
          onPersistMessagesRef.current?.(thinkingSessionIdRef.current, thinkingMessagesRef.current);
        }
        // Also update the UI state
        setMessages(prev =>
          prev.map(m =>
            m.id === agentMsgId ? { ...m, steps: [...m.steps, step] } : m,
          ),
        );
      },
      onDone: () => {
        // Only clear loading if the thinking session is still the active one
        if (thinkingSessionIdRef.current === activeSessionIdRef.current) {
          setLoading(false);
        }
        // Final update to thinking messages
        thinkingMessagesRef.current = thinkingMessagesRef.current.map(m =>
          m.id === agentMsgId ? { ...m, loading: false } : m,
        );
        if (thinkingSessionIdRef.current) {
          onPersistMessagesRef.current?.(thinkingSessionIdRef.current, thinkingMessagesRef.current);
          onThinkingEndRef.current?.(thinkingSessionIdRef.current, 'done');
          thinkingSessionIdRef.current = null;
        }
        setMessages(prev =>
          prev.map(m =>
            m.id === agentMsgId ? { ...m, loading: false } : m,
          ),
        );
      },
      onError: (err) => {
        // Only clear loading if the thinking session is still the active one
        if (thinkingSessionIdRef.current === activeSessionIdRef.current) {
          setLoading(false);
        }
        // Final update to thinking messages with error
        thinkingMessagesRef.current = thinkingMessagesRef.current.map(m =>
          m.id === agentMsgId
            ? { ...m, content: `Error: ${err}`, loading: false }
            : m,
        );
        if (thinkingSessionIdRef.current) {
          onPersistMessagesRef.current?.(thinkingSessionIdRef.current, thinkingMessagesRef.current);
          onThinkingEndRef.current?.(thinkingSessionIdRef.current, 'error');
          thinkingSessionIdRef.current = null;
        }
        setMessages(prev =>
          prev.map(m =>
            m.id === agentMsgId
              ? { ...m, content: `Error: ${err}`, loading: false }
              : m,
          ),
        );
      },
    });
  }, [activeSessionIdRef]);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  const loadMessages = useCallback((msgs: ChatMessage[]) => {
    setMessages(msgs);
  }, []);

  return { messages, loading, sendMessage, clearMessages, loadMessages, setMessages, setLoading };
}