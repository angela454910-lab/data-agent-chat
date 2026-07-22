import { X, BarChart3, Hash, Clock, Database } from 'lucide-react';
import type { ThinkingStep, ChatMessage } from '../types';

interface Props {
  lastQuestion: string;
  steps: ThinkingStep[];
  loading: boolean;
  messages: ChatMessage[];
  isOpen: boolean;
  onToggle: () => void;
}

/* Hand-drawn squiggly underline for section titles */
function Squiggle({ color = '#cbd5e1' }: { color?: string }) {
  return (
    <svg width="100%" height="5" viewBox="0 0 60 5" className="block">
      <path
        d="M1 3 C6 1 12 5 18 3 C24 1 30 5 36 3 C42 1 48 5 54 3 C57 2 59 3.5 59 3"
        fill="none"
        stroke={color}
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

/* Hand-drawn section heading */
function SectionHeading({ children, color = '#94a3b8' }: { children: string; color?: string }) {
  return (
    <div className="mb-2.5">
      <h3
        className="font-['Shantell_Sans',cursive] text-sm text-slate-500 inline-block"
        style={{ transform: 'rotate(-1deg)' }}
      >
        {children}
      </h3>
      <Squiggle color={color} />
    </div>
  );
}

export function InsightPanel({ lastQuestion, steps, loading, messages, onToggle }: Props) {
  const totalMessages = messages.length;

  const toolNames = [...new Set(
    steps
      .filter(s => s.type === 'tool_call')
      .map(s => {
        const match = s.label.match(/调用工具:\s*(.+)/);
        return match ? match[1] : s.label;
      })
  )];

  const hasData = lastQuestion || steps.length > 0;

  return (
    <aside className="w-72 bg-white border-l border-slate-200 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-200 flex-shrink-0 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BarChart3 size={16} className="text-blue-500" />
          <h2 className="text-sm font-semibold text-slate-800">分析详情</h2>
          {loading && (
            <span className="text-xs text-blue-500 animate-pulse">Running...</span>
          )}
        </div>
        <button
          onClick={onToggle}
          className="p-1 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
          title="关闭面板"
        >
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 min-h-0">
        {!hasData ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center mb-3">
              <BarChart3 size={20} className="text-slate-400" />
            </div>
            <p className="text-sm text-slate-500">
              提问后，分析详情将在此显示
            </p>
          </div>
        ) : (
          <div className="space-y-5">
            {/* Question */}
            {lastQuestion && (
              <div>
                <SectionHeading color="#93c5fd">当前问题</SectionHeading>
                <p className="text-sm text-slate-700 bg-slate-50 rounded-lg p-3 border border-slate-200">
                  {lastQuestion}
                </p>
              </div>
            )}

            {/* Stats */}
            <div>
              <SectionHeading color="#94a3b8">会话统计</SectionHeading>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-slate-50 rounded-lg p-2.5 border border-slate-200">
                  <div className="flex items-center gap-1.5 mb-1">
                    <Hash size={12} className="text-slate-400" />
                    <span className="text-[10px] text-slate-500 uppercase">消息</span>
                  </div>
                  <p className="text-lg font-semibold text-slate-800">{totalMessages}</p>
                </div>
                <div className="bg-slate-50 rounded-lg p-2.5 border border-slate-200">
                  <div className="flex items-center gap-1.5 mb-1">
                    <Clock size={12} className="text-slate-400" />
                    <span className="text-[10px] text-slate-500 uppercase">步骤</span>
                  </div>
                  <p className="text-lg font-semibold text-slate-800">{steps.length}</p>
                </div>
              </div>
            </div>

            {/* Tools Used */}
            {toolNames.length > 0 && (
              <div>
                <SectionHeading color="#fcd34d">调用工具</SectionHeading>
                <div className="flex flex-wrap gap-1.5">
                  {toolNames.map(name => (
                    <span
                      key={name}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-blue-50 text-blue-700 text-xs border border-blue-100"
                    >
                      <Database size={10} />
                      {name}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Step Summary */}
            {steps.length > 0 && (
              <div>
                <SectionHeading color="#86efac">步骤概览</SectionHeading>
                <div className="space-y-1">
                  {steps.map((step, i) => (
                    <div
                      key={step.id}
                      className="flex items-center gap-2 px-2.5 py-1.5 rounded text-xs bg-slate-50 border border-slate-100"
                    >
                      <span className="text-[10px] text-slate-400 w-4">{i + 1}</span>
                      <span className="flex-1 text-slate-600 truncate">{step.label}</span>
                      <span className={step.type === 'tool_call' ? 'text-amber-500' : 'text-green-500'}>
                        {step.type === 'tool_call' ? '🔧' : '✓'}
                      </span>
                    </div>
                  ))}
                  {loading && (
                    <div className="flex items-center gap-2 px-2.5 py-1.5 text-blue-500 text-xs">
                      <div className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                      <span>Processing...</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
