import React from 'react';
import {
  RefreshCw,
  Radio,
  Search,
  Globe2,
  Sun,
  Moon,
  Bell,
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
  searchQuery,
  onSearchChange,
  kpis,
  theme,
  toggleTheme,
  onOpenNotifications,
  unreadCount,
}) {
  const isWsConnected = wsStatus === 'connected';

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between px-4 lg:px-8 py-3.5 border-b border-slate-200/80 dark:border-slate-800/80 bg-white/80 dark:bg-slate-950/80 backdrop-blur-xl">
      {/* Left side: Brand + Mobile Logo + Status indicator */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 shadow-glow text-white font-black">
            <Radio className="w-5 h-5 text-white animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-sm sm:text-base tracking-wider uppercase bg-gradient-to-r from-cyan-600 via-sky-600 to-indigo-600 dark:from-cyan-400 dark:via-sky-300 dark:to-indigo-400 bg-clip-text text-transparent">
                CS2 PULSE
              </span>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-cyan-50 dark:bg-cyan-950/80 text-cyan-700 dark:text-cyan-400 border border-cyan-200 dark:border-cyan-800/50 font-bold">
                EU EAST OPS
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 hidden sm:block">
              Valve Dedicated Server Telemetry & Incident Monitor
            </p>
          </div>
        </div>

        {/* Global Live WebSocket Status Badge */}
        <div className="hidden md:flex items-center gap-2 pl-4 border-l border-slate-200 dark:border-slate-800">
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
          <span className="text-slate-500 dark:text-slate-400">LAST SYNC</span>
          <span className="text-cyan-700 dark:text-cyan-400 font-semibold">
            {lastSyncTime ? formatTime(lastSyncTime) : 'Never'}
          </span>
        </div>

        {/* Dark / Light Mode Toggle */}
        <Button
          variant="outline"
          size="sm"
          onClick={toggleTheme}
          title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          className="text-slate-600 dark:text-slate-400 hover:text-amber-500 dark:hover:text-yellow-300"
        >
          {theme === 'dark' ? (
            <Sun className="w-4 h-4" />
          ) : (
            <Moon className="w-4 h-4" />
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
        <div className="hidden sm:flex items-center gap-2 pl-3 py-1 pr-2 rounded-lg bg-slate-100/90 dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 text-xs font-mono">
          <Globe2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
          <span className="text-slate-700 dark:text-slate-300">
            <strong className="text-emerald-600 dark:text-emerald-400">{kpis.onlineServers}</strong>/{kpis.totalServers} Nodes
          </span>
        </div>

        {/* Notifications Toggle */}
        <Button
          variant="outline"
          size="sm"
          onClick={onOpenNotifications}
          className="relative text-slate-600 dark:text-slate-400 hover:text-cyan-600 dark:hover:text-cyan-400"
          title="Notifications"
        >
          {unreadCount > 0 ? (
            <>
              <Bell className="w-4 h-4 text-cyan-600 dark:text-cyan-400 animate-bounce" />
              <span className="absolute -top-1 -right-1 flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-cyan-500"></span>
              </span>
            </>
          ) : (
            <Bell className="w-4 h-4" />
          )}
        </Button>
      </div>
    </header>
  );
}
