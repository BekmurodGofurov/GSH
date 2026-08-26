import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { BarChart3, Clock, Database, Layers } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../common/Card';
import { Badge } from '../common/Badge';
import { formatTime } from '../../utils/formatters';

function CustomBarTooltip({ active, payload }) {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="rounded-xl border border-slate-700 bg-slate-950/95 p-3.5 shadow-2xl backdrop-blur-md font-mono text-xs space-y-2">
        <div className="text-[11px] text-slate-400 border-b border-slate-800 pb-1 flex justify-between gap-4">
          <span>BUCKET (1-MIN)</span>
          <span className="text-slate-200 font-semibold">{formatTime(data.bucket)}</span>
        </div>
        <div className="text-[10px] text-cyan-400 font-semibold">{data.server_id}</div>
        <div className="flex items-center justify-between gap-6">
          <span className="text-slate-400">Avg Ping:</span>
          <span className="text-cyan-400 font-bold">{data.avg_ping} ms</span>
        </div>
        <div className="flex items-center justify-between gap-6">
          <span className="text-slate-400">Avg Players:</span>
          <span className="text-violet-400 font-bold">{data.avg_players}</span>
        </div>
      </div>
    );
  }
  return null;
}

export function PingAnalyticsChart({ pingBuckets = [] }) {
  const formattedData = (pingBuckets || []).slice(0, 16).map((item) => ({
    ...item,
    formattedBucket: formatTime(item.bucket),
    shortServer: (item.server_id || '').split(':')[0].slice(-5) || item.server_id,
  }));

  return (
    <Card className="border-slate-800/80">
      <CardHeader className="flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
        <div>
          <div className="flex items-center gap-2.5">
            <CardTitle icon={BarChart3}>TimescaleDB 1-Min Ping Aggregation</CardTitle>
            <Badge variant="cyan" size="sm">
              HYPERTABLE
            </Badge>
          </div>
          <p className="text-xs text-slate-400 mt-1 font-mono flex items-center gap-1.5">
            <Clock className="w-3 h-3 text-cyan-400" />
            Rolling 10-minute rollup (`time_bucket('1 minute', time)`)
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono text-slate-400 bg-slate-900/80 px-3 py-1.5 rounded-lg border border-slate-800">
          <Database className="w-3.5 h-3.5 text-cyan-400" />
          <span>PostgreSQL + TimescaleDB</span>
        </div>
      </CardHeader>

      <CardContent className="pt-2">
        <div className="h-[250px] min-h-[250px] w-full">
          {formattedData.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 text-xs font-mono p-6 border border-dashed border-slate-800 rounded-xl bg-slate-950/30">
              <Layers className="w-6 h-6 text-slate-400 mb-2" />
              <p className="text-slate-400 font-semibold">No TimescaleDB Buckets Available</p>
              <p className="text-[11px] text-slate-400 mt-1">
                Awaiting continuous aggregation rollup from `/api/v1/analytics/ping-buckets`.
              </p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={formattedData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.6} />
                <XAxis
                  dataKey="formattedBucket"
                  stroke="#64748b"
                  tick={{ fontSize: 10, fill: '#64748b', fontFamily: 'monospace' }}
                  tickLine={false}
                />
                <YAxis
                  stroke="#06b6d4"
                  tick={{ fontSize: 10, fill: '#06b6d4', fontFamily: 'monospace' }}
                  tickLine={false}
                  unit="ms"
                />
                <Tooltip content={<CustomBarTooltip />} />
                <Legend
                  wrapperStyle={{ paddingTop: '8px', fontSize: '11px', fontFamily: 'monospace' }}
                  formatter={() => 'Average Network Ping (ms)'}
                />
                <Bar
                  dataKey="avg_ping"
                  name="avg_ping"
                  fill="#06b6d4"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={32}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
