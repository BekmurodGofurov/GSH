import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  AlertOctagon,
  Activity,
  CheckCircle2,
  Info,
  X,
  Server,
  ExternalLink,
  Flame,
} from 'lucide-react';

function getToastConfig(eventType) {
  const type = (eventType || '').toUpperCase();

  switch (type) {
    case 'CRASH':
      return {
        icon: Flame,
        badgeText: 'CRASH ALERT',
        badgeClass: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/20 dark:text-rose-300 dark:border-rose-500/40',
        cardBorder: 'border-rose-300 dark:border-rose-500/50 shadow-lg dark:shadow-[0_0_25px_rgba(244,63,94,0.25)]',
        bgGradient: 'bg-white dark:bg-slate-950 dark:bg-gradient-to-br dark:from-rose-950/90 dark:via-slate-900/95 dark:to-slate-950',
        progressBar: 'bg-rose-500',
        iconBg: 'bg-rose-100 text-rose-600 border-rose-200 dark:bg-rose-500/20 dark:text-rose-400 dark:border-rose-500/30',
      };
    case 'OFFLINE':
      return {
        icon: AlertOctagon,
        badgeText: 'SERVER OFFLINE',
        badgeClass: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/20 dark:text-rose-300 dark:border-rose-500/40',
        cardBorder: 'border-rose-300 dark:border-rose-500/50 shadow-lg dark:shadow-[0_0_25px_rgba(244,63,94,0.25)]',
        bgGradient: 'bg-white dark:bg-slate-950 dark:bg-gradient-to-br dark:from-rose-950/80 dark:via-slate-900/95 dark:to-slate-950',
        progressBar: 'bg-rose-500',
        iconBg: 'bg-rose-100 text-rose-600 border-rose-200 dark:bg-rose-500/20 dark:text-rose-400 dark:border-rose-500/30',
      };
    case 'HIGH_PING':
    case 'WARNING':
      return {
        icon: Activity,
        badgeText: 'HIGH LATENCY SPIKE',
        badgeClass: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/20 dark:text-amber-300 dark:border-amber-500/40',
        cardBorder: 'border-amber-300 dark:border-amber-500/50 shadow-lg dark:shadow-[0_0_25px_rgba(245,158,11,0.25)]',
        bgGradient: 'bg-white dark:bg-slate-950 dark:bg-gradient-to-br dark:from-amber-950/80 dark:via-slate-900/95 dark:to-slate-950',
        progressBar: 'bg-amber-500',
        iconBg: 'bg-amber-100 text-amber-600 border-amber-200 dark:bg-amber-500/20 dark:text-amber-400 dark:border-amber-500/30',
      };
    case 'RECOVERY':
    case 'ONLINE':
      return {
        icon: CheckCircle2,
        badgeText: 'SERVER RESTORED',
        badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/20 dark:text-emerald-300 dark:border-emerald-500/40',
        cardBorder: 'border-emerald-300 dark:border-emerald-500/50 shadow-lg dark:shadow-[0_0_25px_rgba(16,185,129,0.25)]',
        bgGradient: 'bg-white dark:bg-slate-950 dark:bg-gradient-to-br dark:from-emerald-950/80 dark:via-slate-900/95 dark:to-slate-950',
        progressBar: 'bg-emerald-500',
        iconBg: 'bg-emerald-100 text-emerald-600 border-emerald-200 dark:bg-emerald-500/20 dark:text-emerald-400 dark:border-emerald-500/30',
      };
    default:
      return {
        icon: Info,
        badgeText: 'INCIDENT TELEMETRY',
        badgeClass: 'bg-cyan-50 text-cyan-700 border-cyan-200 dark:bg-cyan-500/20 dark:text-cyan-300 dark:border-cyan-500/40',
        cardBorder: 'border-cyan-300 dark:border-cyan-500/50 shadow-lg dark:shadow-[0_0_25px_rgba(6,182,212,0.25)]',
        bgGradient: 'bg-white dark:bg-slate-950 dark:bg-gradient-to-br dark:from-cyan-950/80 dark:via-slate-900/95 dark:to-slate-950',
        progressBar: 'bg-cyan-500',
        iconBg: 'bg-cyan-100 text-cyan-600 border-cyan-200 dark:bg-cyan-500/20 dark:text-cyan-400 dark:border-cyan-500/30',
      };
  }
}

const TOAST_DURATION_SECONDS = 12;

