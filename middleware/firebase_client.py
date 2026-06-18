"""Firebase client auth — resolves Firebase UID to IntegrationClient."""
from __future__ import annotations

import base64
import json
import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from database import get_session
from models import IntegrationClient

logger = logging.getLogger(__name__)


def _decode_unverified_firebase_token(token: str) -> Optional[dict]:
    """Decode Firebase JWT claims without verification for local/demo use only."""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("utf-8"))
        claims = json.loads(decoded.decode("utf-8"))
        if isinstance(claims, dict):
            if "user_id" in claims and "uid" not in claims:
                claims["uid"] = claims["user_id"]
            if "sub" in claims and "uid" not in claims:
                claims["uid"] = claims["sub"]
            return claims
        return None
    except Exception as e:
        logger.error(f"[DIAG] _decode_unverified_firebase_token error: {e}")
        return None


def _verify_firebase_token(request: Request) -> Optional[dict]:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.replace("Bearer ", "", 1)
    
    if settings.firebase_enabled:
        try:
            from main import _init_firebase
            from firebase_admin import auth as firebase_auth
            _init_firebase()
            decoded = firebase_auth.verify_id_token(token, clock_skew_seconds=60)
            return decoded
        except Exception as e:
            logger.error(f"[DIAG] Firebase verification failed: {e}")
            return None
    
    return _decode_unverified_firebase_token(token)


def resolve_firebase_uid(request: Request) -> Optional[str]:
    token = _verify_firebase_token(request)
    if token is None:
        return None
    return token.get("uid")


async def get_client_from_firebase(
    request: Request, session: Session = Depends(get_session)
) -> IntegrationClient:
    from middleware.api_key_auth import verify_api_key
    try:
        # Allow the UI to authenticate using an API key (e.g. from 1-Click Signup)
        client = verify_api_key(request, session)
        return client
    except HTTPException:
        pass

    uid = resolve_firebase_uid(request)
    if uid is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid Firebase authentication required",
        )
    client = _find_or_link_client(session, uid, request)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No client account found. Complete onboarding first.",
        )
    if not client.enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Client account disabled"
        )
    return client


def _find_or_link_client(session: Session, uid: str, request: Optional[Request] = None) -> Optional[IntegrationClient]:
    """Find client by firebase_uid. If not found, try to link by email from old JWT accounts."""
    client = session.scalar(
        select(IntegrationClient).where(IntegrationClient.firebase_uid == uid)
    )
    if client is not None:
        return client

    # Migration: link existing JWT-era accounts by email
    token = _verify_firebase_token(request) if request else None
    email = token.get("email", "").strip().lower() if token else ""
    if email:
        client = session.scalar(
            select(IntegrationClient).where(
                IntegrationClient.firebase_uid.is_(None),
                IntegrationClient.contact_email == email,
            )
        )
        if client is not None:
            client.firebase_uid = uid
            session.commit()
            session.refresh(client)
            logger.info("Linked Firebase UID %s to existing client %s via email %s", uid, client.id, email)
            return client
    return None


def get_firebase_uid_optional(request: Request) -> Optional[str]:
    return resolve_firebase_uid(request)


async def get_or_create_client(
    request: Request, session: Session = Depends(get_session)
) -> IntegrationClient:
    from middleware.api_key_auth import verify_api_key
    try:
        # Allow the UI to authenticate using an API key (e.g. from 1-Click Signup)
        client = verify_api_key(request, session)
        return client
    except HTTPException:
        pass

    uid = resolve_firebase_uid(request)
    if uid is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid API Key or Firebase authentication required",
        )
    client = _find_or_link_client(session, uid, request)
    if client is not None:
        return client

    import hashlib, secrets
    from middleware.api_key_auth import API_KEY_SALT

    api_key = f"regc_{secrets.token_hex(24)}"
    api_key_hash = hashlib.sha256(f"{API_KEY_SALT}:{api_key}".encode()).hexdigest()
    api_key_prefix = api_key[:8]
    token = _verify_firebase_token(request)
    email = token.get("email", "") if token else ""
    name = token.get("name", email) if token else email

    client = IntegrationClient(
        name=name or email or "Client",
        company_name=name or email or "Client",
        firebase_uid=uid,
        contact_email=email,
        api_key_hash=api_key_hash,
        api_key_prefix=api_key_prefix,
        rate_limit_per_minute=1000,
        enabled=True,
    )
    session.add(client)
    session.commit()
    session.refresh(client)
    return client
