import { cn } from './cn';

interface TabOption<T> {
  value: T;
  label: string;
}

interface TabsProps<T extends string | number> {
  value: T;
  onChange: (value: T) => void;
  options: TabOption<T>[];
  size?: 'sm' | 'md';
  wrap?: boolean;
}

export function Tabs<T extends string | number>({ value, onChange, options, size = 'md', wrap }: TabsProps<T>) {
  return (
    <div className={cn('flex gap-1', wrap && 'flex-wrap')}>
      {options.map((opt) => (
        <button
          key={String(opt.value)}
          onClick={() => onChange(opt.value)}
          className={cn(
            'rounded-md border font-medium transition-colors',
            size === 'sm' && 'px-2 py-1 text-[11.5px]',
            size === 'md' && 'px-3 py-1.5 text-[13px]',
            String(opt.value) === String(value)
              ? 'border-accent bg-accent/10 text-accent'
              : 'border-line bg-white text-ink-500 hover:bg-ink-50'
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