function ToastItem({ toast, onDismiss, onInspect }) {
  const [isClosing, setIsClosing] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [timeLeft, setTimeLeft] = useState(TOAST_DURATION_SECONDS);
  const config = getToastConfig(toast.event_type);
  const Icon = config.icon;

  const handleClose = () => {
    setIsClosing(true);
    setTimeout(() => {
      onDismiss(toast.id);
    }, 250);
  };

  useEffect(() => {
    if (isPaused || isClosing) return;

    const interval = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          handleClose();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [isPaused, isClosing, toast.id]);

  return (
    <div
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      className={`relative w-full overflow-hidden rounded-xl border backdrop-blur-xl transition-all duration-200 pointer-events-auto ${
        config.bgGradient
      } ${config.cardBorder} ${
        isClosing
          ? 'opacity-0 translate-x-full scale-95'
          : 'animate-toast-in opacity-100'
      }`}
    >
      <div className="p-3.5 sm:p-4">
        {/* Top meta row */}
        <div className="flex items-center justify-between gap-2 mb-2">
          <div className="flex items-center gap-2">
            <div
              className={`w-7 h-7 rounded-lg border flex items-center justify-center ${config.iconBg}`}
            >
              <Icon className="w-4 h-4" />
            </div>
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono tracking-wider uppercase border ${config.badgeClass}`}
            >
              {config.badgeText}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span
              className={`text-[11px] font-mono transition-colors ${
                isPaused ? 'text-cyan-600 dark:text-cyan-300 font-semibold' : 'text-slate-500 dark:text-slate-400'
              }`}
            >
              {isPaused ? '⏸ PAUSED' : `${timeLeft}s`}
            </span>
            <button
              onClick={handleClose}
              className="w-6 h-6 rounded-md flex items-center justify-center text-slate-400 hover:text-slate-700 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800/60 transition-colors cursor-pointer"
              aria-label="Dismiss alert"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Server Details */}
        <div className="mb-1.5">
          <div className="font-semibold text-sm text-slate-900 dark:text-slate-100 line-clamp-1">
            {toast.server_name || toast.server_id || 'CS2 Dedicated Server'}
          </div>
          <div className="flex items-center gap-2 text-[11px] font-mono text-slate-500 dark:text-slate-400">
            <span>{toast.server_id}</span>
            {toast.region && (
              <>
                <span>•</span>
                <span className="text-cyan-600 dark:text-cyan-400 font-medium">{toast.region}</span>
              </>
            )}
          </div>
        </div>

        {/* Message / Reason */}
        <p className="text-xs text-slate-700 dark:text-slate-300 font-mono bg-slate-50 dark:bg-slate-950/60 rounded-lg p-2 border border-slate-200 dark:border-slate-800/80 mb-2 leading-relaxed">
          {toast.message || 'Anomaly detected in server telemetry stream.'}
        </p>

        {/* Actions */}
        {onInspect && toast.server_id && (
          <div className="flex justify-end pt-1">
            <button
              onClick={() => {
                onInspect(toast.server_id);
                handleClose();
              }}
              className="text-xs font-mono text-cyan-600 dark:text-cyan-400 hover:text-cyan-700 dark:hover:text-cyan-300 flex items-center gap-1 transition-colors cursor-pointer font-medium"
            >
              Inspect Node <ExternalLink className="w-3 h-3" />
            </button>
          </div>
        )}
      </div>

      {/* Countdown progress bar */}
      <div className="absolute bottom-0 left-0 right-0 h-1 bg-slate-100 dark:bg-slate-950/80">
        <div
          className={`h-full ${config.progressBar} animate-toast-progress`}
          style={{
            animationDuration: `${TOAST_DURATION_SECONDS}s`,
            animationPlayState: isPaused ? 'paused' : 'running',
          }}
        />
      </div>
    </div>
  );
}

export function ToastContainer({ toasts = [], onDismiss, onInspect }) {
  if (!toasts || toasts.length === 0) return null;

  return (
    <div
      aria-live="assertive"
      className="fixed top-16 sm:top-20 right-4 sm:right-6 z-50 flex flex-col gap-2.5 max-w-sm sm:max-w-md w-full pointer-events-none"
    >
      {toasts.map((toast) => (
        <ToastItem
          key={toast.id}
          toast={toast}
          onDismiss={onDismiss}
          onInspect={onInspect}
        />
      ))}
    </div>
  );
}
