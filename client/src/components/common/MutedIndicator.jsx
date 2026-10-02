import React from 'react';
import { BellOff } from 'lucide-react';

/** True while the server has an active alert silence. */
export function isMuted(server) {
  if (!server?.muted_until) return false;
  const until = new Date(server.muted_until).getTime();
  return Number.isNaN(until) ? true : until > Date.now();
}

function describe(server) {
  const until = new Date(server.muted_until);
  if (Number.isNaN(until.getTime())) return 'Alerts muted';
  return `Alerts muted until ${until.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })}`;
}

/**
 * A small bell-with-a-slash that appears only while a server's alerts are
 * muted -- whether the mute came from the admin page or from the agent.
 * Renders nothing otherwise, so callers can drop it in unconditionally.
 */
export function MutedIndicator({ server, withLabel = false, className = '' }) {
  if (!isMuted(server)) return null;
  const title = describe(server);
  return (
    <span
      title={title}
      aria-label={title}
      data-testid="muted-indicator"
      className={`inline-flex items-center gap-1 text-[10px] font-mono font-semibold text-amber-600 dark:text-amber-400 bg-amber-100 dark:bg-amber-500/10 border border-amber-300 dark:border-amber-500/30 rounded px-1.5 py-0.5 ${className}`}
    >
      <BellOff className="w-3 h-3" />
      {withLabel && <span>MUTED</span>}
    </span>
  );
}
