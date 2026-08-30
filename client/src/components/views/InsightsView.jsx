import React, { useState, useEffect } from 'react';
import { Calendar, AlertCircle } from 'lucide-react';
import { api } from '../../services/api';
import { Card, CardHeader, CardTitle, CardContent } from '../common/Card';
import { Badge } from '../common/Badge';

function DashboardCard({ title, value, valueClass = '' }) {
  return (
    <Card className="flex flex-col items-center justify-center p-6 text-center border-slate-200/80 dark:border-slate-800/80 bg-white dark:bg-slate-900 shadow-sm">
      <h3 className="text-xs sm:text-sm font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2">
        {title}
      </h3>
      <div className={`text-2xl sm:text-4xl font-extrabold font-mono ${valueClass}`}>
        {value}
      </div>
    </Card>
  );
}

function ServerReportCard({ server }) {
  const offlineCount = server.offline_count || 0;
  const crashClass = offlineCount > 0 ? 'text-rose-500' : 'text-emerald-500';
  const pingClass = server.max_ping > 150 ? 'text-rose-500' : 'text-emerald-500';

  return (
    <Card className="border-slate-200/80 dark:border-slate-800/80 bg-white dark:bg-slate-900 shadow-sm flex flex-col">
      <div className="p-4 border-b border-slate-100 dark:border-slate-800 flex justify-between items-start">
        <div className="min-w-0 pr-2">
          <h2 className="text-sm font-bold text-slate-800 dark:text-slate-100 truncate" title={server.server_name}>
            {server.server_name}
          </h2>
          <div className="text-xs font-mono text-slate-500 dark:text-slate-400 mt-1">
            {server.server_id}
          </div>
        </div>
        <Badge variant="neutral" className="shrink-0">{server.region}</Badge>
      </div>
      <div className="p-4 flex-1 flex flex-col justify-center space-y-3 font-mono text-sm">
        <div className="flex justify-between items-center">
          <span className="text-slate-500 dark:text-slate-400">Crash / Offline Events</span>
          <span className={`font-bold ${crashClass}`}>{offlineCount}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-slate-500 dark:text-slate-400">Highest Ping</span>
          <span className={`font-bold ${pingClass}`}>
            {server.max_ping} ms <span className="text-xs text-slate-400 dark:text-slate-500 ml-1">@ {server.max_ping_time || '-'}</span>
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-slate-500 dark:text-slate-400">Lowest Ping</span>
          <span className="font-bold text-emerald-500">{server.min_ping} ms</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-slate-500 dark:text-slate-400">Max Players</span>
          <span className="font-bold text-slate-800 dark:text-slate-200">
            {server.max_players} <span className="text-xs text-slate-400 dark:text-slate-500 ml-1">@ {server.max_players_time || '-'}</span>
          </span>
        </div>
      </div>
    </Card>
  );
}

export function InsightsView() {
  const [dateStr, setDateStr] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    return d.toISOString().split('T')[0];
  });
  
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const [page, setPage] = useState(1);
  const [regionFilter, setRegionFilter] = useState('ALL');
  
  const PAGE_SIZE = 9;

  useEffect(() => {
    async function fetchData() {
      if (!dateStr) return;
      setLoading(true);
      setError(null);
      setData(null);
      
      const { data: resData, error: resErr } = await api.getDailyInsights(dateStr);
      
      if (resErr) {
        setError(resErr);
      } else {
        setData(resData);
      }
      setLoading(false);
      setPage(1); // Reset page on new data
    }
    fetchData();
  }, [dateStr]);

  // Filtering
  const allServers = data?.servers || [];
  const regions = [...new Set(allServers.map((s) => s.region))].sort();
  
  const filteredServers = regionFilter === 'ALL' 
    ? allServers 
    : allServers.filter(s => s.region === regionFilter);
    
  // Pagination
  const totalPages = Math.ceil(filteredServers.length / PAGE_SIZE) || 1;
  const paginatedServers = filteredServers.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2.5">
            <Calendar className="w-6 h-6 text-violet-600 dark:text-violet-400" />
            Daily Report Viewer
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Historical 24-hour summary reports
          </p>
        </div>
        
        <div className="flex items-center gap-4 w-full sm:w-auto bg-white dark:bg-slate-900 p-1.5 rounded-lg border border-slate-200 dark:border-slate-800 shadow-sm">
          <input
            type="date"
            value={dateStr}
            onChange={(e) => setDateStr(e.target.value)}
            className="bg-transparent border-none text-sm font-medium text-slate-700 dark:text-slate-200 focus:ring-0 cursor-pointer w-full sm:w-auto"
            max={new Date().toISOString().split('T')[0]}
          />
          
          <div className="h-6 w-px bg-slate-200 dark:bg-slate-700 hidden sm:block"></div>
          
          <select
            value={regionFilter}
            onChange={(e) => {
              setRegionFilter(e.target.value);
              setPage(1);
            }}
            className="bg-transparent border-none text-sm font-medium text-slate-700 dark:text-slate-200 focus:ring-0 cursor-pointer w-full sm:w-auto appearance-none pr-8"
          >
            <option value="ALL">All Regions</option>
            {regions.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>
      </div>

      {loading && (
        <div className="py-20 text-center text-slate-500 animate-pulse">Loading report data...</div>
      )}
      
      {!loading && error && (
        <div className="py-16 flex flex-col items-center justify-center text-center bg-rose-50 dark:bg-rose-950/20 rounded-xl border border-rose-100 dark:border-rose-900/30">
          <AlertCircle className="w-10 h-10 text-rose-500 mb-3" />
          <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">{error}</h3>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-md">
            Please try selecting a different date. The system only caches reports that have been fully generated.
          </p>
        </div>
      )}

      {!loading && !error && data && (
        <>
          {/* 4 Top Summary Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <DashboardCard title="Total Servers" value={data.total_servers} />
            <DashboardCard title="Overall Uptime" value={`${data.uptime_percent}%`} valueClass="text-emerald-500" />
            <DashboardCard title="Total Crashes/Offline" value={data.total_crashes} valueClass={data.total_crashes > 5 ? 'text-rose-500' : 'text-emerald-500'} />
            <DashboardCard title="Active Regions" value={data.active_regions} />
          </div>

          {/* Paginated Server Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {paginatedServers.map((srv) => (
              <ServerReportCard key={srv.server_id} server={srv} />
            ))}
          </div>
          
          {paginatedServers.length === 0 && (
            <div className="py-12 text-center text-slate-500">No servers found for the selected filters.</div>
          )}

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-4 border-t border-slate-200 dark:border-slate-800">
              <span className="text-sm text-slate-500 dark:text-slate-400">
                Showing <span className="font-medium text-slate-900 dark:text-slate-100">{(page - 1) * PAGE_SIZE + 1}</span> to{' '}
                <span className="font-medium text-slate-900 dark:text-slate-100">{Math.min(page * PAGE_SIZE, filteredServers.length)}</span> of{' '}
                <span className="font-medium text-slate-900 dark:text-slate-100">{filteredServers.length}</span> servers
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1.5 text-sm font-medium rounded-lg border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-800 disabled:opacity-50 hover:bg-slate-50 dark:hover:bg-slate-700"
                >
                  Previous
                </button>
                <div className="text-sm font-medium text-slate-700 dark:text-slate-200 px-2">
                  {page} / {totalPages}
                </div>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-3 py-1.5 text-sm font-medium rounded-lg border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-800 disabled:opacity-50 hover:bg-slate-50 dark:hover:bg-slate-700"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
