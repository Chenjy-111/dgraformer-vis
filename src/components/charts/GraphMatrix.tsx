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
              return (
                <div
                  key={j}
                  className={`border border-white flex items-center justify-center ${isTarget ? 'ring-1 ring-accent/40' : ''}`}
                  style={{ width: cellSize, height: cellSize, backgroundColor: color(val) }}
                  title={`${variables[i]} → ${variables[j]}: ${val.toFixed(4)}`}
                >
                  {Math.abs(val) > 0.15 ? val.toFixed(2) : ''}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
