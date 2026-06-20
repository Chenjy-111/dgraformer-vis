export function ErrorTimeline({
  error,
  onPick,
  selected,
  peaks,
}: {
  error: number[];
  onPick: (step: number) => void;
  selected: number | null;
  peaks: number[];
}) {
  const maxErr = Math.max(...error, 0.001);
  const peakSet = new Set(peaks);
  return (
    <div className="card p-3">
      <div className="eyebrow mb-2">Error over prediction horizon</div>
      <div className="flex items-end gap-[2px]" style={{ height: 100 }}>
        {error.map((v, i) => (
          <button
            key={i}
            onClick={() => onPick(i)}
            title={`step ${i}: ${v.toFixed(4)}`}
            className={`flex-1 rounded-t transition hover:opacity-80 ${
              i === selected ? 'bg-accent' : peakSet.has(i) ? 'bg-amber-400' : 'bg-ink-200'
            }`}
            style={{ height: `${(v / maxErr) * 100}%` }}
          />
        ))}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-ink-400">
        <span>step 0</span>
        <span>step {error.length - 1}</span>
      </div>
    </div>
  );
}
