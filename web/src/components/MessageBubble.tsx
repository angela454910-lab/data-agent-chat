import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Bot, User, ChevronDown, ChevronRight, Wrench, CheckCircle2, Loader2 } from 'lucide-react';
import type { ChatMessage, ThinkingStep } from '../types';
import clsx from 'clsx';
import { StepDetail } from './StepDetail';

interface Props {
  message: ChatMessage;
}

function StepItem({ step }: { step: ThinkingStep }) {
  const [expanded, setExpanded] = useState(false);

  const icon = step.type === 'tool_call'
    ? <Wrench size={10} className="text-amber-500 flex-shrink-0" />
    : <CheckCircle2 size={10} className="text-green-500 flex-shrink-0" />;

  return (
    <div className="text-xs">
      <button
        onClick={() => step.detail && setExpanded(!expanded)}
        className={clsx(
          'flex items-center gap-1 w-full text-left py-0.5 hover:bg-slate-50 rounded px-1 -mx-1 transition-colors',
          step.detail ? 'cursor-pointer' : 'cursor-default',
        )}
      >
        {step.detail ? (
          expanded ? <ChevronDown size={10} className="text-slate-400 flex-shrink-0" /> : <ChevronRight size={10} className="text-slate-400 flex-shrink-0" />
        ) : <span className="w-2.5 flex-shrink-0" />}
        {icon}
        <span className="text-slate-500 truncate">{step.label}</span>
      </button>
      {expanded && step.detail && (
        <div className="mt-1 ml-4 p-2 bg-slate-50 rounded-lg overflow-x-auto border border-slate-200">
          <StepDetail detail={step.detail} />
        </div>
      )}
    </div>
  );
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';
  const hasSteps = !isUser && message.steps.length > 0;

  // User message: compact rounded bubble
  if (isUser) {
    return (
      <div className="flex justify-end mb-4">
        <div className="flex items-end gap-2 max-w-[70%]">
          <div className="bg-blue-50 border border-blue-100 rounded-2xl rounded-br-sm px-4 py-2.5">
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">{message.content}</p>
          </div>
          <div className="flex-shrink-0 w-7 h-7 rounded-full bg-blue-500 flex items-center justify-center">
            <User size={14} className="text-white" />
          </div>
        </div>
      </div>
    );
  }

  // Agent message: flat, inline content
  return (
    <div className="mb-6">
      {/* Agent header */}
      <div className="flex items-center gap-2 mb-2">
        <div className="flex-shrink-0 w-6 h-6 rounded-full bg-slate-100 flex items-center justify-center">
          <Bot size={13} className="text-slate-500" />
        </div>
        <span className="text-xs font-medium text-slate-500">Data Agent</span>
        {message.loading && message.steps.length === 0 && (
          <Loader2 size={12} className="animate-spin text-slate-400 ml-1" />
        )}
      </div>

      {/* Thinking chain — always visible, minimal */}
      {hasSteps && (
        <div className="mb-3 ml-0">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-[10px] text-slate-400 uppercase tracking-wide">思考过程</span>
            {message.loading && (
              <Loader2 size={10} className="animate-spin text-slate-400" />
            )}
          </div>
          <div className="space-y-0.5">
            {message.steps.map(step => (
              <StepItem key={step.id} step={step} />
            ))}
          </div>
        </div>
      )}

      {/* Loading with no steps */}
      {message.loading && message.steps.length === 0 && (
        <div className="flex items-center gap-2 mb-2">
          <div className="flex gap-1">
            <span className="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
          <span className="text-sm text-slate-400">Analyzing...</span>
        </div>
      )}

      {/* Content — flat, no bubble */}
      {message.content && (
        <div className="ml-0 pl-0">
          <div className="markdown-content text-sm text-slate-700">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}