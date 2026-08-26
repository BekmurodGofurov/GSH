import React from 'react';
import { cn } from '../../utils/cn';

export function Card({
  children,
  className,
  interactive = false,
  glow = false,
  glowColor = 'cyan',
  ...props
}) {
  const glowStyles = {
    cyan: 'hover:border-cyan-500/40 hover:shadow-glow',
    emerald: 'hover:border-emerald-500/40 hover:shadow-glow-emerald',
    rose: 'hover:border-rose-500/40 hover:shadow-glow-rose',
    violet: 'hover:border-violet-500/40 hover:shadow-glow-violet',
  };

  return (
    <div
      className={cn(
        'relative rounded-xl border border-slate-800/80 bg-slate-900/70 backdrop-blur-md transition-all duration-200 overflow-hidden',
        interactive && 'cursor-pointer hover:bg-slate-800/60',
        interactive && glow && (glowStyles[glowColor] || glowStyles.cyan),
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className, ...props }) {
  return (
    <div
      className={cn('flex items-center justify-between p-4 sm:p-5 border-b border-slate-800/60', className)}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardTitle({ children, className, icon: Icon, ...props }) {
  return (
    <div className={cn('flex items-center gap-2.5 font-semibold text-slate-100', className)} {...props}>
      {Icon && <Icon className="w-5 h-5 text-cyan-400" />}
      <h3>{children}</h3>
    </div>
  );
}

export function CardDescription({ children, className, ...props }) {
  return (
    <p className={cn('text-xs text-slate-400 mt-0.5', className)} {...props}>
      {children}
    </p>
  );
}

export function CardContent({ children, className, ...props }) {
  return (
    <div className={cn('p-4 sm:p-5', className)} {...props}>
      {children}
    </div>
  );
}

export function CardFooter({ children, className, ...props }) {
  return (
    <div
      className={cn('flex items-center justify-between p-4 sm:p-5 border-t border-slate-800/60 bg-slate-950/30', className)}
      {...props}
    >
      {children}
    </div>
  );
}
