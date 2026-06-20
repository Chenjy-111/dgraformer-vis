interface SelectOption<T> {
  value: T;
  label: string;
}

interface SelectProps<T extends string | number> {
  value: T;
  onChange: (value: T) => void;
  options: SelectOption<T>[];
  ariaLabel: string;
}

export function Select<T extends string | number>({ value, onChange, options, ariaLabel }: SelectProps<T>) {
  return (
    <select
      value={String(value)}
      onChange={(e) => {
        const v = options.find((o) => String(o.value) === e.target.value)?.value;
        if (v !== undefined) onChange(v);
      }}
      aria-label={ariaLabel}
      className="w-full rounded-md border border-line bg-white px-2.5 py-1.5 text-[13px] text-ink-900 focus-ring"
    >
      {options.map((opt) => (
        <option key={String(opt.value)} value={String(opt.value)}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}
