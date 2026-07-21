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
    // If a specific session id is provided (e.g. from URL), restore it
    if (initialSessionId && loaded.some(s => s.id === initialSessionId)) {
      return initialSessionId;
    }
    return loaded[0].id;
  });
  const initialized = useRef(false);

  // Create initial session if none exist
  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true;
      if (sessions.length === 0) {
        const newSession: Session = {
          id: generateId(),
          title: '新对话',
          messages: [],
        };
        setSessions([newSession]);
        setActiveSessionId(newSession.id);
      }
    }
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
    setSessions(prev => {
      const next = prev.filter(s => s.id !== id);
      return next;
    });
    setActiveSessionId(prev => {
      if (prev !== id) return prev;
      // Switch to the first remaining session, or create one
      const remaining = sessions.filter(s => s.id !== id);
      if (remaining.length > 0) {
        return remaining[0].id;
      }
      // Will trigger creation in effect
      return null;
    });
  }, [sessions]);

  const switchSession = useCallback((id: string) => {
    setActiveSessionId(id);
  }, []);

  const updateSessionMessages = useCallback((id: string, messages: ChatMessage[]) => {
    setSessions(prev =>
      prev.map(s => {
        if (s.id !== id) return s;
        // Skip if messages are the same reference (e.g. loaded from session switch).
        if (s.messages === messages) return s;
        return {
          ...s,
          messages,
          title: deriveTitle(messages),
        };
      }),
    );
  }, []);

  // If activeSessionId is null (all deleted), create a new one
  useEffect(() => {
    if (activeSessionId === null && initialized.current) {
      const newSession: Session = {
        id: generateId(),
        title: '新对话',
        messages: [],
      };
      setSessions([newSession]);
      setActiveSessionId(newSession.id);
    }
  }, [activeSessionId]);

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
