import { useCallback, useState } from 'react';

export function usePersistedPaneSize(
  storageKey: string,
  defaultSize: number,
  min: number,
  max: number
): [number, (val: number) => void, () => void] {
  const [size, setSize] = useState<number>(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) {
        const parsed = Number(raw);
        if (Number.isFinite(parsed)) {
          return Math.max(min, Math.min(max, parsed));
        }
      }
    } catch {
      // Ignore storage access errors
    }
    return defaultSize;
  });

  const updateSize = useCallback(
    (next: number) => {
      const clamped = Math.max(min, Math.min(max, next));
      setSize(clamped);
      try {
        localStorage.setItem(storageKey, String(clamped));
      } catch {
        // Ignore storage errors
      }
    },
    [max, min, storageKey]
  );

  const resetSize = useCallback(() => {
    updateSize(defaultSize);
  }, [defaultSize, updateSize]);

  return [size, updateSize, resetSize];
}

