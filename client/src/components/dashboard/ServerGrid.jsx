import React from 'react';
import { Server } from 'lucide-react';
import { ServerCard } from './ServerCard';

export function ServerGrid({
  servers = [],
  selectedServerId,
  onSelectServer,
  onInspectServer,
  regionFilter,
  onRegionChange,
  statusFilter,
  onStatusChange,
  regions = [],
}) {
  return (
    <div className="space-y-4">
      {/* Header & Filter Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-900/60 p-3.5 rounded-xl border border-slate-800">
        <div className="flex items-center gap-2">
          <Server className="w-4 h-4 text-cyan-400" />
          <h3 className="font-bold text-sm text-slate-100 uppercase font-mono tracking-wider">
            Active Dedicated Servers ({servers.length})
          </h3>
        </div>

        {/* Region & Status Filters */}
        <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
          {/* Region Tabs */}
          <div className="flex items-center rounded-lg bg-slate-950/80 border border-slate-800 p-0.5">
            {regions.map((reg) => (
              <button
                key={reg}
                onClick={() => onRegionChange(reg)}
                className={`px-2.5 py-1 rounded-md transition-all uppercase ${
                  regionFilter === reg
                    ? 'bg-cyan-500/20 text-cyan-300 font-semibold border border-cyan-500/40'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {reg}
              </button>
            ))}
          </div>

          {/* Status filter */}
          <div className="flex items-center rounded-lg bg-slate-950/80 border border-slate-800 p-0.5">
            {['ALL', 'ONLINE', 'OFFLINE'].map((status) => (
              <button
                key={status}
                onClick={() => onStatusChange(status)}
                className={`px-2.5 py-1 rounded-md transition-all ${
                  statusFilter === status
                    ? 'bg-indigo-500/20 text-indigo-300 font-semibold border border-indigo-500/40'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {status}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Grid of Cards */}
      {servers.length === 0 ? (
        <div className="p-12 text-center rounded-xl border border-slate-800 bg-slate-900/40">
          <p className="text-slate-400 text-sm font-mono">
            No monitored servers match your current filters.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {servers.map((server) => (
            <ServerCard
              key={server.server_id}
              server={server}
              isSelected={server.server_id === selectedServerId}
              onSelect={onSelectServer}
              onInspect={onInspectServer}
            />
          ))}
        </div>
      )}
    </div>
  );
}
