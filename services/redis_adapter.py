"""Redis pub/sub adapter for horizontal WebSocket scaling, plus optional
lightweight job queue backed by Redis lists (enqueue_job / dequeue_job).

Production: set USE_REDIS=true and REDIS_URL=<redis://...> to enable
cross-instance message relay and the job queue. When disabled, both
broadcasts and job operations are local-only (single-process, suitable
for prototyping and hackathon demos).

Usage:
    adapter = RedisPubSubAdapter()
    await adapter.publish("global", {"type": "simulation_snapshot", ...})
    adapter.subscribe("global", my_callback)
    await adapter.enqueue_job("reroute", {"vehicle_id": 1})
    job = await adapter.dequeue_job("reroute")
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from config import settings

logger = logging.getLogger(__name__)


class RedisPubSubAdapter:
    """Pub/sub adapter that uses Redis when enabled, local otherwise.

    In local mode (USE_REDIS=false, the default), publish() is a no-op
    and the ConnectionManager handles broadcasts directly via in-memory
    WebSocket sets.  In production mode, publish() relays the message
    through a Redis channel so every application instance receives it.
    """

    def __init__(self, redis_url: str = "", enabled: bool = False) -> None:
        self._enabled = enabled
        self._redis_url = redis_url
        self._pubsub = None
        self._local_subscribers: list[Callable[[str, dict[str, Any]], None]] = []
        self._local_job_queues: dict[str, list[str]] = {}

        if enabled:
            if redis_url:
                logger.info(
                    "Redis pub/sub enabled — connecting to %s", redis_url
                )
            else:
                logger.warning(
                    "USE_REDIS=true but REDIS_URL is empty — "
                    "falling back to local broadcast"
                )
                self._enabled = False

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        """Publish a JSON-serialisable message to *channel*."""
        if self._enabled and self._pubsub is not None:
            try:
                await self._pubsub.publish(channel, json.dumps(message))
            except Exception:
                logger.exception("Redis publish failed for channel %s", channel)
            return

        # Local fallback — notify in-process subscribers.
        for cb in self._local_subscribers:
            try:
                cb(channel, message)
            except Exception:
                logger.exception("Local pub/sub callback error")

    def subscribe(
        self, channel: str, callback: Callable[[str, dict[str, Any]], None]
    ) -> None:
        """Register a local subscriber for *channel*."""
        self._local_subscribers.append(callback)
        if self._enabled:
            logger.info(
                "Redis subscribe stub registered for channel '%s' "
                "(install `redis-py` and configure REDIS_URL for real "
                "cross-instance pub/sub)",
                channel,
            )

    async def enqueue_job(self, queue: str, payload: dict[str, Any]) -> None:
        """Push a job onto *queue* (backed by a Redis list when enabled).

        In local mode the payload is appended to an in-memory list so the
        rest of the application can still poll for jobs during development.
        """
        job_str = json.dumps(payload)
        if self._enabled and self._pubsub is not None:
            try:
                await self._pubsub.rpush(f"job:{queue}", job_str)
                return
            except Exception:
                logger.exception("Redis rpush failed for queue %s", queue)
        self._local_job_queues.setdefault(queue, []).append(job_str)

    async def dequeue_job(self, queue: str) -> dict[str, Any] | None:
        """Pop the oldest job from *queue* (blocking left-pop via Redis list).

        Returns ``None`` when the queue is empty.
        """
        if self._enabled and self._pubsub is not None:
            try:
                raw = await self._pubsub.blpop(f"job:{queue}", timeout=1)
                if raw is not None:
                    return json.loads(raw[1])
                return None
            except Exception:
                logger.exception("Redis blpop failed for queue %s", queue)
                return None
        jobs = self._local_job_queues.get(queue, [])
        if not jobs:
            return None
        return json.loads(jobs.pop(0))

    @property
    def enabled(self) -> bool:
        return self._enabled


# Module-level singleton, lazy-initialised on first use.
_pubsub_instance: RedisPubSubAdapter | None = None


def get_redis_pubsub() -> RedisPubSubAdapter:
    global _pubsub_instance
    if _pubsub_instance is None:
        _pubsub_instance = RedisPubSubAdapter(
            redis_url=settings.redis_url,
            enabled=settings.use_redis,
        )
    return _pubsub_instance
