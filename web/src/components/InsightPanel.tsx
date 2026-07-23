import { X, BarChart3, Hash, Database, FileText, Table2 } from 'lucide-react';
import type { Session, ChatMessage } from '../types';

interface Props {
  session: Session | null;
  messages: ChatMessage[];
  isOpen: boolean;
  onToggle: () => void;
}

export function InsightPanel({ session, messages, onToggle }: Props) {
  const metadata = session?.metadata;
  const tables = metadata?.tables ?? [];

  const totalMessages = messages.length;
  const totalSteps = messages.reduce((sum, m) => sum + (m.steps?.length || 0), 0);
  const userTurns = messages.filter(m => m.role === 'user').length;

  const hasData = totalMessages > 0 || tables.length > 0;

  return (
    <aside className="w-72 bg-white border-l border-slate-200 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-200 flex-shrink-0 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BarChart3 size={16} className="text-blue-500" />
          <h2 className="text-sm font-semibold text-slate-800">会话概览</h2>
        </div>
        <button
          onClick={onToggle}
          className="p-1 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
          title="关闭面板"
        >
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 min-h-0 sidebar-scrollbar">
        {!hasData ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center mb-3">
              <BarChart3 size={20} className="text-slate-400" />
            </div>
            <p className="text-sm text-slate-500">
              开始对话后，会话概览将在此显示
            </p>
          </div>
        ) : (
          <div className="space-y-5">
            {/* Tables Used */}
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <Table2 size={13} className="text-blue-500" />
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">涉及数据表</h3>
              </div>
              {tables.length > 0 ? (
                <div className="space-y-1">
                  {tables.map(name => (
                    <div
                      key={name}
                      className="flex items-center gap-2 px-2.5 py-1.5 rounded-md bg-slate-50 border border-slate-100"
                    >
                      <Database size={11} className="text-slate-400" />
                      <span className="text-sm text-slate-700 font-mono">{name}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 bg-slate-50 rounded-lg p-2.5 border border-slate-200">
                  本次会话暂未使用数据表
                </p>
              )}
            </div>

            {/* Stats */}
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <Hash size={13} className="text-slate-400" />
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">会话统计</h3>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-slate-50 rounded-lg p-2.5 border border-slate-200 text-center">
                  <p className="text-lg font-semibold text-slate-800">{userTurns}</p>
                  <span className="text-[10px] text-slate-500 uppercase">提问</span>
                </div>
                <div className="bg-slate-50 rounded-lg p-2.5 border border-slate-200 text-center">
                  <p className="text-lg font-semibold text-slate-800">{totalMessages}</p>
                  <span className="text-[10px] text-slate-500 uppercase">消息</span>
                </div>
                <div className="bg-slate-50 rounded-lg p-2.5 border border-slate-200 text-center">
                  <p className="text-lg font-semibold text-slate-800">{totalSteps}</p>
                  <span className="text-[10px] text-slate-500 uppercase">步骤</span>
                </div>
              </div>
            </div>

            {/* Recent Q&A */}
            {totalMessages > 0 && (
              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <FileText size={13} className="text-slate-400" />
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">最近提问</h3>
                </div>
                <div className="space-y-1">
                  {messages.filter(m => m.role === 'user').slice(-3).reverse().map((m, i, arr) => (
                    <div
                      key={m.id}
                      className="flex items-start gap-2 px-2.5 py-1.5 rounded text-xs bg-slate-50 border border-slate-100"
                    >
                      <span className="text-[10px] text-slate-400 w-4 flex-shrink-0 mt-0.5">{arr.length - i}</span>
                      <span className="flex-1 text-slate-600 line-clamp-2">{m.content}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
