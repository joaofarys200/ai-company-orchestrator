import React, { useEffect, useRef, useState } from 'react';

interface ResizableHandleProps {
  direction: 'horizontal' | 'vertical';
  value: number;
  min: number;
  max: number;
  reverse?: boolean;
  onChange: (next: number) => void;
  onReset?: () => void;
  ariaLabel?: string;
}

export const ResizableHandle: React.FC<ResizableHandleProps> = ({
  direction,
  value,
  min,
  max,
  reverse = false,
  onChange,
  onReset,
  ariaLabel = 'Redimensionar painel',
}) => {
  const [dragging, setDragging] = useState(false);
  const startPosRef = useRef(0);
  const startValRef = useRef(value);

  useEffect(() => {
    if (!dragging) return;
    const onMove = (e: MouseEvent) => {
      const delta = direction === 'horizontal' ? e.clientX - startPosRef.current : e.clientY - startPosRef.current;
      const adjusted = reverse ? startValRef.current - delta : startValRef.current + delta;
      onChange(Math.max(min, Math.min(max, Math.round(adjusted))));
    };
    const onUp = () => setDragging(false);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    document.body.style.cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize';
    document.body.style.userSelect = 'none';
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [direction, dragging, max, min, onChange, reverse]);

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    startPosRef.current = direction === 'horizontal' ? e.clientX : e.clientY;
    startValRef.current = value;
    setDragging(true);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    const step = e.shiftKey ? 32 : 12;
    if (direction === 'horizontal') {
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        onChange(Math.max(min, Math.min(max, value + (reverse ? step : -step))));
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        onChange(Math.max(min, Math.min(max, value + (reverse ? -step : step))));
      }
    } else {
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        onChange(Math.max(min, Math.min(max, value + (reverse ? step : -step))));
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        onChange(Math.max(min, Math.min(max, value + (reverse ? -step : step))));
      }
    }
  };

  return (
    <div
      role="separator"
      tabIndex={0}
      aria-label={ariaLabel}
      aria-orientation={direction === 'horizontal' ? 'vertical' : 'horizontal'}
      aria-valuenow={value}
      aria-valuemin={min}
      aria-valuemax={max}
      onMouseDown={handleMouseDown}
      onDoubleClick={onReset}
      onKeyDown={handleKeyDown}
      title="Arrasta para redimensionar (duplo clique para repor)"
      className={`shrink-0 transition-colors select-none focus-visible:outline-none ${
        direction === 'horizontal'
          ? 'w-1.5 cursor-col-resize hover:bg-sky-400/35'
          : 'h-1.5 cursor-row-resize hover:bg-sky-400/35'
      } ${dragging ? 'bg-sky-400/50' : 'bg-slate-800/40'}`}
    />
  );
};

