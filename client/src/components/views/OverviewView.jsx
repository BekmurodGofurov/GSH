import React from 'react';
import { KpiStatsGrid } from '../dashboard/KpiStatsGrid';
import { ServerMetricsChart } from '../dashboard/ServerMetricsChart';
import { PingAnalyticsChart } from '../dashboard/PingAnalyticsChart';
import { ServerGrid } from '../dashboard/ServerGrid';
import { EventFeedTimeline } from '../dashboard/EventFeedTimeline';

export function OverviewView({
  kpis,
  servers,
  filteredServers,
  activeServer,
  activeServerId,
  onSelectServer,
  onInspectServer,
  serverMetrics,
  pingBuckets,
  events,
  regions,
  regionFilter,
  onRegionChange,
  statusFilter,
  onStatusChange,
  timeRange,
  onTimeRangeChange,
}) {
  return (
    <div className="space-y-6">
      {/* 1. Top KPI Summary Grid */}
      <KpiStatsGrid kpis={kpis} />

      {/* 2. Interactive Charts Section (Split 2-Column: Live Telemetry vs Timescale 1-Min Buckets) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7">
          <ServerMetricsChart
            metrics={serverMetrics}
            activeServer={activeServer}
            servers={servers}
            onSelectServer={onSelectServer}
            timeRange={timeRange}
            onTimeRangeChange={onTimeRangeChange}
          />
        </div>
        <div className="lg:col-span-5">
          <PingAnalyticsChart pingBuckets={pingBuckets} />
        </div>
      </div>

      {/* 3. Operational Grid & Live Incident Feed */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        <div className="xl:col-span-8">
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
          />
        </div>
        <div className="xl:col-span-4">
          <EventFeedTimeline
            events={events}
            onSelectServer={onSelectServer}
          />
        </div>
      </div>
    </div>
  );
}
