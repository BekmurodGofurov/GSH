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
    emerald: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 shadow-glow-emerald',
    rose: 'bg-rose-500/10 text-rose-400 border-rose-500/30 shadow-glow-rose',
    amber: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    cyan: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30 shadow-glow',
    violet: 'bg-violet-500/10 text-violet-400 border-violet-500/30 shadow-glow-violet',
    neutral: 'bg-slate-800/80 text-slate-300 border-slate-700/60',
  };

  const dotColors = {
    emerald: 'bg-emerald-400',
    rose: 'bg-rose-400',
    amber: 'bg-amber-400',
    cyan: 'bg-cyan-400',
    violet: 'bg-violet-400',
    neutral: 'bg-slate-400',
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
