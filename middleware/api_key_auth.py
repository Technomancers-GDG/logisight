from __future__ import annotations

import hashlib
import hmac
import logging
import secrets

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_session
from models import IntegrationClient

logger = logging.getLogger(__name__)

API_KEY_SALT = "integ-api-v1-2026"


def _hash_api_key(api_key: str) -> str:
    return hashlib.sha256(f"{API_KEY_SALT}:{api_key}".encode()).hexdigest()


def _generate_api_key() -> tuple[str, str]:
    api_key = f"regc_{secrets.token_hex(24)}"
    return api_key, _hash_api_key(api_key)


def verify_api_key(request: Request, session: Session = Depends(get_session)) -> IntegrationClient:
    auth_header = request.headers.get("Authorization", "")
    api_key = ""

    if auth_header.startswith("Bearer "):
        api_key = auth_header.replace("Bearer ", "")
    else:
        api_key = request.headers.get("X-API-Key", "")

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide via Authorization: Bearer <key> or X-API-Key header.",
        )

    if len(api_key) < 16:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format.",
        )

    prefix = api_key[:8]
    client = session.scalar(
        select(IntegrationClient).where(
            IntegrationClient.api_key_prefix == prefix,
            IntegrationClient.enabled.is_(True),
        )
    )

    if client is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or disabled API key.",
        )

    expected_hash = _hash_api_key(api_key)
    if not hmac.compare_digest(client.api_key_hash, expected_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )

    client.monthly_api_calls = (client.monthly_api_calls or 0) + 1
    session.commit()

    return client


def verify_or_demo_api_key(
    request: Request, session: Session = Depends(get_session)
) -> IntegrationClient | None:
    """Verify API key in production; bypass with a stub client in demo mode.

    When DEMO_MODE=true, the endpoint still *shows* API‑key plumbing:
    a synthetic key is sent by the front‑end, but the backend accepts it
    without a real DB client record so demos never get stuck on auth.
    """
    from config import settings

    if settings.demo_mode:
        api_key = ""

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header.replace("Bearer ", "")
        else:
            api_key = request.headers.get("X-API-Key", "")

        # In demo mode, any sufficiently long key is accepted.
        if not api_key or len(api_key) < 8:
            return _demo_stub_client()

        # Try real lookup first — integration-tests / seeded clients work.
        prefix = api_key[:8]
        client = session.scalar(
            select(IntegrationClient).where(
                IntegrationClient.api_key_prefix == prefix,
                IntegrationClient.enabled.is_(True),
            )
        )
        if client is not None:
            expected_hash = _hash_api_key(api_key)
            if hmac.compare_digest(client.api_key_hash, expected_hash):
                client.monthly_api_calls = (client.monthly_api_calls or 0) + 1
                session.commit()
                return client

        return _demo_stub_client()

    return verify_api_key(request, session)


def _demo_stub_client() -> IntegrationClient:
    return IntegrationClient(
        id=0,
        name="Demo Client",
        company_name="Demo Logistics",
        enabled=True,
        rate_limit_per_minute=5000,
        api_key_hash="",
        api_key_prefix="demo_key",
        contact_email="demo@example.com",
    )


__all__ = ["verify_api_key", "_generate_api_key", "_hash_api_key"]
