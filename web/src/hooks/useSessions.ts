import { useState, useCallback, useEffect, useRef } from 'react';
import type { Session, ChatMessage } from '../types';

const STORAGE_KEY = 'data-agent-sessions';

function loadSessions(): Session[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const sessions: Session[] = JSON.parse(raw);
      // Only restore sessions that have messages
      return sessions.filter(s => s.messages.length > 0);
    }
  } catch {
    // ignore
  }
  return [];
}

function saveSessions(sessions: Session[]) {
  // Only persist sessions that have messages
  const nonEmpty = sessions.filter(s => s.messages.length > 0);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(nonEmpty));
}

function generateId() {
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function deriveTitle(messages: ChatMessage[]): string {
  const firstUser = messages.find(m => m.role === 'user');
  if (!firstUser) return '新对话';
  const text = firstUser.content.trim();
  return text.length > 20 ? text.slice(0, 20) + '...' : text;
}

export function useSessions(initialSessionId?: string | null) {
  const [sessions, setSessions] = useState<Session[]>(loadSessions);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(() => {
    const loaded = loadSessions();
    if (loaded.length === 0) return null;
    if (initialSessionId && loaded.some(s => s.id === initialSessionId)) {
      return initialSessionId;
    }
    return loaded[0].id;
  });
  const initialized = useRef(false);

  // Mark as initialized after first render
  useEffect(() => {
    initialized.current = true;
  }, []);

  // Persist to localStorage
  useEffect(() => {
    if (initialized.current) {
      saveSessions(sessions);
    }
  }, [sessions]);

  const activeSession = sessions.find(s => s.id === activeSessionId) || null;

  const createSession = useCallback(() => {
    const newSession: Session = {
      id: generateId(),
      title: '新对话',
      messages: [],
    };
    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
    return newSession.id;
  }, []);

  const deleteSession = useCallback((id: string) => {
    setSessions(prev => prev.filter(s => s.id !== id));
    setActiveSessionId(prev => {
      if (prev !== id) return prev;
      // Switch to first remaining, or null (no auto-create)
      return null;
    });
  }, []);

  const switchSession = useCallback((id: string) => {
    setActiveSessionId(id);
  }, []);

  const updateSessionMessages = useCallback((id: string, messages: ChatMessage[]) => {
    setSessions(prev =>
      prev.map(s => {
        if (s.id !== id) return s;
        if (s.messages === messages) return s;
        return {
          ...s,
          messages,
          title: deriveTitle(messages),
        };
      }),
    );
  }, []);

  return {
    sessions,
    activeSession,
    activeSessionId,
    createSession,
    deleteSession,
    switchSession,
    updateSessionMessages,
  };
}
