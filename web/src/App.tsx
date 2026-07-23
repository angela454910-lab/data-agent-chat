import { useState, useEffect, useRef } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatPanel } from './components/ChatPanel';
import { InsightPanel } from './components/InsightPanel';
import { useChat } from './hooks/useChat';
import { useSessions } from './hooks/useSessions';
import { fetchSession } from './lib/api';
import type { Session } from './types';
import { PanelRightOpen, PanelRightClose } from 'lucide-react';

const SESSION_PATH_PREFIX = '/session-';

function getSessionFromURL(): string | null {
  const path = window.location.pathname;
  if (path.startsWith(SESSION_PATH_PREFIX)) {
    const id = path.slice(1);
    return id || null;
  }
  return null;
}

function updateURLSession(sessionId: string | null) {
  const url = new URL(window.location.href);
  if (sessionId) {
    url.pathname = `/${sessionId}`;
  } else {
    url.pathname = '/';
  }
  url.search = '';
  window.history.replaceState(null, '', url.toString());
}

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [insightOpen, setInsightOpen] = useState(false);

  const urlSessionId = getSessionFromURL();

  const {
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
  } = useSessions(urlSessionId);

  const activeSessionIdRef = useRef<string | null>(activeSessionId);
  activeSessionIdRef.current = activeSessionId;

  const prevSessionIdRef = useRef<string | null>(null);

  // Local session mirror — updated after stream for immediate metadata display
  const [localSession, setLocalSession] = useState<Session | null>(null);

  const {
    messages,
    loading,
    sendMessage,
    clearMessages,
    loadMessages,
    setLoading,
  } = useChat({
    activeSessionIdRef,
    onThinkingStart: (sessionId: string) => {
      updateSessionStatus(sessionId, 'thinking');
    },
    onThinkingEnd: (sessionId: string, status: 'done' | 'error') => {
      updateSessionStatus(sessionId, status);
    },
    onStreamComplete: async (sessionId: string) => {
      // Refresh session list for sidebar (title, status)
      refreshSessions();
      // Fetch updated session to get metadata (tables)
      try {
        const s = await fetchSession(sessionId);
        setLocalSession(s);
      } catch {
        // ignore
      }
      // Optimistically update title
      const lastUser = [...messages].reverse().find(m => m.role === 'user');
      if (lastUser) {
        const text = lastUser.content.trim();
        const title = text.length > 20 ? text.slice(0, 20) + '...' : text;
        updateSessionTitle(sessionId, title);
      }
    },
  });

  // Load messages when switching sessions
  useEffect(() => {
    if (activeSession && activeSessionId !== prevSessionIdRef.current) {
      prevSessionIdRef.current = activeSessionId;
      loadMessages(activeSession.messages);
      setLocalSession(activeSession);
      if (activeSession.status === 'thinking') {
        setLoading(true);
      } else {
        setLoading(false);
      }
      if (activeSession.status === 'done' || activeSession.status === 'error') {
        clearSessionStatus(activeSession.id);
      }
    } else if (!activeSession && activeSessionId !== prevSessionIdRef.current) {
      prevSessionIdRef.current = activeSessionId;
      clearMessages();
      setLocalSession(null);
    }
  }, [activeSessionId, activeSession, loadMessages, clearMessages, setLoading, clearSessionStatus]);

  // Sync activeSessionId to URL
  useEffect(() => {
    updateURLSession(activeSessionId);
  }, [activeSessionId]);

  // Listen for browser back/forward
  useEffect(() => {
    const onPopState = () => {
      const id = getSessionFromURL();
      if (id && id !== activeSessionId) {
        switchSession(id);
      } else if (!id && activeSessionId) {
        clearMessages();
      }
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, [activeSessionId, switchSession, clearMessages]);

  const sessionStatus =
    activeSession?.status === 'done' || activeSession?.status === 'error'
      ? activeSession.status
      : undefined;

  const handleNewSession = () => {
    clearActiveSession();
    clearMessages();
    setLocalSession(null);
    setSidebarOpen(false);
  };

  const handleSendMessage = (message: string) => {
    if (!activeSessionId) {
      const newId = createSession();
      setTimeout(() => {
        sendMessage(message, newId);
      }, 0);
    } else {
      sendMessage(message, activeSessionId);
    }
  };

  const handleDeleteSession = (id: string) => {
    deleteSession(id);
  };

  const handleSwitchSession = (id: string) => {
    switchSession(id);
    setSidebarOpen(false);
  };

  // Use localSession (updated after stream) or activeSession (loaded on switch)
  const insightSession = localSession || activeSession;

  return (
    <div className="flex h-screen overflow-hidden bg-white">
      {/* Desktop Sidebar */}
      <div className="hidden md:flex flex-shrink-0 h-full overflow-hidden">
        <Sidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onNewSession={handleNewSession}
          onDeleteSession={handleDeleteSession}
          onSwitchSession={handleSwitchSession}
        />
      </div>

      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="relative z-10 w-72 h-full shadow-xl">
            <Sidebar
              sessions={sessions}
              activeSessionId={activeSessionId}
              onNewSession={handleNewSession}
              onDeleteSession={handleDeleteSession}
              onSwitchSession={handleSwitchSession}
            />
          </div>
        </div>
      )}

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        <ChatPanel
          messages={messages}
          loading={loading}
          onSend={handleSendMessage}
          onMenuClick={() => setSidebarOpen(true)}
          sessionStatus={sessionStatus}
        />
      </main>

      {/* Insight Panel Toggle Button */}
      <div className="hidden md:flex items-center">
        <button
          onClick={() => setInsightOpen(!insightOpen)}
          className="flex-shrink-0 flex items-center justify-center w-6 h-20 rounded-l-lg bg-slate-100 hover:bg-slate-200 border border-r-0 border-slate-200 text-slate-500 hover:text-slate-700 transition-colors"
          title={insightOpen ? 'Close panel' : 'Open panel'}
        >
          {insightOpen ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}
        </button>
      </div>

      {/* Desktop Insight Panel */}
      {insightOpen && (
        <div className="hidden md:flex flex-shrink-0 h-full overflow-hidden insight-panel-enter">
          <InsightPanel
            session={insightSession}
            messages={messages}
            isOpen={insightOpen}
            onToggle={() => setInsightOpen(false)}
          />
        </div>
      )}
    </div>
  );
}

export default App;
