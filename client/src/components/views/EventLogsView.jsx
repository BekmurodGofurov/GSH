import React, { useState, useMemo } from 'react';
import {
  Terminal,
  Flame,
  AlertTriangle,
  CheckCircle2,
  Download,
  Search,
} from 'lucide-react';
import { Card, CardHeader, CardContent } from '../common/Card';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { Input } from '../common/Input';
import { formatTime, formatRelativeTime, formatEventBadge } from '../../utils/formatters';

export function EventLogsView({ events = [], onSelectServer }) {
  const [search, setSearch] = useState('');
  const [selectedType, setSelectedType] = useState('ALL');

  const stats = useMemo(() => {
    const total = events.length;
    const crashes = events.filter((e) => (e.event_type || '').toUpperCase() === 'CRASH').length;
    const latencySpikes = events.filter((e) => (e.event_type || '').toUpperCase() === 'HIGH_PING').length;
    const recoveries = events.filter((e) => (e.event_type || '').toUpperCase() === 'RECOVERY').length;

    return { total, crashes, latencySpikes, recoveries };
  }, [events]);

  const filtered = useMemo(() => {
    return events.filter((e) => {
      const matchType =
        selectedType === 'ALL' || (e.event_type || '').toUpperCase() === selectedType;
      const matchSearch =
        search === '' ||
        (e.server_id && e.server_id.toLowerCase().includes(search.toLowerCase())) ||
        (e.message && e.message.toLowerCase().includes(search.toLowerCase())) ||
        (e.event_type && e.event_type.toLowerCase().includes(search.toLowerCase()));

      return matchType && matchSearch;
    });
  }, [events, selectedType, search]);

  const handleExportJSON = () => {
    const jsonString = `data:text/json;charset=utf-8,${encodeURIComponent(
      JSON.stringify(events, null, 2)
    )}`;
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', jsonString);
    downloadAnchor.setAttribute('download', `cs2-incident-logs-${new Date().toISOString()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2.5">
            <Terminal className="w-6 h-6 text-cyan-600 dark:text-cyan-400" />
            System Incident & Event Logs
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 font-mono">
            Audit trail of game server crashes, network anomalies, and cluster recoveries.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          icon={Download}
          onClick={handleExportJSON}
        >
          Export Logs (JSON)
        </Button>
      </div>

      {/* Stats Summary Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="p-4 border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 font-mono shadow-xs dark:shadow-none">
          <span className="text-xs text-slate-500 dark:text-slate-400">TOTAL EVENTS</span>
          <p className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">{stats.total}</p>
        </Card>
        <Card className="p-4 border-rose-200 dark:border-rose-500/30 bg-rose-50/60 dark:bg-rose-950/10 font-mono shadow-xs dark:shadow-none">
          <span className="text-xs text-rose-700 dark:text-rose-400 flex items-center gap-1 font-bold">
            <Flame className="w-3.5 h-3.5" /> CRASHES
          </span>
          <p className="text-2xl font-bold text-rose-700 dark:text-rose-400 mt-1">{stats.crashes}</p>
        </Card>
        <Card className="p-4 border-amber-200 dark:border-amber-500/30 bg-amber-50/60 dark:bg-amber-950/10 font-mono shadow-xs dark:shadow-none">
          <span className="text-xs text-amber-700 dark:text-amber-400 flex items-center gap-1 font-bold">
            <AlertTriangle className="w-3.5 h-3.5" /> LATENCY SPIKES
          </span>
          <p className="text-2xl font-bold text-amber-700 dark:text-amber-400 mt-1">{stats.latencySpikes}</p>
        </Card>
        <Card className="p-4 border-emerald-200 dark:border-emerald-500/30 bg-emerald-50/60 dark:bg-emerald-950/10 font-mono shadow-xs dark:shadow-none">
          <span className="text-xs text-emerald-700 dark:text-emerald-400 flex items-center gap-1 font-bold">
            <CheckCircle2 className="w-3.5 h-3.5" /> RECOVERIES
          </span>
          <p className="text-2xl font-bold text-emerald-700 dark:text-emerald-400 mt-1">{stats.recoveries}</p>
        </Card>
      </div>

      {/* Main Table Card */}
      <Card className="border-slate-200/80 dark:border-slate-800/80">
        <CardHeader className="flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          {/* Search */}
          <div className="w-full sm:w-72">
            <Input
              icon={Search}
              placeholder="Search event messages..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              clearable
              onClear={() => setSearch('')}
              className="h-9 text-xs"
            />
          </div>

          {/* Type Filters */}
          <div className="flex flex-wrap items-center gap-1.5 rounded-lg bg-slate-100 dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 p-0.5 text-xs font-mono">
            {['ALL', 'CRASH', 'HIGH_PING', 'RECOVERY', 'WARNING'].map((type) => (
              <button
                key={type}
                onClick={() => setSelectedType(type)}
                className={`px-2.5 py-1 rounded-md transition-all cursor-pointer ${
                  selectedType === type
                    ? 'bg-white dark:bg-cyan-500/20 text-cyan-700 dark:text-cyan-300 font-semibold border border-slate-200 dark:border-cyan-500/40 shadow-xs'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                }`}
              >
                {type}
              </button>
            ))}
          </div>
        </CardHeader>

        <CardContent className="p-0 overflow-x-auto">
          <table className="w-full text-left font-mono text-xs divide-y divide-slate-200 dark:divide-slate-800">
            <thead className="bg-slate-50 dark:bg-slate-950/80 text-slate-500 dark:text-slate-400 uppercase text-[10px] tracking-wider">
              <tr>
                <th className="p-3.5">Severity / Type</th>
                <th className="p-3.5">Server Target</th>
                <th className="p-3.5">Incident Description</th>
                <th className="p-3.5">Timestamp</th>
                <th className="p-3.5 text-right">Age</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 text-slate-700 dark:text-slate-200">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-slate-500 dark:text-slate-400">
                    No log events match the current criteria.
                  </td>
                </tr>
              ) : (
                filtered.map((evt) => {
                  const badge = formatEventBadge(evt.event_type);
                  const isCrash = (evt.event_type || '').toUpperCase() === 'CRASH';

                  return (
                    <tr
                      key={evt.id || `${evt.server_id}-${evt.time}`}
                      className={`hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors ${
                        isCrash ? 'bg-rose-50/50 dark:bg-rose-950/10' : ''
                      }`}
                    >
                      <td className="p-3.5">
                        <Badge variant={badge.variant} size="sm">
                          {badge.label}
                        </Badge>
                      </td>
                      <td className="p-3.5">
                        <button
                          onClick={() => onSelectServer && onSelectServer(evt.server_id)}
                          className="font-bold text-slate-900 dark:text-slate-100 hover:text-cyan-600 dark:hover:text-cyan-400 hover:underline cursor-pointer"
                        >
                          {evt.server_id}
                        </button>
                      </td>
                      <td className="p-3.5 text-slate-600 dark:text-slate-300 font-sans max-w-md">
                        {evt.message}
                      </td>
                      <td className="p-3.5 text-slate-500 dark:text-slate-400">
                        {formatTime(evt.time)}
                      </td>
                      <td className="p-3.5 text-right text-slate-500 dark:text-slate-400">
                        {formatRelativeTime(evt.time)}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
