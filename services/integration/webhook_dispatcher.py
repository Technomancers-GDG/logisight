from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import SessionLocal
from models import WebhookDelivery, WebhookSubscription

logger = logging.getLogger(__name__)


def _sign_payload(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


async def dispatch_webhook_event(event_type: str, payload: dict[str, Any]) -> None:
    try:
        db = SessionLocal()
        try:
            subscriptions = db.scalars(
                select(WebhookSubscription).where(
                    WebhookSubscription.enabled.is_(True),
                )
            ).all()
        finally:
            db.close()

        active = [s for s in subscriptions if event_type in _parse_events(s.events)]
        if not active:
            return

        tasks = [_deliver(sub, event_type, payload) for sub in active]
        await asyncio.gather(*tasks, return_exceptions=True)

    except Exception as exc:
        logger.error("Webhook dispatch failed for %s: %s", event_type, exc)


def _parse_events(events_json: str) -> list[str]:
    try:
        return json.loads(events_json)
    except (json.JSONDecodeError, TypeError):
        return [events_json]


def _serialize_payload(event_type: str, payload: dict[str, Any]) -> str:
    return json.dumps(
        {
            "event": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": payload,
        },
        default=str,
    )


async def _deliver(sub: WebhookSubscription, event_type: str, payload: dict[str, Any]) -> None:
    body_str = _serialize_payload(event_type, payload)
    body_bytes = body_str.encode()

    signature = _sign_payload(sub.secret, body_bytes) if sub.secret else ""

    for attempt in range(1, sub.retry_count + 2):
        try:
            async with httpx.AsyncClient(timeout=sub.timeout_seconds) as client:
                response = await client.post(
                    sub.callback_url,
                    content=body_bytes,
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Signature": signature,
                        "X-Webhook-Event": event_type,
                        "User-Agent": "REGC-Webhook/1.0",
                    },
                )

            _record_delivery(
                sub.id, event_type, body_str,
                response.status_code, response.text[:2000],
                success=200 <= response.status_code < 300,
                attempt_number=attempt,
            )

            if 200 <= response.status_code < 300:
                return

            logger.warning(
                "Webhook delivery attempt %d/%d to %s returned %d",
                attempt, sub.retry_count + 1, sub.callback_url, response.status_code,
            )

        except Exception as exc:
            _record_delivery(
                sub.id, event_type, body_str,
                response_status=None, response_body=str(exc)[:2000],
                success=False, attempt_number=attempt,
            )
            logger.warning(
                "Webhook delivery attempt %d/%d to %s failed: %s",
                attempt, sub.retry_count + 1, sub.callback_url, exc,
            )

        if attempt <= sub.retry_count:
            await asyncio.sleep(min(2 ** attempt * 5, 300))

    logger.error("Webhook %s all %d attempts exhausted for %s", event_type, sub.retry_count + 1, sub.callback_url)


def _record_delivery(
    subscription_id: int,
    event_type: str,
    payload: str,
    response_status: int | None,
    response_body: str | None,
    success: bool,
    attempt_number: int,
) -> None:
    try:
        db = SessionLocal()
        try:
            delivery = WebhookDelivery(
                subscription_id=subscription_id,
                event_type=event_type,
                payload=payload,
                response_status=response_status,
                response_body=response_body,
                success=success,
                attempt_number=attempt_number,
            )
            db.add(delivery)
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.error("Failed to record webhook delivery: %s", exc)
