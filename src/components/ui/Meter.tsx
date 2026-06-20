interface MeterProps {
  value: number; // 0..1
  label: string;
}

export function Meter({ value, label }: MeterProps) {
  const pct = Math.round(value * 100);
  return (
    <div>
      <div className="mb-0.5 flex justify-between text-[11px] text-ink-400">
        <span>{label}</span>
        <span className="data-num">{pct}%</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-ink-100">
        <div
          className="h-full rounded-full bg-accent transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
