import { useState, useRef, useEffect } from 'react';
import { Send, Menu, Sparkles } from 'lucide-react';
import type { ChatMessage } from '../types';
import { MessageBubble } from './MessageBubble';
import { StarterCards } from './StarterCards';

interface Props {
  messages: ChatMessage[];
  loading: boolean;
  onSend: (message: string) => void;
  onMenuClick?: () => void;
  sessionStatus?: 'done' | 'error';
}

export function ChatPanel({ messages, loading, onSend, onMenuClick, sessionStatus }: Props) {
  const [input, setInput] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const [inputMoved, setInputMoved] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  const isEmptyConversation = messages.length === 0;
  const isWelcome = isEmptyConversation && !inputMoved;

  // Find the index of the last agent message
  const lastAgentIndex = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'agent') return i;
    }
    return -1;
  })();

  // Reset inputMoved when messages become empty (new session)
  useEffect(() => {
    if (isEmptyConversation) {
      setInputMoved(false);
    }
  }, [isEmptyConversation]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || loading) return;
    setInputMoved(true);
    onSend(trimmed);
    setInput('');
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gradient-to-b from-white to-slate-50/50 min-h-0 relative">
      {/* Animated top spacer — pushes content to center when welcome, collapses when sending */}
      <div
        className="flex-shrink-0 overflow-hidden"
        style={{
          height: isWelcome ? '22vh' : '0px',
          transition: 'height 0.5s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      />

      {/* Mobile hamburger — floating */}
      {onMenuClick && (
        <button
          onClick={onMenuClick}
          className="md:hidden absolute top-4 left-4 z-10 p-2 rounded-xl bg-white/80 backdrop-blur-sm border border-slate-200/60 shadow-soft hover:bg-white transition-all duration-200 hover:shadow-soft-lg"
          aria-label="Open menu"
        >
          <Menu size={18} className="text-slate-500" />
        </button>
      )}

      {/* Messages */}
      <div
        ref={messagesContainerRef}
        className={`overflow-y-auto px-4 md:px-6 py-4 min-h-0 ${!isEmptyConversation ? 'flex-1' : ''}`}
      >
        {isEmptyConversation ? (
          <div
            style={{
              opacity: isWelcome ? 1 : 0,
              transform: isWelcome ? 'translateY(0)' : 'translateY(-12px)',
              pointerEvents: isWelcome ? 'auto' : 'none',
              transition: 'opacity 0.3s ease, transform 0.3s ease',
            }}
          >
            <StarterCards onQuestionClick={(q) => {
              setInputMoved(true);
              onSend(q);
            }} />
          </div>
        ) : (
          <div className="max-w-3xl mx-auto">
            {messages.map((msg, i) => (
              <div
                key={msg.id}
                className={msg.role === 'user' ? 'message-bubble-user' : ''}
                style={{ animationDelay: `${i * 50}ms` }}
              >
                <MessageBubble
                  message={msg}
                  sessionStatus={i === lastAgentIndex ? sessionStatus : undefined}
                />
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Composer — floating with glass effect */}
      <div
        className="flex-shrink-0 px-4 md:px-6 pb-4 pt-2"
        style={{ transition: 'all 0.5s cubic-bezier(0.16, 1, 0.3, 1)' }}
      >
        <div className="max-w-3xl mx-auto">
          {isEmptyConversation && (
            <p className="ann ann-se ann-blue ann-no-mark text-xs text-slate-400 mb-1" data-note="或输入你想问的问题">
              &nbsp;
            </p>
          )}
          <form
            onSubmit={handleSubmit}
            className={[
              'flex items-end gap-3 rounded-2xl p-3 transition-all duration-300',
              isFocused
                ? 'bg-white shadow-soft-xl border-slate-200/80 scale-[1.01]'
                : 'bg-white shadow-soft-lg border-slate-100',
              'border',
            ].join(' ')}
          >
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              placeholder="Ask a data question..."
              rows={1}
              className="flex-1 resize-none text-sm outline-none bg-transparent py-1 px-1 placeholder:text-slate-400 align-top"
              disabled={loading}
              style={{ minHeight: '24px', maxHeight: '120px' }}
              onInput={(e) => {
                const el = e.currentTarget;
                el.style.height = 'auto';
                el.style.height = Math.min(el.scrollHeight, 120) + 'px';
              }}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className={[
                'flex items-center justify-center w-10 h-10 rounded-xl flex-shrink-0',
                'transition-all duration-200 btn-press',
                input.trim() && !loading
                  ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-500/30 hover:shadow-blue-500/50 hover:from-blue-400 hover:to-blue-500'
                  : 'bg-slate-100 text-slate-300',
                'disabled:cursor-not-allowed',
              ].join(' ')}
            >
              {loading ? (
                <Sparkles size={16} className="animate-pulse" />
              ) : (
                <Send size={16} />
              )}
            </button>
          </form>
          <p className="text-center text-[10px] text-slate-400 mt-2">
            Data Agent 可能产生不准确的结果，请核实重要信息
          </p>
        </div>
      </div>
    </div>
  );
}
