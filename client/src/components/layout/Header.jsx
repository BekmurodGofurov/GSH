import React from 'react';
import {
  RefreshCw,
  Volume2,
  VolumeX,
  Radio,
  Search,
  Globe2,
} from 'lucide-react';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { Input } from '../common/Input';
import { formatTime } from '../../utils/formatters';

export function Header({
  wsStatus,
  retryCountdown,
  isRefreshing,
  lastSyncTime,
  onRefresh,
  audio,
  searchQuery,
  onSearchChange,
  kpis,
}) {
  const isWsConnected = wsStatus === 'connected';

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between px-4 lg:px-8 py-3.5 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-xl">
      {/* Left side: Brand + Mobile Logo + Status indicator */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 shadow-glow text-slate-950 font-black">
            <Radio className="w-5 h-5 text-slate-950 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-sm sm:text-base tracking-wider uppercase bg-gradient-to-r from-cyan-400 via-sky-300 to-indigo-400 bg-clip-text text-transparent">
                CS2 PULSE
              </span>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/50">
                EU EAST OPS
              </span>
            </div>
            <p className="text-[11px] text-slate-400 hidden sm:block">
              Valve Dedicated Server Telemetry & Incident Monitor
            </p>
          </div>
        </div>

        {/* Global Live WebSocket Status Badge */}
        <div className="hidden md:flex items-center gap-2 pl-4 border-l border-slate-800">
          {isWsConnected ? (
            <Badge variant="emerald" dot pulse size="sm">
              WS STREAM LIVE
            </Badge>
          ) : wsStatus === 'reconnecting' ? (
            <Badge variant="amber" dot pulse size="sm">
              {retryCountdown > 0 ? `RECONNECTING (${retryCountdown}s)` : 'RECONNECTING...'}
            </Badge>
          ) : (
            <Badge variant="rose" dot size="sm">
              GATEWAY OFFLINE
            </Badge>
          )}
        </div>
      </div>

      {/* Center Search Input */}
      <div className="hidden lg:block w-72">
        <Input
          icon={Search}
          placeholder="Filter servers, IPs, regions..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          clearable
          onClear={() => onSearchChange('')}
          className="h-9 text-xs"
        />
      </div>

      {/* Right side Actions */}
      <div className="flex items-center gap-2.5">
        {/* Last sync time */}
        <div className="hidden xl:flex flex-col items-end mr-2 text-[11px] font-mono">
          <span className="text-slate-400">LAST SYNC</span>
          <span className="text-cyan-400 font-semibold">
            {lastSyncTime ? formatTime(lastSyncTime) : 'Never'}
          </span>
        </div>

        {/* Audio Mute/Unmute Toggle */}
        <Button
          variant="outline"
          size="sm"
          onClick={audio.toggleMute}
          title={audio.isMuted ? 'Unmute Audio Alerts' : 'Mute Audio Alerts'}
          className={audio.isMuted ? 'text-slate-500' : 'text-cyan-400 border-cyan-500/30'}
        >
          {audio.isMuted ? (
            <VolumeX className="w-4 h-4" />
          ) : (
            <Volume2 className="w-4 h-4" />
          )}
        </Button>

        {/* Quick Refresh Button */}
        <Button
          variant="outline"
          size="sm"
          onClick={onRefresh}
          loading={isRefreshing}
          icon={RefreshCw}
          title="Refresh telemetry snapshot"
        >
          <span className="hidden sm:inline">Refresh</span>
        </Button>

        {/* Live Cluster Quick Stat */}
        <div className="hidden sm:flex items-center gap-2 pl-3 py-1 pr-2 rounded-lg bg-slate-900/90 border border-slate-800 text-xs font-mono">
          <Globe2 className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-slate-300">
            <strong className="text-emerald-400">{kpis.onlineServers}</strong>/{kpis.totalServers} Nodes
          </span>
        </div>
      </div>
    </header>
  );
}
