export function SensitivityLineChart({
  x,
  mse,
  mae,
  best,
  xLabel,
  showMse,
  showMae,
}: {
  x: number[];
  mse: number[];
  mae: number[];
  best: number;
  xLabel: string;
  showMse: boolean;
  showMae: boolean;
}) {
  const allVals = [...(showMse ? mse : []), ...(showMae ? mae : [])];
  const minVal = Math.min(...allVals);
  const maxVal = Math.max(...allVals);
  const range = maxVal - minVal || 1;
  const norm = (v: number) => ((v - minVal) / range) * 80;

  return (
    <div className="card p-4">
      <div className="eyebrow mb-3">{xLabel}</div>
      <svg viewBox="0 0 400 120" className="w-full">
        {/* Best marker */}
        <line
          x1={0}
          y1={100 - norm(best)}
          x2={400}
          y2={100 - norm(best)}
          stroke="#94a3b8"
          strokeDasharray="4 2"
          strokeWidth={1}
        />
        <text x={4} y={100 - norm(best) - 4} fontSize={9} fill="#94a3b8">
          best {best.toFixed(3)}
        </text>
        {/* Lines */}
        {showMse && (
          <polyline
            fill="none"
            stroke="#c85031"
            strokeWidth={2}
            points={x.map((xi, i) => `${(i / (x.length - 1)) * 380 + 10},${100 - norm(mse[i])}`).join(' ')}
          />
        )}
        {showMae && (
          <polyline
            fill="none"
            stroke="#2563eb"
            strokeWidth={2}
            strokeDasharray="4 2"
            points={x.map((xi, i) => `${(i / (x.length - 1)) * 380 + 10},${100 - norm(mae[i])}`).join(' ')}
          />
        )}
        {/* X labels */}
        {x.map((xi, i) => (
          <text key={i} x={(i / (x.length - 1)) * 380 + 10} y={115} fontSize={8} fill="#94a3b8" textAnchor="middle">
            {xi}
          </text>
        ))}
      </svg>
      <div className="mt-2 flex gap-4 text-[11px]">
        {showMse && <span className="text-[#c85031]">— MSE</span>}
        {showMae && <span className="text-[#2563eb]">--- MAE</span>}
      </div>
    </div>
  );
}
