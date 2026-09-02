const BASE_URL = import.meta.env.VITE_API_URL;
if (!BASE_URL) {
    throw new Error("VITE_API_URL environment variable is not set.");
}

// Circuit breaker to avoid network flooding when Gateway is offline
let lastFailureTimestamp = 0;
const CIRCUIT_COOLDOWN_MS = 2500;

function isCircuitOpen() {
  return Date.now() - lastFailureTimestamp < CIRCUIT_COOLDOWN_MS;
}

function recordSuccess() {
  lastFailureTimestamp = 0;
}

function recordFailure() {
  lastFailureTimestamp = Date.now();
}

/**
 * Robust fetch utility with timeout, circuit breaker, and silent failure handling.
 */
async function fetchSafe(endpoint, options = {}) {
  const { timeout = 3500, bypassCircuit = false, ...fetchOptions } = options;

  if (!bypassCircuit && isCircuitOpen()) {
    return { data: null, error: 'Gateway currently offline' };
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(`${BASE_URL}${endpoint}`, {
      ...fetchOptions,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(fetchOptions.headers || {}),
      },
    });
    clearTimeout(timeoutId);

    if (!response.ok) {
      recordFailure();
      try {
        const errData = await response.json();
        if (errData.detail) return { data: null, error: errData.detail };
      } catch (e) {}
      return { data: null, error: `HTTP ${response.status}: ${response.statusText}` };
    }

    const data = await response.json();
    recordSuccess();
    return { data, error: null };
  } catch (err) {
    clearTimeout(timeoutId);
    recordFailure();
    return {
      data: null,
      error: err.name === 'AbortError' ? 'Request timed out' : 'Backend unavailable',
    };
  }
}

export const api = {
  resetCircuit() {
    lastFailureTimestamp = 0;
  },

  async getServers(bypassCircuit = false) {
    const res = await fetchSafe('/api/v1/servers', { bypassCircuit });
    return { data: Array.isArray(res.data) ? res.data : null, error: res.error };
  },

  async getServerMetrics(serverId, limit = 30, bypassCircuit = false) {
    if (!serverId) return { data: [], error: 'Missing serverId' };
    const encodedId = encodeURIComponent(serverId);
    const res = await fetchSafe(`/api/v1/servers/${encodedId}/metrics?limit=${limit}`, { bypassCircuit });
    return { data: Array.isArray(res.data) ? [...res.data].reverse() : null, error: res.error };
  },

  async getEvents(limit = 20, bypassCircuit = false) {
    const res = await fetchSafe(`/api/v1/events?limit=${limit}`, { bypassCircuit });
    return { data: Array.isArray(res.data) ? res.data : null, error: res.error };
  },

  async getPingBuckets(minutes = 10, bypassCircuit = false) {
    const res = await fetchSafe(`/api/v1/analytics/ping-buckets?minutes=${minutes}`, { bypassCircuit });
    return { data: Array.isArray(res.data) ? res.data : null, error: res.error };
  },

  async getDailyRestarts(bypassCircuit = false) {
    const res = await fetchSafe('/api/v1/analytics/daily-restarts', { bypassCircuit });
    return { data: Array.isArray(res.data) ? res.data : null, error: res.error };
  },

  async getDailyBusy(bypassCircuit = false) {
    const res = await fetchSafe('/api/v1/analytics/daily-busy', { bypassCircuit });
    return { data: Array.isArray(res.data) ? res.data : null, error: res.error };
  },

  async getDailyPing(bypassCircuit = false) {
    const res = await fetchSafe('/api/v1/analytics/daily-ping', { bypassCircuit });
    return { data: Array.isArray(res.data) ? res.data : null, error: res.error };
  },

  async getDailyInsights(dateStr, bypassCircuit = false) {
    return fetchSafe(`/api/v1/insights/daily?target_date=${dateStr}`, { bypassCircuit, timeout: 5000 });
  },
};
