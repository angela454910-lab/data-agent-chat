import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Bot, User, ChevronDown, ChevronRight, Wrench, CheckCircle2, Loader2 } from 'lucide-react';
import type { ChatMessage, ThinkingStep } from '../types';
import clsx from 'clsx';

interface Props {
  message: ChatMessage;
}

function StepItem({ step }: { step: ThinkingStep }) {
  const [expanded, setExpanded] = useState(false);

  const icon = step.type === 'tool_call'
    ? <Wrench size={12} className="text-amber-500" />
    : <CheckCircle2 size={12} className="text-green-500" />;

  return (
    <div className="text-xs">
      <button
        onClick={() => step.detail && setExpanded(!expanded)}
        className={clsx(
          'flex items-center gap-1.5 w-full text-left py-0.5 hover:bg-slate-100 rounded px-1 -mx-1 transition-colors',
          step.detail ? 'cursor-pointer' : 'cursor-default',
        )}
      >
        {step.detail ? (
          expanded ? <ChevronDown size={10} className="text-slate-400" /> : <ChevronRight size={10} className="text-slate-400" />
        ) : null}
        {icon}
        <span className="text-slate-600">{step.label}</span>
      </button>
      {expanded && step.detail && (
        <pre className="mt-1 ml-5 p-2 bg-slate-50 rounded text-[10px] text-slate-500 overflow-x-auto whitespace-pre-wrap border border-slate-200">
          {step.detail}
        </pre>
      )}
    </div>
  );
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';
  const [stepsExpanded, setStepsExpanded] = useState(false);

  return (
    <div
      className={clsx('flex gap-3 mb-4', isUser ? 'flex-row-reverse' : 'flex-row')}
    >
      <div
        className={clsx(
          'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center',
          isUser ? 'bg-blue-500 text-white' : 'bg-slate-200 text-slate-600',
        )}
      >
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>

      <div
        className={clsx(
          'max-w-[75%] rounded-2xl px-4 py-3',
          isUser
            ? 'bg-blue-500 text-white rounded-br-sm'
            : 'bg-slate-100 border border-slate-200 rounded-bl-sm',
        )}
      >
        {/* Thinking chain */}
        {!isUser && message.steps.length > 0 && (
          <div className="mb-2 pb-2 border-b border-slate-200/60">
            <button
              onClick={() => setStepsExpanded(!stepsExpanded)}
              className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 mb-1 transition-colors"
            >
              {stepsExpanded
                ? <ChevronDown size={12} />
                : <ChevronRight size={12} />}
              <span className="font-medium">
                思考过程 ({message.steps.length} 步)
              </span>
              {message.loading && (
                <Loader2 size={10} className="animate-spin ml-1" />
              )}
            </button>
            {stepsExpanded && (
              <div className="space-y-0.5 mt-1">
                {message.steps.map(step => (
                  <StepItem key={step.id} step={step} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Loading state with no steps yet */}
        {message.loading && message.steps.length === 0 && (
          <div className="flex items-center gap-2 text-slate-500">
            <div className="flex gap-1">
              <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
            <span className="text-sm">Analyzing...</span>
          </div>
        )}

        {/* Content */}
        {message.loading && !message.content ? null : isUser ? (
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
        ) : (
          <div className="markdown-content text-sm">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
