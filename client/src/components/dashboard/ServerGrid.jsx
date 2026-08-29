import React from 'react';
import { Server, ChevronDown, ChevronUp, Grid3X3, StretchHorizontal } from 'lucide-react';
import { ServerCard } from './ServerCard';
import { Pagination } from '../common/Pagination';

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
  currentPage = 1,
  totalPages = 1,
  onPageChange,
  pageSize = 3,
  onPageSizeChange,
  totalCount,
}) {
  const isExpanded = pageSize === 9;

  return (
    <div className="space-y-4">
      {/* Header & Filter Controls */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 bg-white/90 dark:bg-slate-900/60 p-3.5 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-xs dark:shadow-none">
        <div className="flex items-center gap-2">
          <Server className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
          <h3 className="font-bold text-sm text-slate-800 dark:text-slate-100 uppercase font-mono tracking-wider">
            Active Dedicated Servers
          </h3>
          {totalCount !== undefined && (
            <span className="text-[11px] font-mono px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
              {totalCount} total
            </span>
          )}
        </div>

        {/* Filters & View Size Controls */}
        <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
          {/* Region Tabs */}
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

          {/* Status filter */}
          <div className="flex items-center rounded-lg bg-slate-100/90 dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 p-0.5">
            {['ALL', 'ONLINE', 'OFFLINE'].map((status) => (
              <button
                key={status}
                onClick={() => onStatusChange(status)}
                className={`px-2.5 py-1 rounded-md transition-all cursor-pointer ${
                  statusFilter === status
                    ? 'bg-white dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300 font-semibold border border-slate-200 dark:border-indigo-500/40 shadow-xs'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                }`}
              >
                {status}
              </button>
            ))}
          </div>

          {/* 3 vs 9 Display Size Toggle */}
          {onPageSizeChange && (
            <div className="flex items-center rounded-lg bg-slate-100/90 dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 p-0.5">
              <button
                onClick={() => onPageSizeChange(3)}
                className={`px-2.5 py-1 rounded-md transition-all flex items-center gap-1.5 cursor-pointer ${
                  pageSize === 3
                    ? 'bg-white dark:bg-cyan-500/20 text-cyan-700 dark:text-cyan-300 font-semibold border border-slate-200 dark:border-cyan-500/40 shadow-xs'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                }`}
                title="Compact view (1 row • 3 servers)"
              >
                <StretchHorizontal className="w-3.5 h-3.5" />
                <span>3</span>
              </button>
              <button
                onClick={() => onPageSizeChange(9)}
                className={`px-2.5 py-1 rounded-md transition-all flex items-center gap-1.5 cursor-pointer ${
                  pageSize === 9
                    ? 'bg-white dark:bg-cyan-500/20 text-cyan-700 dark:text-cyan-300 font-semibold border border-slate-200 dark:border-cyan-500/40 shadow-xs'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                }`}
                title="Expanded view (3 rows • 9 servers)"
              >
                <Grid3X3 className="w-3.5 h-3.5" />
                <span>9</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Grid of Cards (1 row of 3 or 3 rows of 9) */}
      {servers.length === 0 ? (
        <div className="p-12 text-center rounded-xl border border-slate-200 dark:border-slate-800 bg-white/60 dark:bg-slate-900/40">
          <p className="text-slate-500 dark:text-slate-400 text-sm font-mono">
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

      {/* Bottom Controls: Expand/Collapse Button & Pagination */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
        {onPageSizeChange ? (
          <button
            onClick={() => onPageSizeChange(isExpanded ? 3 : 9)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-medium text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 hover:border-cyan-400 dark:hover:border-cyan-500/40 hover:text-cyan-700 dark:hover:text-cyan-300 transition-all cursor-pointer shadow-xs dark:shadow-none w-fit"
          >
            {isExpanded ? (
              <>
                <ChevronUp className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400" />
                <span>Compact (Show 3)</span>
              </>
            ) : (
              <>
                <ChevronDown className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400" />
                <span>More Servers (Show 9)</span>
              </>
            )}
          </button>
        ) : (
          <div />
        )}

        {/* Pagination Controls */}
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={onPageChange}
        />
      </div>
    </div>
  );
}

