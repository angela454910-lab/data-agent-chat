import { useState, useEffect, useRef } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatPanel } from './components/ChatPanel';
import { InsightPanel } from './components/InsightPanel';
import { useChat } from './hooks/useChat';
import { useSessions } from './hooks/useSessions';
import type { ThinkingStep } from './types';

const SESSION_PATH_PREFIX = '/session-';

function getSessionFromURL(): string | null {
  const path = window.location.pathname;
  // Match /session-{timestamp}-{random}
  if (path.startsWith(SESSION_PATH_PREFIX)) {
    const id = path.slice(1); // remove leading /
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
  // Clear any leftover query params from previous URL format
  url.search = '';
  window.history.replaceState(null, '', url.toString());
}

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { messages, loading, sendMessage, clearMessages, loadMessages } = useChat();

  // Read the initial session from the URL so refresh restores the right session
  const urlSessionId = getSessionFromURL();

  const {
    sessions,
    activeSession,
    activeSessionId,
    createSession,
    deleteSession,
    switchSession,
    updateSessionMessages,
  } = useSessions(urlSessionId);

  // Track previous activeSessionId to detect switches
  const prevSessionIdRef = useRef<string | null>(null);

  // Load messages when switching sessions
  useEffect(() => {
    if (activeSession && activeSessionId !== prevSessionIdRef.current) {
      prevSessionIdRef.current = activeSessionId;
      loadMessages(activeSession.messages);
    }
  }, [activeSessionId, activeSession, loadMessages]);

  // Sync activeSessionId to the URL so refresh keeps the current session
  useEffect(() => {
    updateURLSession(activeSessionId);
  }, [activeSessionId]);

  // Listen for browser back/forward to switch sessions via URL change
  useEffect(() => {
    const onPopState = () => {
      const id = getSessionFromURL();
      if (id && id !== activeSessionId) {
        switchSession(id);
      }
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, [activeSessionId, switchSession]);

  // Save messages to active session when they change
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!activeSessionId) return;
    // Debounce saves to avoid thrashing localStorage during streaming
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      updateSessionMessages(activeSessionId, messages);
    }, 300);
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, [messages, activeSessionId, updateSessionMessages]);

  const lastQuestion = messages.length > 0
    ? [...messages].reverse().find(m => m.role === 'user')?.content || ''
    : '';

  const lastAgentMessage = messages.length > 0
    ? [...messages].reverse().find(m => m.role === 'agent')
    : undefined;

  const steps: ThinkingStep[] = lastAgentMessage?.steps || [];

  const handlePresetClick = (question: string) => {
    sendMessage(question);
    setSidebarOpen(false);
  };

  const handleNewSession = () => {
    createSession();
    clearMessages();
    setSidebarOpen(false);
  };

  const handleDeleteSession = (id: string) => {
    deleteSession(id);
    // If deleting the active session, the hook will auto-switch.
    // The effect above will load the new active session's messages.
  };

  const handleSwitchSession = (id: string) => {
    switchSession(id);
    setSidebarOpen(false);
  };

  const handleClear = () => {
    clearMessages();
    if (activeSessionId) {
      updateSessionMessages(activeSessionId, []);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {/* Desktop Sidebar */}
      <div className="hidden md:flex flex-shrink-0 h-full overflow-hidden">
        <Sidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onNewSession={handleNewSession}
          onDeleteSession={handleDeleteSession}
          onSwitchSession={handleSwitchSession}
          onPresetClick={handlePresetClick}
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
              onPresetClick={handlePresetClick}
            />
          </div>
        </div>
      )}

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        <ChatPanel
          messages={messages}
          loading={loading}
          onSend={sendMessage}
          onClear={handleClear}
          onMenuClick={() => setSidebarOpen(true)}
        />
      </main>

      {/* Desktop Insight Panel */}
      <div className="hidden md:flex flex-shrink-0 h-full overflow-hidden">
        <InsightPanel
          lastQuestion={lastQuestion}
          steps={steps}
          loading={loading}
        />
      </div>
    </div>
  );
}

export default App;
