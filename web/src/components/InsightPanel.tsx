import { Activity, HelpCircle, Wrench, CheckCircle2, Brain } from 'lucide-react';
import { StepDetail } from './StepDetail';
import type { ThinkingStep } from '../types';

interface Props {
  lastQuestion: string;
  steps: ThinkingStep[];
  loading: boolean;
}

function StepIcon({ type }: { type: ThinkingStep['type'] }) {
  if (type === 'tool_call') return <Wrench size={14} className="text-amber-500" />;
  return <CheckCircle2 size={14} className="text-green-500" />;
}

export function InsightPanel({ lastQuestion, steps, loading }: Props) {
  const hasData = lastQuestion || steps.length > 0;

  return (
    <aside className="w-80 bg-white border-l border-slate-200 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-slate-200 flex-shrink-0">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-blue-500" />
          <h2 className="text-sm font-semibold text-slate-800">Analysis Process</h2>
          {loading && (
            <span className="ml-auto text-xs text-blue-500 animate-pulse">Running...</span>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 min-h-0">
        {!hasData ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center mb-3">
              <Activity size={20} className="text-slate-400" />
            </div>
            <p className="text-sm text-slate-500">
              The analysis process will be displayed here after asking a question
            </p>
          </div>
        ) : (
          <div className="space-y-5">
            {/* Question */}
            {lastQuestion && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <HelpCircle size={14} className="text-slate-400" />
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                    Question
                  </h3>
                </div>
                <p className="text-sm text-slate-700 bg-slate-50 rounded-lg p-3 border border-slate-200">
                  {lastQuestion}
                </p>
              </div>
            )}

            {/* Thinking Steps */}
            {steps.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Brain size={14} className="text-slate-400" />
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                    Thinking Chain
                  </h3>
                  <span className="text-xs text-slate-400">({steps.length})</span>
                </div>
                <div className="space-y-1">
                  {steps.map((step, i) => (
                    <div
                      key={step.id}
                      className="flex items-start gap-2 p-2 rounded-lg bg-slate-50 border border-slate-200"
                    >
                      <div className="flex-shrink-0 mt-0.5">
                        <StepIcon type={step.type} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-slate-700">{step.label}</p>
                        {step.detail && (
                          <div className="mt-1 bg-white p-1.5 rounded border border-slate-100 max-h-32 overflow-y-auto">
                            <StepDetail detail={step.detail} compact />
                          </div>
                        )}
                      </div>
                      <span className="flex-shrink-0 text-[10px] text-slate-400">#{i + 1}</span>
                    </div>
                  ))}
                  {loading && (
                    <div className="flex items-center gap-2 p-2 text-blue-500">
                      <div className="w-3.5 h-3.5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                      <span className="text-xs">Processing...</span>
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
