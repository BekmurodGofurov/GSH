import React from 'react';
import { BarChart3, Database } from 'lucide-react';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';
import { PingAnalyticsChart } from '../dashboard/PingAnalyticsChart';

export function AnalyticsView({ pingBuckets = [], servers = [] }) {
  // Group by region for comparative analysis
  const viennaServers = (servers || []).filter((s) => s.region === 'Vienna');
  const warsawServers = (servers || []).filter((s) => s.region === 'Warsaw');

  const viennaAvg =
    viennaServers.length > 0
      ? (viennaServers.reduce((acc, s) => acc + (s.ping_ms || 0), 0) / viennaServers.length).toFixed(1)
      : '0.0';

  const warsawAvg =
    warsawServers.length > 0
      ? (warsawServers.reduce((acc, s) => acc + (s.ping_ms || 0), 0) / warsawServers.length).toFixed(1)
      : '0.0';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-100 flex items-center gap-2.5">
          <BarChart3 className="w-6 h-6 text-cyan-400" />
          TimescaleDB Telemetry Analytics
        </h2>
        <p className="text-xs text-slate-400 mt-1 font-mono">
          Continuous rollups, time-bucketed latency, and multi-region performance.
        </p>
      </div>

      {/* Regional Performance Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-5 border-cyan-500/30 bg-slate-900/60 font-mono">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">VIENNA DATACENTER</span>
            <Badge variant="cyan" size="sm">
              HUB #01
            </Badge>
          </div>
          <div className="mt-3">
            <span className="text-3xl font-black text-cyan-400">{viennaAvg}</span>
            <span className="text-xs text-slate-400 ml-1">ms avg latency</span>
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            Valve EU-East Primary Gateway • 128 Tick
          </p>
        </Card>

        <Card className="p-5 border-indigo-500/30 bg-slate-900/60 font-mono">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">WARSAW DATACENTER</span>
            <Badge variant="violet" size="sm">
              HUB #02
            </Badge>
          </div>
          <div className="mt-3">
            <span className="text-3xl font-black text-violet-400">{warsawAvg}</span>
            <span className="text-xs text-slate-400 ml-1">ms avg latency</span>
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            Valve EU-East Secondary Gateway • 128 Tick
          </p>
        </Card>

        <Card className="p-5 border-emerald-500/30 bg-slate-900/60 font-mono">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">POSTGRES HYPERTABLE</span>
            <Badge variant="emerald" size="sm">
              LIVE
            </Badge>
          </div>
          <div className="mt-3">
            <span className="text-3xl font-black text-emerald-400">1-Min</span>
            <span className="text-xs text-slate-400 ml-1">bucket window</span>
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            TimescaleDB Continuous Aggregate Engine
          </p>
        </Card>
      </div>

      {/* Main Aggregation Chart */}
      <PingAnalyticsChart pingBuckets={pingBuckets} />

      {/* Query SQL Explanation Box */}
      <Card className="p-5 border-slate-800 bg-slate-950/80 font-mono text-xs">
        <div className="flex items-center gap-2 mb-3 text-cyan-400 font-bold">
          <Database className="w-4 h-4" />
          <span>Active TimescaleDB Query Architecture:</span>
        </div>
        <pre className="p-3.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 overflow-x-auto text-[11px] leading-relaxed">
{`SELECT 
    time_bucket('1 minute', time) AS bucket,
    server_id,
    ROUND(AVG(ping_ms)::numeric, 2) AS avg_ping,
    ROUND(AVG(player_count)::numeric, 1) AS avg_players
FROM server_metrics
WHERE time > NOW() - (INTERVAL '1 minute' * 10)
GROUP BY bucket, server_id
ORDER BY bucket DESC;`}
        </pre>
      </Card>
    </div>
  );
}
