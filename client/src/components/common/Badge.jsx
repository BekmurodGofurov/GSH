import React from 'react';
import { cn } from '../../utils/cn';

export function Badge({
  children,
  variant = 'neutral',
  size = 'md',
  dot = false,
  pulse = false,
  className,
  ...props
}) {
  const variants = {
    emerald:
      'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/30 dark:shadow-glow-emerald',
    rose:
      'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:text-rose-400 dark:border-rose-500/30 dark:shadow-glow-rose',
    amber:
      'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/30',
    cyan:
      'bg-cyan-50 text-cyan-700 border-cyan-200 dark:bg-cyan-500/10 dark:text-cyan-400 dark:border-cyan-500/30 dark:shadow-glow',
    violet:
      'bg-violet-50 text-violet-700 border-violet-200 dark:bg-violet-500/10 dark:text-violet-400 dark:border-violet-500/30 dark:shadow-glow-violet',
    neutral:
      'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800/80 dark:text-slate-300 dark:border-slate-700/60',
  };

  const dotColors = {
    emerald: 'bg-emerald-500 dark:bg-emerald-400',
    rose: 'bg-rose-500 dark:bg-rose-400',
    amber: 'bg-amber-500 dark:bg-amber-400',
    cyan: 'bg-cyan-500 dark:bg-cyan-400',
    violet: 'bg-violet-500 dark:bg-violet-400',
    neutral: 'bg-slate-500 dark:bg-slate-400',
  };

  const sizes = {
    sm: 'px-2 py-0.5 text-xs font-mono',
    md: 'px-2.5 py-1 text-xs font-mono font-medium',
    lg: 'px-3 py-1.5 text-sm font-mono font-semibold',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border transition-all select-none',
        variants[variant] || variants.neutral,
        sizes[size] || sizes.md,
        className
      )}
      {...props}
    >
      {dot && (
        <span className="relative flex h-2 w-2">
          {pulse && (
            <span
              className={cn(
                'absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping',
                dotColors[variant] || 'bg-slate-400'
              )}
            />
          )}
          <span
            className={cn(
              'relative inline-flex rounded-full h-2 w-2',
              dotColors[variant] || 'bg-slate-400'
            )}
          />
        </span>
      )}
      {children}
    </span>
  );
}
