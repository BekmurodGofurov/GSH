import React from 'react';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { ConnectionBanner } from '../common/ConnectionBanner';

export function Layout({
  children,
  currentView,
  onViewChange,
  wsStatus,
  retryCountdown,
  isOffline,
  justReconnected,
  onRetry,
  isRefreshing,
  lastSyncTime,
  onRefresh,
  searchQuery,
  onSearchChange,
  kpis,
  eventCount,
  crashCount,
  theme,
  toggleTheme,
  onOpenNotifications,
  unreadCount,
}) {
  return (
    <div className="min-h-screen flex flex-col font-sans bg-grid-pattern antialiased">
      {/* Top Navbar */}
      <Header
        wsStatus={wsStatus}
        retryCountdown={retryCountdown}
        isRefreshing={isRefreshing}
        lastSyncTime={lastSyncTime}
        onRefresh={onRefresh}
        searchQuery={searchQuery}
        onSearchChange={onSearchChange}
        kpis={kpis}
        theme={theme}
        toggleTheme={toggleTheme}
        onOpenNotifications={onOpenNotifications}
        unreadCount={unreadCount}
      />

      {/* Slack / YouTube Style Persistent Connection Banner */}
      <ConnectionBanner
        isOffline={isOffline}
        wsStatus={wsStatus}
        retryCountdown={retryCountdown}
        justReconnected={justReconnected}
        onRetry={onRetry}
        lastSyncTime={lastSyncTime}
      />

      {/* Main App Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar */}
        <Sidebar
          currentView={currentView}
          onViewChange={onViewChange}
          kpis={kpis}
          eventCount={eventCount}
          crashCount={crashCount}
        />

        {/* Dynamic View Canvas */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 space-y-6">
          {children}
        </main>
      </div>

      {/* Mobile Bottom Navigation Bar for smaller viewports */}
      <div className="md:hidden flex items-center justify-around border-t border-slate-800 bg-slate-950/90 backdrop-blur-lg p-2 sticky bottom-0 z-40 text-xs overflow-x-auto">
        {['overview', 'servers', 'events', 'analytics', 'insights', 'admin'].map((view) => (
          <button
            key={view}
            onClick={() => onViewChange(view)}
            className={`px-2 py-2 rounded-lg font-mono uppercase tracking-wider ${
              currentView === view
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                : 'text-slate-400'
            }`}
          >
            {view === 'overview' ? 'Dash' : view === 'insights' ? 'Insight' : view}
          </button>
        ))}
      </div>
    </div>
  );
}
