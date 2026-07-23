import { useState, useCallback, useEffect, useRef } from 'react';
import type { Session, SessionSummary } from '../types';
import { fetchSessions, fetchSession, deleteSessionApi } from '../lib/api';

function generateId() {
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function useSessions(initialSessionId?: string | null) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(initialSessionId ?? null);
  const [activeSession, setActiveSession] = useState<Session | null>(null);
  const initialized = useRef(false);

  // Load session list on mount
  const refreshSessions = useCallback(async () => {
    try {
      const list = await fetchSessions();
      setSessions(list);
    } catch (e) {
      console.error('Failed to load sessions:', e);
    }
  }, []);

  useEffect(() => {
    refreshSessions();
    initialized.current = true;
  }, [refreshSessions]);

  // Load full session when activeSessionId changes
  useEffect(() => {
    if (activeSessionId) {
      fetchSession(activeSessionId)
        .then(s => setActiveSession(s))
        .catch(e => {
          console.error('Failed to load session:', e);
          setActiveSession(null);
        });
    } else {
      setActiveSession(null);
    }
  }, [activeSessionId]);

  const createSession = useCallback(() => {
    const id = generateId();
    // Optimistic placeholder for sidebar; backend creates lazily on first message
    const now = new Date().toISOString();
    setSessions(prev => [
      { id, title: '新对话', status: undefined, updated_at: now, created_at: now, message_count: 0 },
      ...prev,
    ]);
    setActiveSessionId(id);
    // Don't set activeSession — no messages yet, backend doesn't have it
    setActiveSession(null);
    return id;
  }, []);

  const deleteSession = useCallback(async (id: string) => {
    try {
      await deleteSessionApi(id);
    } catch (e) {
      console.error('Failed to delete session:', e);
    }
    setSessions(prev => prev.filter(s => s.id !== id));
    setActiveSessionId(prev => (prev === id ? null : prev));
  }, []);

  const switchSession = useCallback((id: string) => {
    setActiveSessionId(id);
  }, []);

  const clearActiveSession = useCallback(() => {
    setActiveSessionId(null);
  }, []);

  // Local status tracking for sidebar dots (backend also persists, but this is for real-time UX)
  const updateSessionStatus = useCallback((id: string, status: 'thinking' | 'done' | 'error') => {
    setSessions(prev => prev.map(s => (s.id === id ? { ...s, status } : s)));
  }, []);

  const clearSessionStatus = useCallback((id: string) => {
    setSessions(prev => prev.map(s => (s.id === id ? { ...s, status: undefined } : s)));
  }, []);

  // Update title optimistically after stream (backend will have the real title on next refresh)
  const updateSessionTitle = useCallback((id: string, title: string) => {
    setSessions(prev => prev.map(s => (s.id === id ? { ...s, title } : s)));
  }, []);

  return {
    sessions,
    activeSession,
    activeSessionId,
    createSession,
    deleteSession,
    switchSession,
    clearActiveSession,
    updateSessionStatus,
    clearSessionStatus,
    updateSessionTitle,
    refreshSessions,
  };
}
