import React, { useState } from 'react';
import { useServerData } from './hooks/useServerData';
import { Layout } from './components/layout/Layout';
import { OverviewView } from './components/views/OverviewView';
import { ServersView } from './components/views/ServersView';
import { EventLogsView } from './components/views/EventLogsView';
import { AnalyticsView } from './components/views/AnalyticsView';
import { AlertingSettingsView } from './components/views/AlertingSettingsView';
import { ServerDetailModal } from './components/dashboard/ServerDetailModal';

export function App() {
  const [currentView, setCurrentView] = useState('overview');
  const [inspectServer, setInspectServer] = useState(null);

  const {
    servers,
    filteredServers,
    events,
    activeServerId,
    setActiveServerId,
    activeServer,
    serverMetrics,
    pingBuckets,
    kpis,
    regions,
    searchQuery,
    setSearchQuery,
    regionFilter,
    setRegionFilter,
    statusFilter,
    setStatusFilter,
    timeRange,
    setTimeRange,
    isRefreshing,
    lastSyncTime,
    wsStatus,
    retryCountdown,
    isOffline,
    justReconnected,
    reconnectWs,
    refreshData,
    audio,
  } = useServerData();

  const crashCount = (events || []).filter(
    (e) => (e.event_type || '').toUpperCase() === 'CRASH'
  ).length;

  return (
    <Layout
      currentView={currentView}
      onViewChange={setCurrentView}
      wsStatus={wsStatus}
      retryCountdown={retryCountdown}
      isOffline={isOffline}
      justReconnected={justReconnected}
      onRetry={reconnectWs}
      isRefreshing={isRefreshing}
      lastSyncTime={lastSyncTime}
      onRefresh={refreshData}
      audio={audio}
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      kpis={kpis}
      eventCount={events.length}
      crashCount={crashCount}
    >
      {/* Dynamic View rendering */}
      {currentView === 'overview' && (
        <OverviewView
          kpis={kpis}
          servers={servers}
          filteredServers={filteredServers}
          activeServer={activeServer}
          activeServerId={activeServerId}
          onSelectServer={setActiveServerId}
          onInspectServer={(srv) => setInspectServer(srv)}
          serverMetrics={serverMetrics}
          pingBuckets={pingBuckets}
          events={events}
          regions={regions}
          regionFilter={regionFilter}
          onRegionChange={setRegionFilter}
          statusFilter={statusFilter}
          onStatusChange={setStatusFilter}
          timeRange={timeRange}
          onTimeRangeChange={setTimeRange}
        />
      )}

      {currentView === 'servers' && (
        <ServersView
          servers={servers}
          filteredServers={filteredServers}
          activeServerId={activeServerId}
          onSelectServer={setActiveServerId}
          onInspectServer={(srv) => setInspectServer(srv)}
          regions={regions}
          regionFilter={regionFilter}
          onRegionChange={setRegionFilter}
          statusFilter={statusFilter}
          onStatusChange={setStatusFilter}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
        />
      )}

      {currentView === 'events' && (
        <EventLogsView
          events={events}
          onSelectServer={(sid) => {
            setActiveServerId(sid);
            const found = servers.find((s) => s.server_id === sid);
            if (found) setInspectServer(found);
          }}
        />
      )}

      {currentView === 'analytics' && (
        <AnalyticsView
          pingBuckets={pingBuckets}
          servers={servers}
        />
      )}

      {currentView === 'alerting' && (
        <AlertingSettingsView audio={audio} />
      )}

      {/* Inspect Server Detail Modal */}
      <ServerDetailModal
        server={inspectServer}
        isOpen={Boolean(inspectServer)}
        onClose={() => setInspectServer(null)}
        events={events}
      />
    </Layout>
  );
}

export default App;
