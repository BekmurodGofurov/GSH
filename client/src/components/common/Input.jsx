import React from 'react';
import { cn } from '../../utils/cn';

export function Input({
  icon: Icon,
  className,
  wrapperClassName,
  clearable = false,
  onClear,
  value,
  ...props
}) {
  return (
    <div className={cn('relative flex items-center', wrapperClassName)}>
      {Icon && (
        <Icon className="absolute left-3 w-4 h-4 text-slate-400 pointer-events-none" />
      )}
      <input
        value={value}
        className={cn(
          'w-full bg-slate-900/90 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 transition-all outline-none focus:border-cyan-500/80 focus:ring-1 focus:ring-cyan-500/30 font-sans',
          Icon && 'pl-9',
          clearable && value && 'pr-8',
          className
        )}
        {...props}
      />
      {clearable && value && onClear && (
        <button
          type="button"
          onClick={onClear}
          className="absolute right-2.5 text-slate-400 hover:text-slate-200 text-xs px-1"
        >
          ✕
        </button>
      )}
    </div>
  );
}

export function Select({
  icon: Icon,
  options = [],
  className,
  ...props
}) {
  return (
    <div className="relative flex items-center">
      {Icon && (
        <Icon className="absolute left-3 w-4 h-4 text-slate-400 pointer-events-none" />
      )}
      <select
        className={cn(
          'bg-slate-900/90 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-500/80 focus:ring-1 focus:ring-cyan-500/30 cursor-pointer appearance-none pr-8 font-mono',
          Icon && 'pl-9',
          className
        )}
        {...props}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value} className="bg-slate-900 text-slate-200">
            {opt.label}
          </option>
        ))}
      </select>
      <span className="absolute right-3 pointer-events-none text-slate-400 text-xs">▼</span>
    </div>
  );
}
