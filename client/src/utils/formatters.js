export function formatPing(ping) {
  if (ping === undefined || ping === null) return '-- ms';
  const num = typeof ping === 'number' ? ping : parseFloat(ping);
  if (isNaN(num)) return '-- ms';
  return `${num.toFixed(1)} ms`;
}

export function getPingColorClass(ping) {
  if (ping === undefined || ping === null) return 'text-slate-400';
  const num = typeof ping === 'number' ? ping : parseFloat(ping);
  if (num < 30) return 'text-emerald-400';
  if (num < 75) return 'text-cyan-400';
  if (num < 130) return 'text-amber-400';
  return 'text-rose-400';
}

export function getPingBadgeColor(ping) {
  if (ping === undefined || ping === null) return 'bg-slate-800 text-slate-400 border-slate-700';
  const num = typeof ping === 'number' ? ping : parseFloat(ping);
  if (num < 30) return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
  if (num < 75) return 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30';
  if (num < 130) return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
  return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
}

export function formatTime(timeStr) {
  if (!timeStr) return '--:--:--';
  try {
    const d = new Date(timeStr);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch (e) {
    return timeStr;
  }
}

export function formatRelativeTime(timeStr) {
  if (!timeStr) return 'Never';
  try {
    const d = new Date(timeStr);
    const now = new Date();
    const diffSec = Math.floor((now - d) / 1000);

    if (diffSec < 5) return 'just now';
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHour = Math.floor(diffMin / 60);
    if (diffHour < 24) return `${diffHour}h ago`;
    const diffDay = Math.floor(diffHour / 24);
    return `${diffDay}d ago`;
  } catch (e) {
    return timeStr;
  }
}

export function formatEventBadge(eventType) {
  const type = (eventType || '').toUpperCase();
  switch (type) {
    case 'CRASH':
      return {
        label: 'CRASH',
        variant: 'rose',
        dot: 'bg-rose-500 animate-ping',
        badgeClass: 'bg-rose-500/15 text-rose-400 border-rose-500/40 shadow-glow-rose',
      };
    case 'OFFLINE':
      return {
        label: 'OFFLINE',
        variant: 'rose',
        dot: 'bg-rose-500',
        badgeClass: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
      };
    case 'HIGH_PING':
    case 'WARNING':
      return {
        label: 'WARNING',
        variant: 'amber',
        dot: 'bg-amber-500',
        badgeClass: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
      };
    case 'RECOVERY':
      return {
        label: 'RECOVERY',
        variant: 'emerald',
        dot: 'bg-emerald-500',
        badgeClass: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
      };
    default:
      return {
        label: type || 'EVENT',
        variant: 'cyan',
        dot: 'bg-cyan-500',
        badgeClass: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30',
      };
  }
}
