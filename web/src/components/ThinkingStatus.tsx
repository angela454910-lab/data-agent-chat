import { useTypewriter } from '../hooks/useTypewriter';
import type { ThinkingStep } from '../types';

/** 把最新真实步骤映射为一句自然的过程文案，让等待状态与 agent 实际进度挂钩。 */
function stepToText(step?: ThinkingStep): string | null {
  if (!step) return null;
  switch (step.type) {
    case 'tool_call':
      return '正在查找相关内容';
    case 'tool_result':
      return '正在分析数据';
    case 'thinking':
    default:
      return '正在思考';
  }
}

/** 单条短语的逐字揭示；key 变化时整体重挂载，从空开始打，避免新短语从旧位置串味。 */
function TypewriterText({ text, speed, className }: { text: string; speed: number; className?: string }) {
  const { shown } = useTypewriter(text, true, speed);
  return <span className={className}>{shown}</span>;
}

interface Props {
  steps: ThinkingStep[];
}

/**
 * 等待期文案：优先反映 agent 真实步骤（tool_call / tool_result），
 * 没有真实步骤时固定显示"正在思考"（不轮播，避免显得假），显示在
 * agent 头像右侧，答案出现前持续展示，替代转圈加载。每句逐字打出，无光标、无转圈。
 */
export function ThinkingStatus({ steps }: Props) {
  const latest = steps.length > 0 ? steps[steps.length - 1] : undefined;
  const text = stepToText(latest) ?? '正在思考';

  return (
    <span className="text-sm ml-1 select-none">
      <TypewriterText key={text} text={`${text}...`} speed={60} className="thinking-shimmer" />
    </span>
  );
}
