import React from 'react';
import {
  AlertTriangle,
  RefreshCw,
  CheckCircle2,
  WifiOff,
  Radio,
  Clock,
} from 'lucide-react';
import { Button } from './Button';
import { formatRelativeTime } from '../../utils/formatters';

export function ConnectionBanner({
  isOffline,
  wsStatus,
  retryCountdown,
  justReconnected,
  onRetry,
  lastSyncTime,
}) {
  // If reconnected just now, display temporary green toast banner
  if (justReconnected) {
    return (
      <div className="bg-emerald-500/15 border-b border-emerald-500/40 text-emerald-300 px-4 py-2.5 shadow-glow-emerald transition-all duration-300 animate-fade-in flex items-center justify-between text-xs font-mono">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 animate-bounce" />
          <span className="font-bold">LIVE TELEMETRY RESTORED:</span>
          <span>Successfully reconnected to Gateway API and live WebSocket feed.</span>
        </div>
        <span className="text-[11px] text-emerald-400/80 hidden sm:inline">
          Syncing latest ticks...
        </span>
      </div>
    );
  }

  // If online and not just reconnected, do not display banner
  if (!isOffline) return null;

  const isReconnecting = wsStatus === 'reconnecting';

  return (
    <div className="bg-amber-950/80 border-b border-amber-500/30 text-amber-200 px-4 py-2.5 backdrop-blur-md transition-all duration-300 flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
      <div className="flex items-center gap-2.5">
        <div className="p-1 rounded-md bg-amber-500/20 text-amber-400 border border-amber-500/30">
          <WifiOff className="w-3.5 h-3.5" />
        </div>
        <span className="font-bold text-amber-300">⚠️ OFFLINE MODE:</span>
        <span className="text-slate-200">
          Gateway API connection lost. Displaying cached telemetry snapshot
          {lastSyncTime ? ` (cached ${formatRelativeTime(lastSyncTime)})` : ''}.
        </span>
      </div>

      <div className="flex items-center gap-3 ml-auto">
        <span className="text-amber-400/90 font-medium">
          {retryCountdown > 0 ? (
            <>Reconnecting in <strong className="text-amber-300 font-bold">{retryCountdown}s</strong>...</>
          ) : (
            'Attempting connection...'
          )}
        </span>

        <Button
          variant="outline"
          size="sm"
          onClick={onRetry}
          icon={RefreshCw}
          loading={isReconnecting}
          className="text-xs py-1 px-2.5 h-7 border-amber-500/40 text-amber-300 hover:bg-amber-500/20"
        >
          Retry Now
        </Button>
      </div>
    </div>
  );
}
