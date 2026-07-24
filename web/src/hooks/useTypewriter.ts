import { useEffect, useRef, useState } from 'react';

/**
 * 逐字揭示 `target`，模拟 token 流式打字效果（无光标）。
 *
 * - `animate=true`：内容出现后开始逐字打出，并持续追赶不断增长的 `target`
 *   （实时消息随流式 chunk 增长），直到打完。即便来源的 loading 标志翻 false
 *   也继续打完，避免半截答案整段补齐。
 * - `animate=false`（历史消息）：直接展示全文，不动画。
 */
export function useTypewriter(
  target: string,
  animate: boolean,
  speed = 24,
): { shown: string; done: boolean } {
  const [shown, setShown] = useState('');
  const startedRef = useRef(false);

  // 非动画（历史消息）：始终瞬显全文
  useEffect(() => {
    if (!animate && !startedRef.current) {
      setShown(target);
    }
  }, [animate, target]);

  // 逐字推进：内容出现后开始，追赶不断增长的 target（实时流式 chunk）。
  // 每拍至少揭一字；落后较多时按比例加快，避免长答案长时间拖在后面。
  useEffect(() => {
    if (!animate) return;
    const remaining = target.length - shown.length;
    if (remaining <= 0) return;
    if (target && !startedRef.current) startedRef.current = true;
    if (!startedRef.current) return;
    const step = Math.max(1, Math.ceil(remaining / 80));
    const id = setTimeout(() => setShown(target.slice(0, shown.length + step)), speed);
    return () => clearTimeout(id);
  }, [shown, target, animate, speed]);

  return { shown, done: shown.length >= target.length };
}
