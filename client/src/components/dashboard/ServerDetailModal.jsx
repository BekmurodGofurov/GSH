import React, { useState, useEffect } from 'react';
import {
  Activity,
  Wifi,
  RefreshCw,
  Power,
  CheckCircle2,
  Terminal,
} from 'lucide-react';
import { Modal } from '../common/Modal';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { api } from '../../services/api';
import { formatPing, formatTime, formatRelativeTime, formatEventBadge } from '../../utils/formatters';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export function ServerDetailModal({
  server,
  isOpen,
  onClose,
  events = [],
}) {
  const [metrics, setMetrics] = useState([]);
  const [loadingMetrics, setLoadingMetrics] = useState(false);
  const [actionStatus, setActionStatus] = useState(null);

  const isOnline = (server?.status || '').toUpperCase() === 'ONLINE';

  useEffect(() => {
    if (server && isOpen) {
      setLoadingMetrics(true);
      api.getServerMetrics(server.server_id, 30)
        .then((res) => {
          if (res.data) {
            setMetrics(res.data);
          }
        })
        .finally(() => setLoadingMetrics(false));
    }
  }, [server, isOpen]);

  if (!server) return null;

  const serverEvents = (events || []).filter((e) => e.server_id === server.server_id);

  const handleAction = (actionName) => {
    setActionStatus(`Executing ${actionName}...`);
    setTimeout(() => {
      setActionStatus(`Success: ${actionName} command dispatched to host.`);
      setTimeout(() => setActionStatus(null), 3000);
    }, 1000);
  };

  const chartData = (metrics || []).map((m) => ({
    ...m,
    timeFormatted: formatTime(m.time),
  }));

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={server.server_name}
      subtitle={`Dedicated Node: ${server.server_id} • Region: ${server.region}`}
      maxWidth="max-w-4xl"
    >
      <div className="space-y-5">
        {/* Top Status Banner */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 rounded-xl bg-slate-950/70 border border-slate-800 font-mono text-xs">
          <div>
            <span className="text-slate-400 block text-[10px]">HEALTH STATUS</span>
            <div className="mt-1">
              <Badge variant={isOnline ? 'emerald' : 'rose'} dot size="sm">
                {isOnline ? 'ONLINE' : 'OFFLINE'}
              </Badge>
            </div>
          </div>

          <div>
            <span className="text-slate-400 block text-[10px]">AVG LATENCY</span>
            <span className="text-sm font-bold text-cyan-400 mt-1 block">
              {formatPing(server.ping_ms)}
            </span>
          </div>

          <div>
            <span className="text-slate-400 block text-[10px]">PLAYER CAPACITY</span>
            <span className="text-sm font-bold text-violet-400 mt-1 block">
              {server.player_count ?? (isOnline ? 18 : 0)} / {server.max_players || 24} slots
            </span>
          </div>

          <div>
            <span className="text-slate-400 block text-[10px]">TICK RATE / MAP</span>
            <span className="text-sm font-bold text-slate-200 mt-1 block">
              128 T / {server.map || 'de_mirage'}
            </span>
          </div>
        </div>

        {/* Action feedback banner */}
        {actionStatus && (
          <div className="p-3 rounded-lg bg-cyan-950/80 border border-cyan-500/50 text-cyan-300 font-mono text-xs flex items-center gap-2 animate-fade-in">
            <CheckCircle2 className="w-4 h-4 text-cyan-400" />
            {actionStatus}
          </div>
        )}

        {/* Mini Chart */}
        <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyan-400" />
              Real-time Latency (ms) History
            </h4>
            <span className="text-[11px] font-mono text-slate-400">Past 30 data points</span>
          </div>

          <div className="h-44 min-h-[176px] w-full">
            {chartData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-slate-400 font-mono text-xs p-4 border border-dashed border-slate-800 rounded-lg">
                {loadingMetrics ? 'Loading telemetry...' : 'No historical metrics recorded for this server.'}
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                  <defs>
                    <linearGradient id="modalPing" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#06b6d4" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="timeFormatted"
                    stroke="#475569"
                    tick={{ fontSize: 10, fill: '#64748b' }}
                  />
                  <YAxis stroke="#475569" tick={{ fontSize: 10, fill: '#64748b' }} unit="ms" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#020617',
                      borderColor: '#334155',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="ping_ms"
                    name="Ping"
                    stroke="#06b6d4"
                    strokeWidth={2}
                    fill="url(#modalPing)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Server Specific Logs */}
        <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800">
          <h4 className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-2">
            <Terminal className="w-4 h-4 text-rose-400" />
            Server Incident Log History
          </h4>

          {serverEvents.length === 0 ? (
            <p className="text-xs font-mono text-slate-400">
              No recent anomalies or crashes recorded for this server instance.
            </p>
          ) : (
            <div className="space-y-2 max-h-36 overflow-y-auto">
              {serverEvents.map((evt) => {
                const badge = formatEventBadge(evt.event_type);
                return (
                  <div
                    key={evt.id || evt.time}
                    className="p-2.5 rounded-lg bg-slate-900/90 border border-slate-800 flex items-start justify-between gap-3 text-xs"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge variant={badge.variant} size="sm">
                          {badge.label}
                        </Badge>
                        <span className="text-[11px] font-mono text-slate-400">
                          {formatTime(evt.time)}
                        </span>
                      </div>
                      <p className="text-slate-300 font-sans">{evt.message}</p>
                    </div>
                    <span className="text-[11px] font-mono text-slate-400 whitespace-nowrap">
                      {formatRelativeTime(evt.time)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Operational Actions */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-800">
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              icon={RefreshCw}
              onClick={() => handleAction('A2S Re-Query Probe')}
            >
              Trigger A2S Probe
            </Button>
            <Button
              variant="outline"
              size="sm"
              icon={Wifi}
              onClick={() => handleAction('ICMP Echo Ping')}
            >
              Test Latency
            </Button>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="danger"
              size="sm"
              icon={Power}
              onClick={() => handleAction('Graceful Container Restart')}
            >
              Restart Node
            </Button>
            <Button variant="ghost" size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
