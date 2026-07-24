import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import type { Session, SessionSummary } from '../types';
import { fetchSessions, fetchSession, deleteSessionApi } from '../lib/api';

function generateId() {
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function useSessions(initialSessionId?: string | null) {
  // rawSessions: backend list (refresh-safe). unreadIds: ephemeral, client-only
  // set of completed sessions whose result the user hasn't viewed yet. It is
  // deliberately NOT persisted -- a refresh or another device starts clean.
  const [rawSessions, setRawSessions] = useState<SessionSummary[]>([]);
  const [unreadIds, setUnreadIds] = useState<Set<string>>(() => new Set());
  // Derived list overlays the ephemeral unread flag without storing it in the
  // backend-backed list, so refreshSessions() can never wipe a live unread dot.
  const sessions = useMemo(
    () => rawSessions.map(s => ({ ...s, unread: unreadIds.has(s.id) })),
    [rawSessions, unreadIds],
  );
  const [activeSessionId, setActiveSessionId] = useState<string | null>(initialSessionId ?? null);
  const [activeSession, setActiveSession] = useState<Session | null>(null);
  const initialized = useRef(false);

  // Load session list on mount
  const refreshSessions = useCallback(async () => {
    try {
      const list = await fetchSessions();
      setRawSessions(list);
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
    setRawSessions(prev => [
      { id, title: '新对话', status: 'thinking', updated_at: now, created_at: now, message_count: 0 },
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
    setRawSessions(prev => prev.filter(s => s.id !== id));
    setUnreadIds(prev => {
      if (!prev.has(id)) return prev;
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
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
    setRawSessions(prev => prev.map(s => (s.id === id ? { ...s, status } : s)));
  }, []);

  const clearSessionStatus = useCallback((id: string) => {
    setRawSessions(prev => prev.map(s => (s.id === id ? { ...s, status: undefined } : s)));
  }, []);

 // Update title optimistically after stream (backend will have the real title on next refresh)
const updateSessionTitle = useCallback((id: string, title: string) => {
   setRawSessions(prev => prev.map(s => (s.id === id ? { ...s, title } : s)));
}, []);

  // Mark a completed session's result as viewed: clear its ephemeral unread
  // dot. Client-only -- intentionally no backend call, so the state resets on
  // refresh or from another device (the desired "don't persist" behavior).
  const markRead = useCallback((id: string) => {
    setUnreadIds(prev => {
      if (!prev.has(id)) return prev;
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }, []);

  // Flag a completed session as unread (green dot). Called when a turn
  // finishes while the user is NOT looking at that session.
  const markUnread = useCallback((id: string) => {
    setUnreadIds(prev => {
      if (prev.has(id)) return prev;
      const next = new Set(prev);
      next.add(id);
      return next;
    });
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
   markRead,
   markUnread,
};
}
