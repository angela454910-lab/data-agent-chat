import { useState, useEffect, useRef } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatPanel } from './components/ChatPanel';
import { InsightPanel } from './components/InsightPanel';
import { useChat } from './hooks/useChat';
import { useSessions } from './hooks/useSessions';
import type { ThinkingStep } from './types';
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
  const { messages, loading, sendMessage, clearMessages, loadMessages } = useChat();

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

  const prevSessionIdRef = useRef<string | null>(null);

  // Load messages when switching sessions
  useEffect(() => {
    if (activeSession && activeSessionId !== prevSessionIdRef.current) {
      prevSessionIdRef.current = activeSessionId;
      loadMessages(activeSession.messages);
    } else if (!activeSession && activeSessionId !== prevSessionIdRef.current) {
      // No active session - clear messages for welcome screen
      prevSessionIdRef.current = activeSessionId;
      clearMessages();
    }
  }, [activeSessionId, activeSession, loadMessages, clearMessages]);

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
        // Navigated to root - show welcome screen
        clearMessages();
      }
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, [activeSessionId, switchSession, clearMessages]);

  // Save messages to active session when they change
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!activeSessionId) return;
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

  const handleNewSession = () => {
    clearMessages();
    setSidebarOpen(false);
  };

  const handleSendMessage = (message: string) => {
    // Create session on first message if none exists
    if (!activeSessionId) {
      const newId = createSession();
      setTimeout(() => {
        sendMessage(message);
      }, 0);
    } else {
      sendMessage(message);
    }
  };

  const handleDeleteSession = (id: string) => {
    deleteSession(id);
  };

  const handleSwitchSession = (id: string) => {
    switchSession(id);
    setSidebarOpen(false);
  };

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
            lastQuestion={lastQuestion}
            steps={steps}
            loading={loading}
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
