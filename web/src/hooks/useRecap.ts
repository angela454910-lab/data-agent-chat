import { useState, useEffect, useRef, useCallback } from 'react';
import type { ChatMessage } from '../types';
import { generateRecap } from '../lib/api';

const IDLE_MS = 60_000;

export interface UseRecapResult {
  recap: string | null;
  generating: boolean;
  dismiss: () => void;
}

/**
 * On-demand, idle-triggered recap.
 *
 * After a settled agent turn (last message is a non-loading agent message and
 * the turn count grew since last handled), wait IDLE_MS of dwell time, then
 * call the backend recap endpoint once. The recap is purely transient: it is
 * not persisted and is dismissed on typing, sending, or explicit close.
 */
export function useRecap(messages: ChatMessage[], input: string): UseRecapResult {
  const [recap, setRecap] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const lastHandledCountRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const generatingRef = useRef(false);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // Arm the idle timer when a new agent turn settles.
  useEffect(() => {
    clearTimer();
    if (!messages.length) {
      // 切换到新对话时清空，避免上一段会话的 recap 残留显示。
      lastHandledCountRef.current = 0;
      setRecap(null);
      setGenerating(false);
      generatingRef.current = false;
      return;
    }
    const last = messages[messages.length - 1];
    // Only react to a settled agent message.
    if (last.role !== 'agent' || last.loading) return;
    // Avoid re-triggering for the same turn or for a shrunk message list.
    if (messages.length <= lastHandledCountRef.current) return;
    lastHandledCountRef.current = messages.length;

    // Snapshot the messages captured at arm time for the recap call.
    const captured = messages.slice();
    timerRef.current = setTimeout(async () => {
      if (generatingRef.current) return;
      generatingRef.current = true;
      setGenerating(true);
      setRecap(null);
      try {
        const text = await generateRecap(captured);
        setRecap(text);
      } catch {
        // recap is best-effort; silently give up
      } finally {
        generatingRef.current = false;
        setGenerating(false);
      }
    }, IDLE_MS);

    return clearTimer;
  }, [messages, clearTimer]);

  // Dismiss the recap as soon as the user starts typing.
  useEffect(() => {
    if (input === '') return;
    if (recap || generating) {
      setRecap(null);
      setGenerating(false);
      generatingRef.current = false;
      clearTimer();
    }
  }, [input, recap, generating, clearTimer]);

  const dismiss = useCallback(() => {
    setRecap(null);
    setGenerating(false);
    generatingRef.current = false;
    clearTimer();
  }, [clearTimer]);

  return { recap, generating, dismiss };
}
