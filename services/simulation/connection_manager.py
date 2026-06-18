"""WebSocket connection manager supporting multiple named channels."""
from __future__ import annotations

from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._channels: dict[str, set[WebSocket]] = {"global": set()}

    async def connect(self, websocket: WebSocket, channel: str = "global") -> None:
        await websocket.accept()
        if channel not in self._channels:
            self._channels[channel] = set()
        self._channels[channel].add(websocket)

    def disconnect(self, websocket: WebSocket, channel: str = "global") -> None:
        if channel in self._channels:
            self._channels[channel].discard(websocket)

    async def broadcast(self, payload: dict[str, Any], channel: str = "global") -> None:
        connections = self._channels.get(channel, set())
        for websocket in list(connections):
            try:
                await websocket.send_json(payload)
            except Exception:
                self.disconnect(websocket, channel)

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
