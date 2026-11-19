import { lazy, Suspense, useState, useEffect, useRef } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatPanel } from './components/ChatPanel';
import { InsightPanel } from './components/InsightPanel';
import { useChat } from './hooks/useChat';
import { useSessions } from './hooks/useSessions';
import { useMemories } from './hooks/useMemories';
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

function ChatApp() {
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
   updateSessionTitle,
  refreshSessions,
  markRead,
  markUnread,
} = useSessions(urlSessionId);

  const { memories, refresh: refreshMemories, remove: deleteMemory } = useMemories();

 const activeSessionIdRef = useRef<string | null>(activeSessionId);
 activeSessionIdRef.current = activeSessionId;

 // Local session mirror — updated after stream for immediate metadata display
 const [localSession, setLocalSession] = useState<Session | null>(null);

 const {
   messages,
   loading,
   sendMessage,
   clearMessages,
   loadMessages,
   setLoading,
    isStreaming,
    restoreStream,
    abortStream,
 } = useChat({
   activeSessionIdRef,
   onThinkingStart: (sessionId: string) => {
     updateSessionStatus(sessionId, 'thinking');
   },
  onThinkingEnd: (sessionId: string, status: 'done' | 'error') => {
    updateSessionStatus(sessionId, status);
    // A completed turn that the user is NOT currently viewing gets an unread
    // dot (ephemeral, client-only). If they're looking at it, it's "read"
    // immediately and onStreamComplete also clears the flag for safety.
    if (status === 'done' && sessionId !== activeSessionIdRef.current) {
      markUnread(sessionId);
    }
  },
   onStreamComplete: async (sessionId: string) => {
     // Refresh session list for sidebar (title, status)
     refreshSessions();
     // Memory extraction runs as a background task after the answer lands;
     // give it a moment then refresh the panel so new memories surface.
     setTimeout(() => { refreshMemories(); }, 3000);
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
      // If the completed turn is the one currently in view, mark it read so
      // the green "unread" dot doesn't linger on the session you're looking at.
      if (sessionId === activeSessionIdRef.current) {
        markRead(sessionId);
      }
   },
 });

 // Load messages when the active session object changes (real switch or clear).
 // Keying on activeSession identity avoids a race where activeSessionId has
 // flipped but activeSession still holds the previous (stale) session object.
 useEffect(() => {
    if (activeSession) {
      // If a turn is still streaming for this session in the background,
      // restore its live in-progress messages instead of the stale backend
      // snapshot (which has no partial answer yet). Otherwise loading the
      // persisted messages would overwrite what's still arriving.
      if (isStreaming(activeSession.id)) {
        setLocalSession(activeSession);
        return;
      }
     loadMessages(activeSession.messages ?? []);
     setLocalSession(activeSession);
     setLoading(activeSession.status === 'thinking');
      // Viewing a session clears its ephemeral unread dot (if any). Safe to
     // call unconditionally -- markRead is a no-op when the id isn't flagged.
    markRead(activeSession.id);
  } else {
    clearMessages();
    setLocalSession(null);
  }
}, [activeSession, loadMessages, clearMessages, setLoading, isStreaming, markRead]);

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
   // Disconnect any in-flight turn so it doesn't keep streaming into a
   // deleted session (and avoid a dangling background fetch).
   abortStream(id);
   deleteSession(id);
 };

const handleSwitchSession = (id: string) => {
  switchSession(id);
  // Give the switch instant visual feedback. If the target is streaming in
  // the background, restore its live messages; otherwise blank the view and
  // show a loader until the full session loads, so the chat never lingers on
  // the previous session's content while its data is still being fetched.
  if (!restoreStream(id)) {
    clearMessages();
    setLoading(true);
  }
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
            memories={memories}
            onDeleteMemory={deleteMemory}
          />
        </div>
      )}
    </div>
  );
}

const SopWorkspace = lazy(() => import('./sop/SopWorkspace'));

function App() {
  // Mount the legacy chat only on its own routes: its URL/session effects
  // must not rewrite /sop or start chat requests in the SOP workspace.
  if (window.location.pathname === '/sop' || window.location.pathname.startsWith('/sop/')) {
    return (
      <Suspense fallback={<div className="flex min-h-screen items-center justify-center text-sm text-slate-500" role="status">正在打开 SOP Agent…</div>}>
        <SopWorkspace />
      </Suspense>
    );
  }
  return <ChatApp />;
}

export default App;
