import React from 'react';
import {
  AreaChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { Activity, Radio } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../common/Card';
import { Badge } from '../common/Badge';
import { formatTime } from '../../utils/formatters';

// Custom tooltip supporting light and dark modes
function CustomTooltip({ active, payload, label }) {
  if (active && payload && payload.length) {
    return (
      <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white/95 dark:bg-slate-950/95 p-3.5 shadow-xl dark:shadow-2xl backdrop-blur-md font-mono text-xs space-y-2 min-w-[170px]">
        <div className="text-[11px] text-slate-500 dark:text-slate-400 border-b border-slate-100 dark:border-slate-800 pb-1.5 flex justify-between items-center">
          <span>TIME</span>
          <span className="text-slate-800 dark:text-slate-200 font-semibold">{formatTime(label)}</span>
        </div>
        {payload.map((entry, index) => (
          <div key={`item-${index}`} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 font-medium" style={{ color: entry.color }}>
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
              {entry.name === 'player_count' ? 'Players' : 'Ping'}
            </span>
            <span className="font-bold text-slate-900 dark:text-slate-100">
              {entry.value} {entry.name === 'ping_ms' ? 'ms' : ''}
            </span>
          </div>
        ))}
      </div>
    );
  }
  return null;
}

export function ServerMetricsChart({
  metrics = [],
  activeServer,
  servers = [],
  onSelectServer,
  timeRange,
  onTimeRangeChange,
}) {
  const chartData = (metrics || []).map((m) => ({
    ...m,
    formattedTime: formatTime(m.time),
  }));

  const latestMetric = metrics && metrics.length > 0 ? metrics[metrics.length - 1] : null;

  return (
    <Card className="border-slate-200/80 dark:border-slate-800/80">
      <CardHeader className="flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <CardTitle icon={Activity}>Live Server Telemetry</CardTitle>
            {activeServer && (
              <Badge
                variant={activeServer.status === 'ONLINE' ? 'emerald' : 'rose'}
                dot
                size="sm"
              >
                {activeServer.status || 'ONLINE'}
              </Badge>
            )}
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 font-mono">
            {activeServer
              ? `${activeServer.server_name} (${activeServer.server_id})`
              : 'Real-time Player vs Latency stream'}
          </p>
        </div>

        {/* Server & Limit Controls */}
        <div className="flex flex-wrap items-center gap-2.5 w-full sm:w-auto">
          {/* Server Selector */}
          <select
            value={activeServer?.server_id || ''}
            onChange={(e) => onSelectServer(e.target.value)}
            className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-slate-800 dark:text-slate-200 font-mono outline-none focus:border-cyan-500 cursor-pointer shadow-xs dark:shadow-none"
          >
            {servers.length === 0 ? (
              <option value="">No servers available</option>
            ) : (
              servers.map((s) => (
                <option key={s.server_id} value={s.server_id} className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">
                  {s.server_name} ({s.region})
                </option>
              ))
            )}
          </select>

          {/* Time Limit Pills */}
          <div className="flex items-center rounded-lg bg-slate-100 dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 p-0.5 text-xs font-mono">
            {['15', '30', '60'].map((range) => (
              <button
                key={range}
                onClick={() => onTimeRangeChange(range)}
                className={`px-2.5 py-1 rounded-md transition-all cursor-pointer ${
                  timeRange === range
                    ? 'bg-white dark:bg-cyan-500/20 text-cyan-700 dark:text-cyan-300 font-semibold border border-slate-200 dark:border-cyan-500/40 shadow-xs'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                }`}
              >
                {range} pts
              </button>
            ))}
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-2">
        {/* Quick summary badges */}
        {latestMetric && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4 p-3 rounded-lg bg-slate-50 dark:bg-slate-950/40 border border-slate-200/80 dark:border-slate-800/60 font-mono text-xs">
            <div>
              <span className="text-slate-500 dark:text-slate-400 block text-[10px]">CURRENT PING</span>
              <span className="text-sm font-bold text-cyan-700 dark:text-cyan-400">{latestMetric.ping_ms ?? '--'} ms</span>
            </div>
            <div>
              <span className="text-slate-500 dark:text-slate-400 block text-[10px]">PLAYERS IN MATCH</span>
              <span className="text-sm font-bold text-violet-700 dark:text-violet-400">
                {latestMetric.player_count ?? 0} / {latestMetric.max_players || activeServer?.max_players || 24}
              </span>
            </div>
            <div>
              <span className="text-slate-500 dark:text-slate-400 block text-[10px]">TICK RATE</span>
              <span className="text-sm font-bold text-emerald-700 dark:text-emerald-400">
                {latestMetric.tick_rate || 128} Hz
              </span>
            </div>
            <div>
              <span className="text-slate-500 dark:text-slate-400 block text-[10px]">CURRENT MAP</span>
              <span className="text-sm font-bold text-slate-800 dark:text-slate-200">
                {latestMetric.map || activeServer?.map || 'de_mirage'}
              </span>
            </div>
          </div>
        )}

        {/* Chart Canvas with explicit container height */}
        <div className="h-[280px] min-h-[280px] w-full">
          {chartData.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 text-xs font-mono p-6 border border-dashed border-slate-800 rounded-xl bg-slate-950/30">
              <Radio className="w-6 h-6 text-slate-400 mb-2 animate-pulse" />
              <p className="text-slate-400 font-semibold">No Metric Telemetry Recorded Yet</p>
              <p className="text-[11px] text-slate-400 mt-1">
                Awaiting time-series data from Gateway endpoint `/api/v1/servers/{activeServer?.server_id || '...'}/metrics`.
              </p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="pingGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#06b6d4" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="playerGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.5} />
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0.0} />
                  </linearGradient>
                </defs>

                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.6} />
                <XAxis
                  dataKey="formattedTime"
                  stroke="#64748b"
                  tick={{ fontSize: 11, fill: '#64748b', fontFamily: 'monospace' }}
                  tickLine={false}
                />
                <YAxis
                  yAxisId="players"
                  orientation="left"
                  stroke="#8b5cf6"
                  domain={[0, 'dataMax + 4']}
                  tick={{ fontSize: 11, fill: '#8b5cf6', fontFamily: 'monospace' }}
                  tickLine={false}
                />
                <YAxis
                  yAxisId="ping"
                  orientation="right"
                  stroke="#06b6d4"
                  domain={[0, 'dataMax + 20']}
                  tick={{ fontSize: 11, fill: '#06b6d4', fontFamily: 'monospace' }}
                  tickLine={false}
                />

                <Tooltip content={<CustomTooltip />} />
                <Legend
                  wrapperStyle={{ paddingTop: '10px', fontSize: '12px', fontFamily: 'monospace' }}
                  formatter={(value) => (value === 'player_count' ? 'Player Load' : 'Network Ping (ms)')}
                />

                <Area
                  yAxisId="players"
                  type="monotone"
                  dataKey="player_count"
                  name="player_count"
                  stroke="#8b5cf6"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#playerGradient)"
                  isAnimationActive={false}
                />

                <Line
                  yAxisId="ping"
                  type="monotone"
                  dataKey="ping_ms"
                  name="ping_ms"
                  stroke="#06b6d4"
                  strokeWidth={2}
                  dot={{ r: 2, fill: '#06b6d4' }}
                  activeDot={{ r: 5, fill: '#22d3ee', stroke: '#083344' }}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
