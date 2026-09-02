import { useState, useEffect, useRef, useCallback } from 'react';

const DEFAULT_WS_URL =
  import.meta.env.VITE_WS_URL ||
  (import.meta.env.VITE_API_URL
    ? `${import.meta.env.VITE_API_URL.replace(/^http/, 'ws')}/ws/live`
    : null);

if (!DEFAULT_WS_URL) {
    throw new Error('VITE_WS_URL (or VITE_API_URL) environment variable is not set.');
}

const BACKOFF_SCHEDULE = [3000, 6000, 12000, 20000];

/**
 * Production-grade WebSocket hook with:
 * - Stable callback refs (prevents re-render reconnect churn)
 * - Safe connection cancellation (no "closed before established" warnings)
 * - Exponential backoff retry countdown
 */
export function useWebSocket(url = DEFAULT_WS_URL, options = {}) {
  const { onMessage, onOpen } = options;

  // Keep latest callbacks in refs so they never cause connect() to re-run
  const onMessageRef = useRef(onMessage);
  const onOpenRef = useRef(onOpen);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    onOpenRef.current = onOpen;
  }, [onOpen]);

  const [status, setStatus] = useState('reconnecting'); // 'connected' | 'reconnecting' | 'offline'
  const [retryCountdown, setRetryCountdown] = useState(0);

  const wsRef = useRef(null);
  const backoffIndexRef = useRef(0);
  const reconnectTimerRef = useRef(null);
  const countdownIntervalRef = useRef(null);
  const isMountedRef = useRef(true);

  // Clear all pending timers
  const clearTimers = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
  }, []);

  // Safe cleanup of a socket without triggering "closed before established"
  const safelyCloseSocket = useCallback((ws) => {
    if (!ws) return;
    ws.onmessage = null;

    if (ws.readyState === WebSocket.CONNECTING) {
      // If still connecting, wait until it opens to close it gracefully
      ws.onopen = () => {
        try {
          ws.close();
        } catch (e) {
          // Ignore
        }
      };
      ws.onerror = () => {};
      ws.onclose = () => {};
    } else if (ws.readyState === WebSocket.OPEN) {
      ws.onopen = null;
      ws.onerror = null;
      ws.onclose = null;
      try {
        ws.close();
      } catch (e) {
        // Ignore
      }
    }
  }, []);

  const connect = useCallback(() => {
    if (!isMountedRef.current) return;

    // If already connected or connecting, do not duplicate
    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    clearTimers();
    setStatus('reconnecting');

    try {
      safelyCloseSocket(wsRef.current);

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current) return;
        setStatus('connected');
        backoffIndexRef.current = 0;
        setRetryCountdown(0);
        clearTimers();

        if (onOpenRef.current) {
          onOpenRef.current();
        }
      };

      ws.onmessage = (event) => {
        if (!isMountedRef.current) return;
        try {
          const payload = JSON.parse(event.data);
          if (onMessageRef.current) {
            onMessageRef.current(payload);
          }
        } catch (e) {
          // Ignore malformed payloads
        }
      };

      ws.onerror = () => {
        // Error will trigger onclose automatically
      };

      ws.onclose = () => {
        if (!isMountedRef.current) return;
        setStatus('offline');
        wsRef.current = null;

        // Determine exponential backoff delay
        const delay =
          BACKOFF_SCHEDULE[
            Math.min(backoffIndexRef.current, BACKOFF_SCHEDULE.length - 1)
          ];
        backoffIndexRef.current += 1;

        let secondsRemaining = Math.ceil(delay / 1000);
        setRetryCountdown(secondsRemaining);

        // Tick down every second
        countdownIntervalRef.current = setInterval(() => {
          if (!isMountedRef.current) return;
          secondsRemaining -= 1;
          setRetryCountdown(Math.max(0, secondsRemaining));
          if (secondsRemaining <= 0) {
            clearInterval(countdownIntervalRef.current);
            countdownIntervalRef.current = null;
          }
        }, 1000);

        // Schedule next reconnect attempt
        reconnectTimerRef.current = setTimeout(() => {
          if (isMountedRef.current) {
            connect();
          }
        }, delay);
      };
    } catch (err) {
      if (isMountedRef.current) {
        setStatus('offline');
      }
    }
  }, [url, clearTimers, safelyCloseSocket]);

  useEffect(() => {
    isMountedRef.current = true;
    connect();

    return () => {
      isMountedRef.current = false;
      clearTimers();
      safelyCloseSocket(wsRef.current);
      wsRef.current = null;
    };
  }, [connect, clearTimers, safelyCloseSocket]);

  const manualReconnect = useCallback(() => {
    backoffIndexRef.current = 0;
    safelyCloseSocket(wsRef.current);
    wsRef.current = null;
    connect();
  }, [connect, safelyCloseSocket]);

  const sendMessage = useCallback((data) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify(data));
      } catch (e) {
        // Ignore send errors (socket closing)
      }
    }
  }, []);

  return {
    status,
    isConnected: status === 'connected',
    isOffline: status === 'offline' || status === 'reconnecting',
    retryCountdown,
    reconnect: manualReconnect,
    sendMessage,
  };
}
