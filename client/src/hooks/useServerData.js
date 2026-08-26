import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { api } from '../services/api';
import { useWebSocket } from './useWebSocket';
import { useAudioAlert } from './useAudioAlert';

const CACHE_KEY = 'cs2_dashboard_cache';

function getInitialCache() {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (raw) {
      return JSON.parse(raw);
    }
  } catch (e) {
    // Ignore corrupt localStorage
  }
  return {
    servers: [],
    events: [],
    serverMetrics: {},
    pingBuckets: [],
    lastUpdated: null,
  };
}

function saveCache(data) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(data));
  } catch (e) {
    // LocalStorage write error (e.g. quota exceeded)
  }
}

export function useServerData() {
  const initialCache = useMemo(() => getInitialCache(), []);

  const [servers, setServers] = useState(initialCache.servers || []);
  const [events, setEvents] = useState(initialCache.events || []);
  const [activeServerId, setActiveServerId] = useState(
    initialCache.servers && initialCache.servers.length > 0
      ? initialCache.servers[0].server_id
      : null
  );
  const [metricsCache, setMetricsCache] = useState(initialCache.serverMetrics || {});
  const [pingBuckets, setPingBuckets] = useState(initialCache.pingBuckets || []);
  const [lastSyncTime, setLastSyncTime] = useState(
    initialCache.lastUpdated ? new Date(initialCache.lastUpdated) : null
  );

  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [justReconnected, setJustReconnected] = useState(false);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [regionFilter, setRegionFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [timeRange, setTimeRange] = useState('30');

  const audio = useAudioAlert();
  const wasOfflineRef = useRef(false);

  // Synchronize state changes to localStorage
  const syncToStorage = useCallback(
    (updatedData) => {
      setServers((prevServers) => {
        setEvents((prevEvents) => {
          setMetricsCache((prevMetrics) => {
            setPingBuckets((prevBuckets) => {
              const currentCache = {
                servers: updatedData.servers !== undefined ? updatedData.servers : prevServers,
                events: updatedData.events !== undefined ? updatedData.events : prevEvents,
                serverMetrics:
                  updatedData.metrics !== undefined
                    ? { ...prevMetrics, ...updatedData.metrics }
                    : prevMetrics,
                pingBuckets:
                  updatedData.pingBuckets !== undefined ? updatedData.pingBuckets : prevBuckets,
                lastUpdated: new Date().toISOString(),
              };
              saveCache(currentCache);
              return currentCache.pingBuckets;
            });
            return updatedData.metrics !== undefined
              ? { ...prevMetrics, ...updatedData.metrics }
              : prevMetrics;
          });
          return updatedData.events !== undefined ? updatedData.events : prevEvents;
        });
        return updatedData.servers !== undefined ? updatedData.servers : prevServers;
      });
      setLastSyncTime(new Date());
    },
    []
  );

  // Handle incoming live WebSocket payloads
  const handleWsMessage = useCallback(
    (payload) => {
      if (!payload) return;

      let newServers = undefined;
      let newEvents = undefined;

      if (Array.isArray(payload.servers) && payload.servers.length > 0) {
        newServers = payload.servers;
        setServers((prev) => {
          const map = new Map(payload.servers.map((s) => [s.server_id, s]));
          return prev.length === 0
            ? payload.servers
            : prev.map((s) => map.get(s.server_id) || s);
        });

        // Set default active server if unset
        setActiveServerId((prev) => prev || payload.servers[0].server_id);
      }

      if (Array.isArray(payload.events) && payload.events.length > 0) {
        setEvents((prev) => {
          const existingIds = new Set(prev.map((e) => e.id));
          const fresh = payload.events.filter((e) => !existingIds.has(e.id));
          if (fresh.length > 0) {
            audio.triggerAlert(fresh[0].event_type);
            newEvents = [...fresh, ...prev].slice(0, 50);
            return newEvents;
          }
          return prev;
        });
      }

      syncToStorage({ servers: newServers, events: newEvents });
    },
    [audio, syncToStorage]
  );

  // Fetch full REST data
  const fetchData = useCallback(async (force = false) => {
    setIsRefreshing(true);
    if (force) {
      api.resetCircuit();
    }

    try {
      const [serversRes, eventsRes, analyticsRes] = await Promise.all([
        api.getServers(force),
        api.getEvents(25, force),
        api.getPingBuckets(10, force),
      ]);

      const updates = {};

      if (serversRes.data) {
        setServers(serversRes.data);
        updates.servers = serversRes.data;
        setActiveServerId((prev) => prev || (serversRes.data[0] ? serversRes.data[0].server_id : null));
      }

      if (eventsRes.data) {
        setEvents(eventsRes.data);
        updates.events = eventsRes.data;
      }

      if (analyticsRes.data) {
        setPingBuckets(analyticsRes.data);
        updates.pingBuckets = analyticsRes.data;
      }

      if (Object.keys(updates).length > 0) {
        syncToStorage(updates);
      }
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [syncToStorage]);

  // Handle WebSocket reconnection
  const handleWsOpen = useCallback(() => {
    if (wasOfflineRef.current) {
      setJustReconnected(true);
      setTimeout(() => setJustReconnected(false), 3500);
    }
    wasOfflineRef.current = false;
    fetchData(true);
  }, [fetchData]);

  const {
    status: wsStatus,
    isConnected,
    isOffline,
    retryCountdown,
    reconnect: reconnectWs,
  } = useWebSocket(undefined, {
    onMessage: handleWsMessage,
    onOpen: handleWsOpen,
  });

  // Track offline transitions
  useEffect(() => {
    if (isOffline) {
      wasOfflineRef.current = true;
    }
  }, [isOffline]);

  // Fetch metrics for active server
  const fetchActiveServerMetrics = useCallback(
    async (serverId, limit) => {
      if (!serverId) return;
      const res = await api.getServerMetrics(serverId, parseInt(limit, 10));
      if (res.data) {
        setMetricsCache((prev) => {
          const updated = { ...prev, [serverId]: res.data };
          syncToStorage({ metrics: { [serverId]: res.data } });
          return updated;
        });
      }
    },
    [syncToStorage]
  );

  // Initial load
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Load metrics when activeServerId or timeRange changes
  useEffect(() => {
    if (activeServerId) {
      fetchActiveServerMetrics(activeServerId, timeRange);
    }
  }, [activeServerId, timeRange, fetchActiveServerMetrics]);

  // Current active server metrics (from cache or live)
  const currentMetrics = useMemo(() => {
    if (!activeServerId) return [];
    return metricsCache[activeServerId] || [];
  }, [activeServerId, metricsCache]);

  // Active Server details object
  const activeServer = useMemo(() => {
    return servers.find((s) => s.server_id === activeServerId) || servers[0] || null;
  }, [servers, activeServerId]);

  // Regions list
  const regions = useMemo(() => {
    const set = new Set(servers.map((s) => s.region).filter(Boolean));
    return ['ALL', ...Array.from(set)];
  }, [servers]);

  // Filtered servers
  const filteredServers = useMemo(() => {
    return servers.filter((s) => {
      const matchSearch =
        searchQuery === '' ||
        (s.server_name && s.server_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (s.server_id && s.server_id.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (s.region && s.region.toLowerCase().includes(searchQuery.toLowerCase()));

      const matchRegion = regionFilter === 'ALL' || s.region === regionFilter;
      const matchStatus =
        statusFilter === 'ALL' || (s.status || '').toUpperCase() === statusFilter.toUpperCase();

      return matchSearch && matchRegion && matchStatus;
    });
  }, [servers, searchQuery, regionFilter, statusFilter]);

  // Calculated Dashboard KPI Stats strictly from real data
  const kpis = useMemo(() => {
    const total = servers.length;
    const online = servers.filter((s) => (s.status || '').toUpperCase() === 'ONLINE').length;
    const offline = total - online;

    const onlineServers = servers.filter((s) => (s.status || '').toUpperCase() === 'ONLINE');
    const validPingServers = onlineServers.filter((s) => typeof s.ping_ms === 'number' && s.ping_ms > 0);
    const avgPing =
      validPingServers.length > 0
        ? validPingServers.reduce((acc, s) => acc + s.ping_ms, 0) / validPingServers.length
        : 0;

    const totalPlayers = servers.reduce((acc, s) => acc + (s.player_count || 0), 0);
    const maxCapacity = servers.reduce((acc, s) => acc + (s.max_players || 0), 0);

    let health = total > 0 ? (online / total) * 100 : 0;
    if (avgPing > 80) health = Math.max(0, health - 15);
    else if (avgPing > 50) health = Math.max(0, health - 5);
    const healthIndex = Math.round(health);

    return {
      totalServers: total,
      onlineServers: online,
      offlineServers: offline,
      avgPing: parseFloat(avgPing.toFixed(1)),
      totalPlayers,
      maxCapacity,
      healthIndex,
      uptimePercentage: total > 0 ? ((online / total) * 100).toFixed(1) : '0.0',
    };
  }, [servers]);

  return {
    servers,
    filteredServers,
    events,
    activeServerId,
    setActiveServerId,
    activeServer,
    serverMetrics: currentMetrics,
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
    isLoading,
    isRefreshing,
    lastSyncTime,
    wsStatus,
    isConnected,
    isOffline,
    retryCountdown,
    justReconnected,
    reconnectWs: () => {
      api.resetCircuit();
      reconnectWs();
      fetchData(true);
    },
    refreshData: () => fetchData(true),
    audio,
  };
}
