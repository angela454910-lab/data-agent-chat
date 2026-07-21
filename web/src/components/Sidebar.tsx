import { Plus, MessageSquare, Trash2, MessageSquareQuote } from 'lucide-react';
import type { Session } from '../types';
import clsx from 'clsx';

interface Props {
  sessions: Session[];
  activeSessionId: string | null;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
  onSwitchSession: (id: string) => void;
  onPresetClick: (question: string) => void;
}

const PRESETS = [
  '最近30天销售额是多少，哪个渠道贡献最大？',
  '各地区订单量排名如何？',
  '退款率怎么样？',
  '新用户转化率如何？',
];

export function Sidebar({
  sessions,
  activeSessionId,
  onNewSession,
  onDeleteSession,
  onSwitchSession,
  onPresetClick,
}: Props) {
  return (
    <aside className="w-72 bg-white border-r border-slate-200 flex flex-col h-full overflow-hidden">
      {/* Brand */}
      <div className="px-5 py-4 border-b border-slate-200 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-blue-500 flex items-center justify-center">
            <span className="text-white font-bold text-sm">D</span>
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-800">Data Agent</h1>
            <p className="text-xs text-slate-500">LangChain + LangGraph</p>
          </div>
        </div>
      </div>

      {/* New Chat Button */}
      <div className="px-4 pt-4 pb-2 flex-shrink-0">
        <button
          onClick={onNewSession}
          className="flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-lg bg-blue-500 text-white text-sm font-medium hover:bg-blue-600 transition-colors"
        >
          <Plus size={16} />
          <span>新对话</span>
        </button>
      </div>

      {/* Session History */}
      <div className="flex-1 overflow-y-auto min-h-0 px-3 py-2">
        <div className="flex items-center gap-2 px-2 mb-2">
          <MessageSquare size={14} className="text-slate-400" />
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
            历史记录
          </h3>
        </div>
        <div className="space-y-0.5">
          {sessions.filter(s => s.messages.length > 0).map(session => (
            <div
              key={session.id}
              className={clsx(
                'group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors',
                session.id === activeSessionId
                  ? 'bg-blue-50 text-blue-700'
                  : 'hover:bg-slate-50 text-slate-700',
              )}
              onClick={() => onSwitchSession(session.id)}
            >
              <MessageSquare
                size={14}
                className={clsx(
                  'flex-shrink-0',
                  session.id === activeSessionId ? 'text-blue-500' : 'text-slate-400',
                )}
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate">{session.title}</p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteSession(session.id);
                }}
                className={clsx(
                  'flex-shrink-0 p-1 rounded transition-colors',
                  'opacity-0 group-hover:opacity-100',
                  'hover:bg-red-50 hover:text-red-500 text-slate-400',
                )}
                title="删除对话"
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}
          {sessions.filter(s => s.messages.length > 0).length === 0 && (
            <p className="text-xs text-slate-400 text-center py-4">暂无历史记录</p>
          )}
        </div>
      </div>

      {/* Presets */}
      <div className="flex-shrink-0 border-t border-slate-200 px-4 py-3">
        <div className="flex items-center gap-2 mb-2">
          <MessageSquareQuote size={14} className="text-slate-400" />
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
            示例问题
          </h3>
        </div>
        <div className="space-y-1">
          {PRESETS.map((q, i) => (
            <button
              key={i}
              onClick={() => onPresetClick(q)}
              className="block w-full text-left text-xs text-slate-500 px-2 py-1.5 rounded hover:bg-blue-50 hover:text-blue-700 transition-colors truncate"
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}