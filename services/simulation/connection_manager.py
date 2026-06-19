"""WebSocket connection manager supporting multiple named channels.

When USE_REDIS=true, the broadcast method also publishes messages through
a Redis channel so that all application instances in a horizontally-scaled
deployment receive the same real-time updates.  Local WebSocket delivery
still happens in-process for directly-connected clients on this instance.
"""
from __future__ import annotations

from typing import Any

from fastapi import WebSocket

from config import settings
from services.redis_adapter import get_redis_pubsub


class ConnectionManager:
    def __init__(self) -> None:
        self._channels: dict[str, set[WebSocket]] = {"global": set()}
        self._redis = get_redis_pubsub() if settings.use_redis else None

    async def connect(self, websocket: WebSocket, channel: str = "global") -> None:
        await websocket.accept()
        if channel not in self._channels:
            self._channels[channel] = set()
        self._channels[channel].add(websocket)

    def disconnect(self, websocket: WebSocket, channel: str = "global") -> None:
        if channel in self._channels:
            self._channels[channel].discard(websocket)

    async def broadcast(self, payload: dict[str, Any], channel: str = "global") -> None:
        # Local delivery to WebSockets connected to this instance.
        connections = self._channels.get(channel, set())
        for websocket in list(connections):
            try:
                await websocket.send_json(payload)
            except Exception:
                self.disconnect(websocket, channel)

        # Cross-instance delivery via Redis pub/sub (when enabled).
        if self._redis is not None and self._redis.enabled:
            await self._redis.publish(channel, payload)

    @property
    def connections(self) -> set[WebSocket]:
        """Backward-compatible accessor for code using .connections directly.
        Returns all connections across all channels."""
        all_conns: set[WebSocket] = set()
        for conns in self._channels.values():
            all_conns.update(conns)
        return all_conns

    @connections.setter
    def connections(self, value: set[WebSocket]) -> None:
        """No-op setter for backward compatibility."""
        pass
