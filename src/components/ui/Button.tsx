import { type ButtonHTMLAttributes, type ReactNode } from 'react';
import { cn } from './cn';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'outline' | 'subtle' | 'ghost';
  size?: 'sm' | 'md';
  icon?: ReactNode;
}

export function Button({ variant = 'outline', size = 'md', icon, className, children, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border font-medium transition-colors focus-ring',
        variant === 'primary' && 'border-accent bg-accent text-white hover:bg-accent/90',
        variant === 'outline' && 'border-line bg-white text-ink-700 hover:bg-ink-50',
        variant === 'subtle' && 'border-transparent text-ink-500 hover:text-ink-700 hover:bg-ink-50',
        variant === 'ghost' && 'border-transparent text-ink-400 hover:text-ink-600',
        size === 'sm' && 'px-2.5 py-1 text-[12.5px]',
        size === 'md' && 'px-4 py-2 text-[13.5px]',
        className
      )}
      {...props}
    >
      {icon}
      {children}
    </button>
  );
}
