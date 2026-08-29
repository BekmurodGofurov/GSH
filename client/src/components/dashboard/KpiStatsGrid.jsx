import React from 'react';
import {
  Server,
  Users,
  ShieldCheck,
  TrendingDown,
  Wifi,
} from 'lucide-react';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';
import { getPingColorClass } from '../../utils/formatters';

export function KpiStatsGrid({ kpis }) {
  const playerPercentage =
    kpis.maxCapacity > 0
      ? Math.round((kpis.totalPlayers / kpis.maxCapacity) * 100)
      : 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 lg:gap-5">
      {/* 1. Online Servers */}
      <Card className="p-5 border-emerald-200 dark:border-emerald-500/20 bg-gradient-to-br from-white via-white to-emerald-50/60 dark:from-slate-900/90 dark:to-emerald-950/10 shadow-xs dark:shadow-none">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-mono text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Server className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
              ONLINE SERVERS
            </p>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-black font-mono tracking-tight text-slate-900 dark:text-slate-100">
                {kpis.onlineServers}
              </span>
              <span className="text-sm font-mono text-slate-500 dark:text-slate-400 font-medium">
                / {kpis.totalServers}
              </span>
            </div>
          </div>
          <Badge
            variant={kpis.offlineServers === 0 ? 'emerald' : 'rose'}
            dot
            pulse={kpis.offlineServers > 0}
            size="sm"
          >
            {kpis.offlineServers === 0 ? 'ALL NODES UP' : `${kpis.offlineServers} OFFLINE`}
          </Badge>
        </div>

        {/* Mini progress track */}
        <div className="mt-4">
          <div className="flex justify-between text-[11px] font-mono text-slate-500 dark:text-slate-400 mb-1">
            <span>Cluster Availability</span>
            <span className="text-emerald-600 dark:text-emerald-400 font-semibold">{kpis.uptimePercentage}%</span>
          </div>
          <div className="h-1.5 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-emerald-500 to-teal-400 rounded-full transition-all duration-500"
              style={{ width: `${kpis.uptimePercentage}%` }}
            />
          </div>
        </div>
      </Card>

      {/* 2. Average Ping */}
      <Card className="p-5 border-cyan-200 dark:border-cyan-500/20 bg-gradient-to-br from-white via-white to-cyan-50/60 dark:from-slate-900/90 dark:to-cyan-950/10 shadow-xs dark:shadow-none">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-mono text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Wifi className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400" />
              AVG NETWORK PING
            </p>
            <div className="mt-2 flex items-baseline gap-2">
              <span className={`text-3xl font-black font-mono tracking-tight ${getPingColorClass(kpis.avgPing)}`}>
                {kpis.avgPing}
              </span>
              <span className="text-sm font-mono text-slate-500 dark:text-slate-400">ms</span>
            </div>
          </div>
          <Badge
            variant={kpis.avgPing < 40 ? 'cyan' : kpis.avgPing < 80 ? 'amber' : 'rose'}
            size="sm"
          >
            {kpis.avgPing < 30 ? 'OPTIMAL' : kpis.avgPing < 75 ? 'NOMINAL' : 'LATENCY SPIKE'}
          </Badge>
        </div>

        <div className="mt-4 flex items-center justify-between text-[11px] font-mono text-slate-500 dark:text-slate-400 pt-2 border-t border-slate-100 dark:border-slate-800/80">
          <span>Target Threshold: &lt;50ms</span>
          <span className="text-cyan-700 dark:text-cyan-400 flex items-center gap-1 font-medium">
            <TrendingDown className="w-3 h-3 text-emerald-600 dark:text-emerald-400" /> Nominal
          </span>
        </div>
      </Card>

      {/* 3. Total Active Players */}
      <Card className="p-5 border-violet-200 dark:border-violet-500/20 bg-gradient-to-br from-white via-white to-violet-50/60 dark:from-slate-900/90 dark:to-violet-950/10 shadow-xs dark:shadow-none">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-mono text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Users className="w-3.5 h-3.5 text-violet-600 dark:text-violet-400" />
              ACTIVE PLAYERS
            </p>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-black font-mono tracking-tight text-slate-900 dark:text-slate-100">
                {kpis.totalPlayers}
              </span>
              <span className="text-sm font-mono text-slate-500 dark:text-slate-400">
                / {kpis.maxCapacity} slots
              </span>
            </div>
          </div>
          <Badge variant="violet" size="sm">
            {playerPercentage}% LOAD
          </Badge>
        </div>

        <div className="mt-4">
          <div className="flex justify-between text-[11px] font-mono text-slate-500 dark:text-slate-400 mb-1">
            <span>Fleet Capacity</span>
            <span className="text-violet-700 dark:text-violet-400 font-semibold">{playerPercentage}%</span>
          </div>
          <div className="h-1.5 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 rounded-full transition-all duration-500"
              style={{ width: `${playerPercentage}%` }}
            />
          </div>
        </div>
      </Card>

      {/* 4. Health Index */}
      <Card className="p-5 border-slate-200 dark:border-slate-700/60 bg-gradient-to-br from-white via-white to-slate-100/70 dark:from-slate-900/90 dark:to-slate-950 shadow-xs dark:shadow-none">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-mono text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400" />
              SYSTEM HEALTH INDEX
            </p>
            <div className="mt-2 flex items-baseline gap-2">
              <span className={`text-3xl font-black font-mono tracking-tight ${kpis.healthIndex > 80 ? 'text-emerald-600 dark:text-emerald-400' : kpis.healthIndex > 60 ? 'text-amber-600 dark:text-amber-400' : 'text-rose-600 dark:text-rose-400'}`}>
                {kpis.healthIndex}%
              </span>
            </div>
          </div>
          <Badge
            variant={kpis.healthIndex >= 90 ? 'emerald' : kpis.healthIndex >= 70 ? 'amber' : 'rose'}
            dot
            size="sm"
          >
            {kpis.healthIndex >= 90 ? 'HEALTHY' : kpis.healthIndex >= 70 ? 'DEGRADED' : 'CRITICAL'}
          </Badge>
        </div>

        <div className="mt-4 flex items-center justify-between text-[11px] font-mono text-slate-500 dark:text-slate-400 pt-2 border-t border-slate-100 dark:border-slate-800/80">
          <span>Telemetry Protocol</span>
          <span className="text-slate-700 dark:text-slate-200 font-medium">UDP / A2S 128T</span>
        </div>
      </Card>
    </div>
  );
}
