import { useState, useEffect, useCallback } from 'react';
import { fetchMemories, deleteMemoryApi } from '../lib/api';
import type { Memory } from '../types';

export function useMemories() {
  const [memories, setMemories] = useState<Memory[]>([]);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchMemories();
      setMemories(data);
    } catch {
      // memory panel is best-effort; never block the chat on it
    }
  }, []);

  // Load once on mount.
  useEffect(() => {
    refresh();
  }, [refresh]);

  const remove = useCallback(async (id: string) => {
    try {
      await deleteMemoryApi(id);
      setMemories(prev => prev.filter(m => m.id !== id));
    } catch {
      // ignore
    }
  }, []);

  return { memories, refresh, remove };
}
