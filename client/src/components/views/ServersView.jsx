import React, { useState } from 'react';
import {
  Server,
  LayoutGrid,
  List,
  Wifi,
  ExternalLink,
  ArrowUpDown,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../common/Card';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { ServerGrid } from '../dashboard/ServerGrid';
import { Pagination } from '../common/Pagination';
import {
  formatPing,
  getPingBadgeColor,
  formatRelativeTime,
} from '../../utils/formatters';

export function ServersView({
  servers = [],
  filteredServers = [],
  activeServerId,
  onSelectServer,
  onInspectServer,
  regions = [],
  regionFilter,
  onRegionChange,
  statusFilter,
  onStatusChange,
  currentPage = 1,
  totalPages = 1,
  onPageChange,
  totalCount = 0,
}) {
  const [viewMode, setViewMode] = useState('grid'); // 'grid' | 'table'
  const [sortField, setSortField] = useState('name'); // 'name' | 'ping' | 'players' | 'status'
  const [sortOrder, setSortOrder] = useState('asc');

  const handleSort = (field) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortOrder('asc');
    }
  };

  const sortedServers = [...filteredServers].sort((a, b) => {
    let result = 0;
    if (sortField === 'name') {
      result = (a.server_name || '').localeCompare(b.server_name || '');
    } else if (sortField === 'ping') {
      result = (a.ping_ms || 0) - (b.ping_ms || 0);
    } else if (sortField === 'players') {
      result = (a.player_count || 0) - (b.player_count || 0);
    } else if (sortField === 'status') {
      result = (a.status || '').localeCompare(b.status || '');
    }
    return sortOrder === 'asc' ? result : -result;
  });

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2.5">
            <Server className="w-6 h-6 text-cyan-600 dark:text-cyan-400" />
            Dedicated Server Fleet
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 font-mono">
            Managing {servers.length} target instances across Vienna and Warsaw datacenters.
          </p>
        </div>

        {/* View Switcher */}
        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-lg bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-0.5 shadow-xs dark:shadow-none">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-1.5 rounded-md transition-all cursor-pointer ${
                viewMode === 'grid'
                  ? 'bg-white dark:bg-cyan-500/20 text-cyan-700 dark:text-cyan-300 border border-slate-200 dark:border-cyan-500/40 shadow-xs'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
              title="Grid View"
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('table')}
              className={`p-1.5 rounded-md transition-all cursor-pointer ${
                viewMode === 'table'
                  ? 'bg-white dark:bg-cyan-500/20 text-cyan-700 dark:text-cyan-300 border border-slate-200 dark:border-cyan-500/40 shadow-xs'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
              title="Table View"
            >
              <List className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Grid or Table Display */}
      {viewMode === 'grid' ? (
        <ServerGrid
          servers={filteredServers}
          selectedServerId={activeServerId}
          onSelectServer={onSelectServer}
          onInspectServer={onInspectServer}
          regions={regions}
          regionFilter={regionFilter}
          onRegionChange={onRegionChange}
          statusFilter={statusFilter}
          onStatusChange={onStatusChange}
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={onPageChange}
        />
      ) : (
        <Card className="border-slate-200/80 dark:border-slate-800/80">
          <CardHeader className="flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <CardTitle icon={Server}>Server Inventory Table ({totalCount})</CardTitle>

            {/* Region & Status Filters */}
            <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
              <div className="flex items-center rounded-lg bg-slate-100/90 dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 p-0.5">
                {regions.map((reg) => (
                  <button
                    key={reg}
                    onClick={() => onRegionChange(reg)}
                    className={`px-2.5 py-1 rounded-md transition-all uppercase cursor-pointer ${
                      regionFilter === reg
                        ? 'bg-white dark:bg-cyan-500/20 text-cyan-700 dark:text-cyan-300 font-semibold border border-slate-200 dark:border-cyan-500/40 shadow-xs'
                        : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                    }`}
                  >
                    {reg}
                  </button>
                ))}
              </div>

              <div className="flex items-center rounded-lg bg-slate-100/90 dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 p-0.5">
                {['ALL', 'ONLINE', 'OFFLINE'].map((st) => (
                  <button
                    key={st}
                    onClick={() => onStatusChange(st)}
                    className={`px-2.5 py-1 rounded-md transition-all cursor-pointer ${
                      statusFilter === st
                        ? 'bg-white dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300 font-semibold border border-slate-200 dark:border-indigo-500/40 shadow-xs'
                        : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                    }`}
                  >
                    {st}
                  </button>
                ))}
              </div>
            </div>
          </CardHeader>

          <CardContent className="p-0 overflow-x-auto">
            <table className="w-full text-left font-mono text-xs divide-y divide-slate-200 dark:divide-slate-800">
              <thead className="bg-slate-50 dark:bg-slate-950/80 text-slate-500 dark:text-slate-400 uppercase text-[10px] tracking-wider">
                <tr>
                  <th
                    className="p-3.5 cursor-pointer hover:text-slate-800 dark:hover:text-slate-200"
                    onClick={() => handleSort('name')}
                  >
                    <div className="flex items-center gap-1.5">
                      Server / Node <ArrowUpDown className="w-3 h-3" />
                    </div>
                  </th>
                  <th className="p-3.5">Region / Map</th>
                  <th
                    className="p-3.5 cursor-pointer hover:text-slate-800 dark:hover:text-slate-200"
                    onClick={() => handleSort('status')}
                  >
                    <div className="flex items-center gap-1.5">
                      Status <ArrowUpDown className="w-3 h-3" />
                    </div>
                  </th>
                  <th
                    className="p-3.5 cursor-pointer hover:text-slate-800 dark:hover:text-slate-200"
                    onClick={() => handleSort('players')}
                  >
                    <div className="flex items-center gap-1.5">
                      Players <ArrowUpDown className="w-3 h-3" />
                    </div>
                  </th>
                  <th
                    className="p-3.5 cursor-pointer hover:text-slate-800 dark:hover:text-slate-200"
                    onClick={() => handleSort('ping')}
                  >
                    <div className="flex items-center gap-1.5">
                      Ping <ArrowUpDown className="w-3 h-3" />
                    </div>
                  </th>
                  <th className="p-3.5">Last Seen</th>
                  <th className="p-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 text-slate-700 dark:text-slate-200">
                {sortedServers.map((s) => {
                  const isOnline = (s.status || '').toUpperCase() === 'ONLINE';
                  return (
                    <tr
                      key={s.server_id}
                      onClick={() => onSelectServer(s.server_id)}
                      className={`hover:bg-slate-50 dark:hover:bg-slate-800/40 cursor-pointer transition-colors ${
                        activeServerId === s.server_id ? 'bg-cyan-50/50 dark:bg-slate-800/60' : ''
                      }`}
                    >
                      <td className="p-3.5">
                        <div className="font-bold text-slate-900 dark:text-slate-100 font-sans text-sm">
                          {s.server_name}
                        </div>
                        <div className="text-slate-500 dark:text-slate-400 text-[11px]">{s.server_id}</div>
                      </td>
                      <td className="p-3.5">
                        <div className="text-slate-800 dark:text-slate-200">{s.region}</div>
                        <div className="text-slate-500 dark:text-slate-400 text-[11px]">{s.map || 'de_mirage'}</div>
                      </td>
                      <td className="p-3.5">
                        <Badge variant={isOnline ? 'emerald' : 'rose'} dot size="sm">
                          {isOnline ? 'ONLINE' : 'OFFLINE'}
                        </Badge>
                      </td>
                      <td className="p-3.5">
                        <div className="text-slate-800 dark:text-slate-200 font-semibold">
                          {s.player_count || (isOnline ? 18 : 0)} / {s.max_players || 24}
                        </div>
                      </td>
                      <td className="p-3.5">
                        {isOnline ? (
                          <span
                            className={`px-2 py-0.5 rounded border inline-flex items-center gap-1 font-bold ${getPingBadgeColor(
                              s.ping_ms
                            )}`}
                          >
                            <Wifi className="w-3 h-3" />
                            {formatPing(s.ping_ms)}
                          </span>
                        ) : (
                          <span className="text-slate-400 dark:text-slate-500">--</span>
                        )}
                      </td>
                      <td className="p-3.5 text-slate-500 dark:text-slate-400 text-[11px]">
                        {isOnline
                          ? formatRelativeTime(s.last_online_at)
                          : formatRelativeTime(s.last_offline_at)}
                      </td>
                      <td className="p-3.5 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            onInspectServer(s);
                          }}
                          className="text-cyan-600 dark:text-cyan-400 hover:text-cyan-700 dark:hover:text-cyan-300 text-xs py-1 font-medium"
                        >
                          Inspect <ExternalLink className="w-3 h-3 ml-1" />
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardContent>
          {/* Table pagination */}
          <div className="px-4 pb-4">
            <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={onPageChange}
            />
          </div>
        </Card>
      )}
    </div>
  );
}
