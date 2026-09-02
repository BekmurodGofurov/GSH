import React, { useState } from 'react';
import { useServerData } from './hooks/useServerData';
import { useTheme } from './hooks/useTheme';
import { Layout } from './components/layout/Layout';
import { OverviewView } from './components/views/OverviewView';
import { ServersView } from './components/views/ServersView';
import { EventLogsView } from './components/views/EventLogsView';
import { AnalyticsView } from './components/views/AnalyticsView';
import { InsightsView } from './components/views/InsightsView';
import { ServerDetailModal } from './components/dashboard/ServerDetailModal';
import { NotificationsDrawer } from './components/common/NotificationsDrawer';
import { AdminWrapper } from './components/views/AdminWrapper';

export function App() {
  const [currentView, setCurrentView] = useState('overview');
  const [inspectServer, setInspectServer] = useState(null);
  const { theme, toggleTheme } = useTheme();

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
    dailyInsights,
    refreshInsights,
    paginatedOverview,
    overviewPage,
    overviewTotalPages,
    goToOverviewPage,
    overviewPageSize,
    changeOverviewPageSize,
    paginatedFleet,
    fleetPage,
    fleetTotalPages,
    goToFleetPage,
    notifications,
    dismissNotification,
    clearAllNotifications,
    triggerTestNotification,
  } = useServerData();

  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);

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
      theme={theme}
      toggleTheme={toggleTheme}
      onOpenNotifications={() => setIsNotificationsOpen(true)}
      unreadCount={notifications.length}
    >
      {/* Dynamic View rendering */}
      {currentView === 'overview' && (
        <OverviewView
          kpis={kpis}
          servers={servers}
          filteredServers={paginatedOverview}
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
          currentPage={overviewPage}
          totalPages={overviewTotalPages}
          onPageChange={goToOverviewPage}
          pageSize={overviewPageSize}
          onPageSizeChange={changeOverviewPageSize}
          totalCount={filteredServers.length}
        />
      )}

      {currentView === 'servers' && (
        <ServersView
          servers={servers}
          filteredServers={paginatedFleet}
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
          currentPage={fleetPage}
          totalPages={fleetTotalPages}
          onPageChange={goToFleetPage}
          totalCount={filteredServers.length}
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

      {currentView === 'insights' && (
        <InsightsView />
      )}

      {currentView === 'admin' && (
        <AdminWrapper />
      )}

    {/* Inspect Server Detail Modal */}
      <ServerDetailModal
        server={inspectServer}
        isOpen={Boolean(inspectServer)}
        onClose={() => setInspectServer(null)}
        events={events}
      />

      <NotificationsDrawer
        isOpen={isNotificationsOpen}
        onClose={() => setIsNotificationsOpen(false)}
        notifications={notifications}
        onInspect={(sid) => {
          const found = servers.find((s) => s.server_id === sid);
          if (found) setInspectServer(found);
        }}
        onClearAll={clearAllNotifications}
      />
    </Layout>
  );
}

export default App;
