import { useEffect, useRef, useState, useCallback } from "react";

const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

export function useWebSocket(path = "/ws/operations", enabled = true) {
  const [snapshot, setSnapshot] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState(null);
  const socketRef = useRef(null);
  const retryCountRef = useRef(0);
  const retryTimerRef = useRef(null);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!enabled) return;
    if (socketRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const backendHost =
      window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
        ? window.location.host
        : import.meta.env.VITE_WS_HOST || window.location.host;

    try {
      const socket = new WebSocket(`${protocol}://${backendHost}${path}`);
      socketRef.current = socket;

      socket.onopen = () => {
        if (!mountedRef.current) return;
        setIsConnected(true);
        setConnectionError(null);
        retryCountRef.current = 0;
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === "simulation_snapshot") {
            setSnapshot(payload.payload);
          }
        } catch {}
      };

      socket.onerror = () => {
        if (!mountedRef.current) return;
        setConnectionError("WebSocket connection error");
      };

      socket.onclose = (event) => {
        if (!mountedRef.current) return;
        setIsConnected(false);
        if (enabled) {
          const delay = Math.min(
            RECONNECT_BASE_MS * Math.pow(2, retryCountRef.current),
            RECONNECT_MAX_MS
          );
          retryCountRef.current += 1;
          setConnectionError(`Disconnected (${event.code}). Reconnecting in ${Math.round(delay / 1000)}s…`);
          retryTimerRef.current = setTimeout(connect, delay);
        }
      };
    } catch (err) {
      if (!mountedRef.current) return;
      setConnectionError(`Connection failed: ${err.message}`);
      if (enabled) {
        retryTimerRef.current = setTimeout(connect, RECONNECT_BASE_MS);
      }
    }
  }, [path, enabled]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    const ping = setInterval(() => {
      if (socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.send("ping");
      }
    }, 15000);

    return () => {
      mountedRef.current = false;
      clearInterval(ping);
      clearTimeout(retryTimerRef.current);
      if (socketRef.current) {
        socketRef.current.onclose = null;
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [connect]);

  return { snapshot, isConnected, connectionError };
}
