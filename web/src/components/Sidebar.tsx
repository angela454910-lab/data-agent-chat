import { Plus, MessageSquare, Trash2, Sparkles, Loader2 } from 'lucide-react';
import type { SessionSummary } from '../types';
import clsx from 'clsx';

interface Props {
  sessions: SessionSummary[];
  activeSessionId: string | null;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
  onSwitchSession: (id: string) => void;
}

export function Sidebar({
  sessions,
  activeSessionId,
  onNewSession,
  onDeleteSession,
  onSwitchSession,
}: Props) {
  // 新对话首次发送时会先放一条 message_count=0 的乐观占位，等到流式完成后
  // refreshSessions 再用后端列表覆盖。只要它是当前激活会话就显示，避免问答期间侧栏空白。
  // Keep a session in the list if it has messages, is currently active, or
  // carries a live/terminal status (thinking/done/error). The latter covers
  // the optimistic placeholder dropped right after sending the first message
  // (message_count still 0) and sessions still streaming in the background.
  const activeSessions = sessions.filter(
    s => s.message_count > 0 || s.id === activeSessionId || s.status || s.unread,
  );

  return (
    <aside className="w-72 bg-white border-r border-slate-200 flex flex-col h-full overflow-hidden">
      {/* Brand */}
      <div className="px-5 py-5 border-b border-slate-100 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/25">
              <Sparkles size={18} className="text-white" />
            </div>
            <div className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-green-400 rounded-full border-2 border-white" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-800 tracking-tight">Data Agent</h1>
            <p className="text-xs text-slate-400">AI-Powered Analytics</p>
          </div>
        </div>
      </div>

      {/* New Chat Button */}
      <div className="px-4 pt-4 pb-3 flex-shrink-0">
        <button
          onClick={onNewSession}
          className="flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-xl
                     bg-gradient-to-r from-blue-600 to-blue-500 text-white text-sm font-medium
                     hover:from-blue-500 hover:to-blue-400
                     shadow-lg shadow-blue-500/20 hover:shadow-blue-500/35
                     transition-all duration-200 active:scale-[0.98]"
        >
          <Plus size={16} />
          <span>新对话</span>
        </button>
      </div>

      {/* Session History */}
      <div className="flex-1 overflow-y-auto min-h-0 px-3 py-2 sidebar-scrollbar">
        <div className="flex items-center gap-2 px-2 mb-2">
          <MessageSquare size={14} className="text-slate-400" />
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            历史记录
          </h3>
        </div>
        <div className="space-y-0.5">
          {activeSessions.map((session) => {
            const isActive = session.id === activeSessionId;
            return (
              <div
                key={session.id}
                className={clsx(
                  'group flex items-center gap-2.5 px-3 py-2.5 rounded-xl cursor-pointer',
                  'transition-all duration-200',
                  isActive
                    ? 'bg-blue-50 text-blue-700 shadow-sm border border-blue-100/80'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-800',
                )}
                onClick={() => onSwitchSession(session.id)}
              >
                <MessageSquare
                  size={14}
                  className={clsx(
                    'flex-shrink-0 transition-colors duration-200',
                    isActive ? 'text-blue-500' : 'text-slate-400 group-hover:text-slate-500',
                  )}
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm truncate font-medium">{session.title}</p>
                </div>
                {/* Status indicator */}
                {session.status === 'thinking' && (
                  <Loader2 size={14} className="flex-shrink-0 animate-spin text-blue-500" />
                )}
                {session.unread && (
                  <span className="flex-shrink-0 w-2.5 h-2.5 rounded-full bg-green-500" />
                )}
                {session.status === 'error' && (
                  <span className="flex-shrink-0 w-2.5 h-2.5 rounded-full bg-red-500" />
                )}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSession(session.id);
                  }}
                  className={clsx(
                    'flex-shrink-0 p-1 rounded-lg transition-all duration-200',
                    'opacity-0 group-hover:opacity-100',
                    isActive
                      ? 'hover:bg-red-100 hover:text-red-500 text-blue-400'
                      : 'hover:bg-red-50 hover:text-red-400 text-slate-300',
                    'active:scale-90',
                  )}
                  title="删除对话"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            );
          })}
          {activeSessions.length === 0 && (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <div className="w-12 h-12 rounded-2xl bg-slate-100 flex items-center justify-center mb-3">
                <MessageSquare size={20} className="text-slate-300" />
              </div>
              <p className="text-xs text-slate-400">暂无历史记录</p>
              <p className="text-[10px] text-slate-400 mt-1">开始新对话，探索数据</p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
