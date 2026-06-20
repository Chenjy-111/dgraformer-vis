interface Bar {
  label: string;
  value: number;
  highlight: boolean;
  note: string;
}

export function MetricBarChart({
  bars,
  metricLabel,
  selected,
  baselineValue,
  onPick,
}: {
  bars: Bar[];
  metricLabel: string;
  selected: string | null;
  baselineValue: number;
  onPick: (label: string) => void;
}) {
  const maxVal = Math.max(...bars.map((b) => b.value), baselineValue);
  return (
    <div className="space-y-1">
      <div className="mb-2 text-[11px] text-ink-400">{metricLabel}</div>
      {bars.map((b) => (
        <button
          key={b.label}
          onClick={() => onPick(b.label)}
          className={`flex w-full items-center gap-2 rounded px-2 py-1 text-left text-[12.5px] transition hover:bg-ink-50 ${
            selected === b.label ? 'bg-accent/10 ring-1 ring-accent/30' : ''
          }`}
        >
          <span className={`w-24 truncate font-medium ${b.highlight ? 'text-accent' : 'text-ink-700'}`}>
            {b.label}
          </span>
          <span className="flex-1">
            <span
              className={`block h-4 rounded ${b.highlight ? 'bg-accent/40' : 'bg-ink-200'}`}
              style={{ width: `${(b.value / maxVal) * 100}%` }}
            />
          </span>
          <span className="data-num w-14 text-right text-[11px] text-ink-400">{b.value.toFixed(4)}</span>
        </button>
      ))}
    </div>
  );
}
