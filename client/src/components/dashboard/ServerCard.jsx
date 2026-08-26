import React from 'react';
import {
  Wifi,
  Users,
  MapPin,
  Clock,
  ExternalLink,
} from 'lucide-react';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import {
  formatPing,
  getPingBadgeColor,
  formatRelativeTime,
} from '../../utils/formatters';

export function ServerCard({
  server,
  isSelected,
  onSelect,
  onInspect,
}) {
  const isOnline = (server.status || '').toUpperCase() === 'ONLINE';
  const playersRaw = Number(server.player_count);
  const maxPlayersRaw = Number(server.max_players);
  const players = Number.isFinite(playersRaw) && playersRaw >= 0 ? playersRaw : 0;
  const maxPlayers = Number.isFinite(maxPlayersRaw) && maxPlayersRaw > 0 ? maxPlayersRaw : 0;
  const loadPercentage = maxPlayers > 0 ? Math.round((players / maxPlayers) * 100) : 0;

  return (
    <Card
      interactive
      glow
      glowColor={isOnline ? 'cyan' : 'rose'}
      onClick={() => onSelect(server.server_id)}
      className={`border transition-all duration-200 ${
        isSelected
          ? 'border-cyan-500/80 bg-slate-800/80 shadow-glow'
          : isOnline
          ? 'border-slate-800/80 bg-slate-900/60'
          : 'border-rose-950/60 bg-rose-950/10'
      }`}
    >
      <div className="p-4 sm:p-5">
        {/* Top bar: Status + Region */}
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2">
            <Badge
              variant={isOnline ? 'emerald' : 'rose'}
              dot
              pulse={!isOnline}
              size="sm"
            >
              {isOnline ? 'ONLINE' : 'OFFLINE'}
            </Badge>
            <span className="text-[11px] font-mono text-slate-400 flex items-center gap-1 bg-slate-950/60 px-2 py-0.5 rounded border border-slate-800">
              <MapPin className="w-3 h-3 text-cyan-400" />
              {server.region}
            </span>
          </div>

          {/* Ping badge */}
          {isOnline && (
            <span
              className={`text-xs font-mono font-bold px-2 py-0.5 rounded border flex items-center gap-1 ${getPingBadgeColor(
                server.ping_ms
              )}`}
            >
              <Wifi className="w-3 h-3" />
              {formatPing(server.ping_ms)}
            </span>
          )}
        </div>

        {/* Server Name + IP */}
        <div className="mb-4">
          <h4 className="font-bold text-slate-100 text-sm sm:text-base tracking-tight truncate">
            {server.server_name}
          </h4>
          <div className="flex items-center gap-2 mt-1">
            <span className="font-mono text-xs text-slate-400 select-all">
              {server.server_id}
            </span>
            {server.map && (
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-300">
                {server.map}
              </span>
            )}
          </div>
        </div>

        {/* Player Load Bar */}
        <div className="space-y-1.5 mb-4">
          <div className="flex justify-between text-xs font-mono">
            <span className="text-slate-400 flex items-center gap-1">
              <Users className="w-3.5 h-3.5 text-violet-400" /> Player Slots
            </span>
            <span className="text-slate-200 font-semibold">
              {players} / {maxPlayers}{' '}
              <span className="text-slate-500 font-normal">({loadPercentage}%)</span>
            </span>
          </div>

          <div className="h-1.5 w-full bg-slate-950 rounded-full overflow-hidden border border-slate-800">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                isOnline
                  ? loadPercentage > 90
                    ? 'bg-amber-400'
                    : 'bg-gradient-to-r from-violet-500 to-cyan-400'
                  : 'bg-slate-700'
              }`}
              style={{ width: `${isOnline ? loadPercentage : 0}%` }}
            />
          </div>
        </div>

        {/* Bottom meta & Action */}
        <div className="flex items-center justify-between pt-3 border-t border-slate-800/80 text-[11px] font-mono text-slate-400">
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3 text-slate-400" />
            {isOnline
              ? `Online ${formatRelativeTime(server.last_online_at)}`
              : `Down ${formatRelativeTime(server.last_offline_at)}`}
          </span>

          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              onInspect(server);
            }}
            className="text-cyan-400 hover:text-cyan-300 text-xs py-1 px-2 h-auto"
          >
            Inspect <ExternalLink className="w-3 h-3 ml-1" />
          </Button>
        </div>
      </div>
    </Card>
  );
}
