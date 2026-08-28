import React from 'react';
import { TrendingUp, Users, Zap, RefreshCw, AlertTriangle, CheckCircle } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../common/Card';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';

// --- Utility helpers ---

function shortName(name = '') {
  // Keep name under 40 chars for display
  return name.length > 42 ? name.slice(0, 40) + '…' : name;
}

function pingColor(ms) {
  if (!ms || ms === 0) return 'text-slate-400';
  if (ms < 40) return 'text-emerald-400';
  if (ms < 80) return 'text-cyan-400';
  if (ms < 140) return 'text-amber-400';
  return 'text-rose-400';
}

function restartColor(count) {
  if (count === 0) return 'text-emerald-400';
  if (count <= 2) return 'text-amber-400';
  return 'text-rose-400';
}

function restartBadgeVariant(count) {
  if (count === 0) return 'emerald';
  if (count <= 2) return 'amber';
  return 'rose';
}

// --- Bar component for player fill ratio ---
function FillBar({ value, max, color = 'bg-cyan-500' }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="w-full h-1.5 rounded-full bg-slate-800 dark:bg-slate-800 overflow-hidden">
      <div
        className={`h-full rounded-full ${color} transition-all duration-500`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

// ============================================================
// SECTION 1 — Server Restarts Today
// ============================================================
function RestartsSection({ restarts, loading }) {
  const displayed = restarts.slice(0, 15);

  return (
    <Card>
      <CardHeader>
        <CardTitle icon={AlertTriangle}>Server Restarts (Last 24h)</CardTitle>
        <span className="text-xs text-slate-400 dark:text-slate-400 font-mono">
          Offline events from <code>server_events</code>
        </span>
      </CardHeader>
      <CardContent className="p-0">
        {loading ? (
          <div className="flex items-center justify-center h-28 text-slate-500 text-sm">Loading…</div>
        ) : displayed.length === 0 ? (
          <div className="flex items-center justify-center h-28 text-slate-500 text-sm">No data yet</div>
        ) : (
          <div className="divide-y divide-slate-800/60">
            {displayed.map((row, i) => {
              const count = Number(row.restart_count) || 0;
              return (
                <div
                  key={row.server_id}
                  className="flex items-center justify-between px-5 py-3 hover:bg-slate-800/30 transition-colors"
                >
                  {/* Rank + Name */}
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-[11px] font-mono text-slate-500 w-5 text-right shrink-0">
                      {i + 1}
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-100 dark:text-slate-100 truncate leading-tight">
                        {shortName(row.server_name)}
                      </p>
                      <p className="text-[11px] text-slate-500 font-mono mt-0.5">{row.region}</p>
                    </div>
                  </div>

                  {/* Count badge */}
                  <div className="flex items-center gap-2 shrink-0 ml-4">
                    {count === 0 ? (
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                      <AlertTriangle className={`w-3.5 h-3.5 ${restartColor(count)}`} />
                    )}
                    <Badge variant={restartBadgeVariant(count)} size="sm" className="font-mono font-bold w-10 text-center">
                      {count}x
                    </Badge>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================
// SECTION 2 — Busiest Servers
// ============================================================
function BusySection({ busy, loading }) {
  const displayed = busy.filter((r) => Number(r.avg_players) > 0).slice(0, 12);
  const maxAvg = displayed.length > 0 ? Math.max(...displayed.map((r) => Number(r.avg_players))) : 1;

  return (
    <Card>
      <CardHeader>
        <CardTitle icon={Users}>Busiest Servers (Last 24h)</CardTitle>
        <span className="text-xs text-slate-400 font-mono">
          Avg &amp; peak from <code>server_metrics</code>
        </span>
      </CardHeader>
      <CardContent className="p-0">
        {loading ? (
          <div className="flex items-center justify-center h-28 text-slate-500 text-sm">Loading…</div>
        ) : displayed.length === 0 ? (
          <div className="flex items-center justify-center h-28 text-slate-500 text-sm">No player data yet</div>
        ) : (
          <div className="divide-y divide-slate-800/60">
            {displayed.map((row, i) => {
              const avg = Number(row.avg_players) || 0;
              const peak = Number(row.peak_players) || 0;
              const slots = Number(row.max_slots) || 20;
              return (
                <div key={row.server_id} className="px-5 py-3 hover:bg-slate-800/30 transition-colors">
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="text-[11px] font-mono text-slate-500 w-5 text-right shrink-0">{i + 1}</span>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-slate-100 truncate leading-tight">
                          {shortName(row.server_name)}
                        </p>
                        <p className="text-[11px] text-slate-500 font-mono mt-0.5">{row.region}</p>
                      </div>
                    </div>
                    <div className="text-right shrink-0 ml-4">
                      <p className="text-sm font-bold text-cyan-400 font-mono">{avg.toFixed(1)}</p>
                      <p className="text-[10px] text-slate-500">avg / {peak} peak</p>
                    </div>
                  </div>
                  <div className="pl-8">
                    <FillBar value={avg} max={slots} color="bg-cyan-500" />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================
// SECTION 3 — Lowest Average Ping
// ============================================================
function PingSection({ ping, loading }) {
  const displayed = ping.slice(0, 12);
  const maxPing = displayed.length > 0 ? Math.max(...displayed.map((r) => Number(r.avg_ping))) : 200;

  return (
    <Card>
      <CardHeader>
        <CardTitle icon={Zap}>Lowest Avg Ping (Last 24h)</CardTitle>
        <span className="text-xs text-slate-400 font-mono">
          Daily latency from <code>server_metrics</code>
        </span>
      </CardHeader>
      <CardContent className="p-0">
        {loading ? (
          <div className="flex items-center justify-center h-28 text-slate-500 text-sm">Loading…</div>
        ) : displayed.length === 0 ? (
          <div className="flex items-center justify-center h-28 text-slate-500 text-sm">No ping data yet</div>
        ) : (
          <div className="divide-y divide-slate-800/60">
            {displayed.map((row, i) => {
              const avg = Number(row.avg_ping) || 0;
              const best = Number(row.best_ping) || 0;
              const samples = Number(row.sample_count) || 0;
              return (
                <div key={row.server_id} className="px-5 py-3 hover:bg-slate-800/30 transition-colors">
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="text-[11px] font-mono text-slate-500 w-5 text-right shrink-0">{i + 1}</span>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-slate-100 truncate leading-tight">
                          {shortName(row.server_name)}
                        </p>
                        <p className="text-[11px] text-slate-500 font-mono mt-0.5">
                          {row.region} · {samples.toLocaleString()} samples
                        </p>
                      </div>
                    </div>
                    <div className="text-right shrink-0 ml-4">
                      <p className={`text-sm font-bold font-mono ${pingColor(avg)}`}>{avg} ms</p>
                      <p className="text-[10px] text-slate-500">best {best} ms</p>
                    </div>
                  </div>
                  <div className="pl-8">
                    {/* Inverted bar: lower ping = fuller bar */}
                    <FillBar
                      value={maxPing - avg}
                      max={maxPing}
                      color={avg < 40 ? 'bg-emerald-500' : avg < 80 ? 'bg-cyan-500' : avg < 140 ? 'bg-amber-500' : 'bg-rose-500'}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================
// MAIN InsightsView
// ============================================================
export function InsightsView({ dailyInsights = {}, onRefresh }) {
  const { restarts = [], busy = [], ping = [], loading = false } = dailyInsights;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-100 flex items-center gap-2.5">
            <TrendingUp className="w-6 h-6 text-cyan-400" />
            Daily Server Insights
          </h2>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            Last 24 hours · sourced from <code>monitored_servers</code> + <code>server_metrics</code>
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={onRefresh}
          loading={loading}
          icon={RefreshCw}
          title="Refresh insights"
        >
          <span className="hidden sm:inline">Refresh</span>
        </Button>
      </div>

      {/* Summary Pills */}
      <div className="flex flex-wrap gap-2">
        <span className="text-xs font-mono px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700 text-slate-300">
          <span className="text-rose-400 font-bold">{restarts.filter((r) => Number(r.restart_count) > 0).length}</span>
          &nbsp;servers had outages
        </span>
        <span className="text-xs font-mono px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700 text-slate-300">
          <span className="text-cyan-400 font-bold">{busy.filter((r) => Number(r.avg_players) > 0).length}</span>
          &nbsp;servers had players
        </span>
        <span className="text-xs font-mono px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700 text-slate-300">
          <span className="text-emerald-400 font-bold">
            {ping.length > 0 ? Number(ping[0].avg_ping).toFixed(0) : '—'}
          </span>
          &nbsp;ms best avg ping
        </span>
      </div>

      {/* 3 Sections stacked */}
      <RestartsSection restarts={restarts} loading={loading} />
      <BusySection busy={busy} loading={loading} />
      <PingSection ping={ping} loading={loading} />
    </div>
  );
}
