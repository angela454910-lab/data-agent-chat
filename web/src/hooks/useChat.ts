import { useState, useCallback } from 'react';
import type { ChatMessage, ThinkingStep } from '../types';
import { sendChatStream } from '../lib/api';

let idCounter = 0;
function nextId() {
  return `msg-${Date.now()}-${++idCounter}`;
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [lastRoutedTo, setLastRoutedTo] = useState<string>('');

  const sendMessage = useCallback(async (content: string) => {
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

    setMessages(prev => [...prev, userMsg, agentMsg]);
    setLoading(true);

    let accumulated = '';

    await sendChatStream(content, {
      onChunk: (chunk) => {
        accumulated += chunk;
        setMessages(prev =>
          prev.map(m =>
            m.id === agentMsgId ? { ...m, content: accumulated, loading: false } : m,
          ),
        );
      },
      onMetadata: (routedTo) => {
        setLastRoutedTo(routedTo);
        setMessages(prev =>
          prev.map(m =>
            m.id === agentMsgId ? { ...m, routedTo } : m,
          ),
        );
      },
      onStep: (step: ThinkingStep) => {
        setMessages(prev =>
          prev.map(m =>
            m.id === agentMsgId ? { ...m, steps: [...m.steps, step] } : m,
          ),
        );
      },
      onDone: () => {
        setLoading(false);
        setMessages(prev =>
          prev.map(m =>
            m.id === agentMsgId ? { ...m, loading: false } : m,
          ),
        );
      },
      onError: (err) => {
        setMessages(prev =>
          prev.map(m =>
            m.id === agentMsgId
              ? { ...m, content: `Error: ${err}`, loading: false }
              : m,
          ),
        );
        setLoading(false);
      },
    });
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setLastRoutedTo('');
  }, []);

  const loadMessages = useCallback((msgs: ChatMessage[]) => {
    setMessages(msgs);
    setLastRoutedTo('');
  }, []);

  return { messages, loading, lastRoutedTo, sendMessage, clearMessages, loadMessages, setMessages };
}
