export function AttentionHeatmap({
  matrix,
  patchLabel,
  selected,
  onHoverCell,
  onClickCell,
  size = 300,
  title,
}: {
  matrix: number[][];
  patchLabel?: (i: number) => string;
  selected?: { q: number; k: number } | null;
  onHoverCell?: (q: number, k: number) => void;
  onClickCell?: (q: number, k: number) => void;
  size?: number;
  title?: string;
}) {
  const rows = matrix.length;
  const cols = matrix[0]?.length ?? 0;
  const maxVal = Math.max(...matrix.flat(), 0.001);
  const cellSize = Math.max(12, Math.floor((size - 40) / Math.max(rows, cols)));

  return (
    <div>
      {title && <div className="mb-2 text-[12px] font-medium text-ink-600 text-center">{title}</div>}
      <div className="overflow-auto">
        <div className="inline-block">
          <div className="grid gap-px" style={{ gridTemplateColumns: `repeat(${cols}, ${cellSize}px)` }}>
            {matrix.map((row, qi) =>
              row.map((val, ki) => {
                const isSel = selected?.q === qi && selected?.k === ki;
                return (
                  <div
                    key={`${qi}-${ki}`}
                    className={`cursor-crosshair transition ${isSel ? 'ring-1 ring-accent' : ''}`}
                    style={{
                      width: cellSize,
                      height: cellSize,
                      backgroundColor: `rgba(200,80,49,${(val / maxVal).toFixed(2)})`,
                    }}
                    onMouseEnter={() => onHoverCell?.(qi, ki)}
                    onClick={() => onClickCell?.(qi, ki)}
                    title={`Q${qi} K${ki}: ${val.toFixed(4)}`}
                  />
                );
              })
            )}
          </div>
          {patchLabel && (
            <div className="mt-1 flex gap-px" style={{ paddingLeft: 0 }}>
              {Array.from({ length: cols }).map((_, i) => (
                <div key={i} className="text-[9px] text-ink-400 text-center" style={{ width: cellSize }}>
                  {patchLabel(i)}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
