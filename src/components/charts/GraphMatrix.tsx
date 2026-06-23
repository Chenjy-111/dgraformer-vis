import { useState, useCallback } from 'react';

export function GraphMatrix({
  variables,
  matrix,
  diverging,
  target,
  size = 300,
}: {
  variables: string[];
  matrix: number[][];
  diverging?: boolean;
  target?: number;
  size?: number;
}) {
  const N = variables.length;
  const cellSize = Math.max(16, Math.min(40, Math.floor((size - 60) / N)));
  const maxAbs = Math.max(...matrix.flat().map(Math.abs), 0.001);

  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);

  const show = useCallback((e: React.MouseEvent, text: string) => {
    setTip({ x: e.clientX + 10, y: e.clientY - 8, text });
  }, []);
  const move = useCallback((e: React.MouseEvent) => {
    setTip((t) => (t ? { ...t, x: e.clientX + 10, y: e.clientY - 8 } : null));
  }, []);
  const hide = useCallback(() => setTip(null), []);

  function color(v: number) {
    if (diverging) {
      if (v > 0) return `rgba(200,80,49,${(v / maxAbs).toFixed(2)})`;
      if (v < 0) return `rgba(37,99,235,${(-v / maxAbs).toFixed(2)})`;
      return '#f1f5f9';
    }
    const alpha = Math.abs(v) / maxAbs;
    return `rgba(200,80,49,${alpha.toFixed(2)})`;
  }

  return (
    <div className="overflow-auto text-[10px]">
      <div className="inline-block">
        {Array.from({ length: N }).map((_, i) => (
          <div key={i} className="flex">
            {Array.from({ length: N }).map((_, j) => {
              const val = matrix[i]?.[j] ?? 0;
              const isTarget = target !== undefined && (i === target || j === target);
              const label = `${variables[i]} → ${variables[j]}: ${val.toFixed(4)}`;
              return (
                <div
                  key={j}
                  className={`flex items-center justify-center ${isTarget ? 'ring-2 ring-amber-500/60' : ''}`}
                  style={{ width: cellSize, height: cellSize, backgroundColor: color(val) }}
                  onMouseEnter={(e) => show(e, label)}
                  onMouseMove={move}
                  onMouseLeave={hide}
                >
                  {Math.abs(val) > 0.15 ? val.toFixed(2) : ''}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {tip && (
        <div
          className="pointer-events-none fixed z-50 rounded bg-ink-900 px-2 py-1 text-[11px] text-white shadow-lg"
          style={{ left: tip.x, top: tip.y }}
        >
          {tip.text}
        </div>
      )}
    </div>
  );
}
