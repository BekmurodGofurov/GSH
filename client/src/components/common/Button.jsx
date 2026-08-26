import React from 'react';
import { cn } from '../../utils/cn';

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  icon: Icon,
  iconPosition = 'left',
  loading = false,
  disabled = false,
  className,
  ...props
}) {
  const variants = {
    primary:
      'bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold shadow-glow hover:shadow-cyan-500/30 border border-cyan-400/50',
    secondary:
      'bg-violet-600 hover:bg-violet-500 text-white font-medium shadow-glow-violet border border-violet-500/50',
    outline:
      'bg-slate-800/60 hover:bg-slate-700/80 text-slate-200 border border-slate-700 hover:border-cyan-500/50',
    ghost:
      'bg-transparent hover:bg-slate-800/60 text-slate-300 hover:text-slate-100 border border-transparent',
    danger:
      'bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 hover:text-rose-200 border border-rose-500/40 shadow-glow-rose',
    emerald:
      'bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 hover:text-emerald-200 border border-emerald-500/40 shadow-glow-emerald',
  };

  const sizes = {
    sm: 'px-2.5 py-1.5 text-xs rounded-lg gap-1.5',
    md: 'px-3.5 py-2 text-sm rounded-lg gap-2',
    lg: 'px-5 py-2.5 text-base rounded-xl gap-2.5',
    icon: 'p-2 rounded-lg',
  };

  return (
    <button
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center font-medium transition-all duration-150 active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none disabled:active:scale-100 select-none cursor-pointer',
        variants[variant] || variants.primary,
        sizes[size] || sizes.md,
        className
      )}
      {...props}
    >
      {loading ? (
        <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : (
        <>
          {Icon && iconPosition === 'left' && <Icon className="w-4 h-4 flex-shrink-0" />}
          {children}
          {Icon && iconPosition === 'right' && <Icon className="w-4 h-4 flex-shrink-0" />}
        </>
      )}
    </button>
  );
}
