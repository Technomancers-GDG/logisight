import { useEffect, useRef, useState } from "react";

export function useWebSocket(path = "/ws/operations") {
  const [snapshot, setSnapshot] = useState(null);
  const socketRef = useRef(null);

  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const backendHost =
      window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
        ? window.location.host
        : import.meta.env.VITE_WS_HOST || window.location.host;

    const socket = new WebSocket(`${protocol}://${backendHost}${path}`);
    socketRef.current = socket;

    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "simulation_snapshot") {
          setSnapshot(payload.payload);
        }
      } catch {}
    };

    const ping = setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) socket.send("ping");
    }, 15000);

    return () => {
      clearInterval(ping);
      socket.close();
    };
  }, [path]);

  return snapshot;
}
