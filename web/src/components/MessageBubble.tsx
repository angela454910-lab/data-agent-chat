import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Bot, User, ChevronDown, ChevronRight, Wrench, CheckCircle2 } from 'lucide-react';
import type { ChatMessage, ThinkingStep } from '../types';
import clsx from 'clsx';
import { StepDetail } from './StepDetail';
import { useTypewriter } from '../hooks/useTypewriter';
import { ThinkingStatus } from './ThinkingStatus';

interface Props {
  message: ChatMessage;
  sessionStatus?: 'done' | 'error';
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
        <div className="mt-1 ml-4 p-2 bg-slate-50 rounded-lg overflow-x-auto border border-slate-200 step-expand-enter">
          <StepDetail detail={step.detail} />
        </div>
      )}
    </div>
  );
}

export function MessageBubble({ message, sessionStatus }: Props) {
  const isUser = message.role === 'user';
 const hasSteps = !isUser && message.steps.length > 0;

// Agent 回答逐字揭示（无光标）。loading 期间及之后持续打到追上；历史消息瞬显。
 // 实时消息（挂载时 loading）逐字打出并追赶流式 chunk；历史消息直接显示全文。
  // 挂载时一次性捕获 loading，避免后续 loading 翻 false 后被打字机当作历史消息整段瞬显。
  const [isLive] = useState(() => !!message.loading);
  const { shown: shownContent, done: typingDone } = useTypewriter(message.content, isLive, 10);

  // 打字进行中以 rAF 节流滚到底，避免逐字触发昂贵的平滑滚动
  const rafRef = useRef<number | null>(null);
  useEffect(() => {
    if (isUser || !shownContent || typingDone) return;
    if (rafRef.current != null) return;
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null;
      document.getElementById('messages-scroll-end')?.scrollIntoView({ block: 'end' });
    });
  }, [shownContent, typingDone, isUser]);

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

  return (
    <div className="mb-6">
      {/* Agent header — bot avatar with annotation */}
     <div className="flex items-center gap-2 mb-2">
        <span className="ann ann-e ann-blue ann-no-mark" data-note="AI 助手" style={{ display: 'inline-flex' }}>
          <div className="flex-shrink-0 w-6 h-6 rounded-full bg-slate-100 flex items-center justify-center">
            <Bot size={13} className="text-slate-500" />
          </div>
        </span>
        {isLive && !shownContent && (
          <ThinkingStatus steps={message.steps} />
        )}
      </div>

      {/* Thinking chain — annotation style */}
      {hasSteps && (
        <div className="mb-3 ml-0">
          <div className="flex items-center gap-1.5 mb-1.5">
            <span
              className="font-['Shantell_Sans',cursive] text-xs text-slate-400"
              style={{ transform: 'rotate(-1.5deg)', display: 'inline-block' }}
            >
              思考过程
            </span>
            <svg width="48" height="6" viewBox="0 0 48 6" className="flex-shrink-0">
              <path
                d="M1 4 C8 1 14 5 20 3 C26 1 32 5 38 3 C42 1.5 45 4 47 3"
                fill="none"
                stroke="#cbd5e1"
                strokeWidth="1.2"
                strokeLinecap="round"
              />
            </svg>
          </div>
          <div className="space-y-0.5">
            {message.steps.map(step => (
              <StepItem key={step.id} step={step} />
            ))}
          </div>
        </div>
      )}

      {/* Content */}
      {shownContent && (
        <div className="ml-0 pl-0">
          <div className="markdown-content text-sm text-slate-700">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {shownContent}
            </ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}
