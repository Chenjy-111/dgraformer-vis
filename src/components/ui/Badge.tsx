import { type ReactNode } from 'react';
import { cn } from './cn';

interface BadgeProps {
  children: ReactNode;
  tone?: 'neutral' | 'kept' | 'filtered' | 'warn' | 'accent';
  className?: string;
}

const TONE_CLASS: Record<string, string> = {
  neutral: 'bg-ink-100 text-ink-600',
  kept: 'bg-green-100 text-green-700',
  filtered: 'bg-red-100 text-red-600',
  warn: 'bg-amber-100 text-amber-700',
  accent: 'bg-accent/10 text-accent',
};

export function Badge({ children, tone = 'neutral', className }: BadgeProps) {
  return (
    <span className={cn('inline-block rounded px-1.5 py-0.5 text-[11px] font-medium', TONE_CLASS[tone], className)}>
      {children}
    </span>
  );
}
