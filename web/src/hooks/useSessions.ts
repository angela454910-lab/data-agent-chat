import { useState, useCallback, useEffect, useRef } from 'react';
import type { Session, ChatMessage } from '../types';

const STORAGE_KEY = 'data-agent-sessions';

function loadSessions(): Session[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    // ignore
  }
  return [];
}

function saveSessions(sessions: Session[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
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

export function useSessions() {
  const [sessions, setSessions] = useState<Session[]>(loadSessions);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(() => {
    const loaded = loadSessions();
    return loaded.length > 0 ? loaded[0].id : null;
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
          createdAt: Date.now(),
          updatedAt: Date.now(),
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
      createdAt: Date.now(),
      updatedAt: Date.now(),
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
      // Switch to the most recent remaining session, or create one
      const remaining = sessions.filter(s => s.id !== id);
      if (remaining.length > 0) {
        return remaining.sort((a, b) => b.updatedAt - a.updatedAt)[0].id;
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
      prev.map(s =>
        s.id === id
          ? {
              ...s,
              messages,
              title: deriveTitle(messages),
              updatedAt: Date.now(),
            }
          : s,
      ),
    );
  }, []);

  // If activeSessionId is null (all deleted), create a new one
  useEffect(() => {
    if (activeSessionId === null && initialized.current) {
      const newSession: Session = {
        id: generateId(),
        title: '新对话',
        messages: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
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
