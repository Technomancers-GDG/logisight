"""Client portal — Firebase-based auth (status check, onboarding setup)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_session
from middleware.firebase_client import (
    _find_or_link_client,
    get_client_from_firebase,
    get_or_create_client,
    resolve_firebase_uid,
)
from models import (
    ClientSimulation,
    DriverProfile,
    Facility,
    IntegrationClient,
    Objective,
    Vehicle,
)

router = APIRouter(prefix="/api/auth", tags=["Client Auth"])


@router.get("/client-status")
def client_status(request: Request, session: Session = Depends(get_session)):
    """Check if the current Firebase user has a client account and fleet data."""
    uid = resolve_firebase_uid(request)
    if uid is None:
        return {"authenticated": False, "has_fleet": False}

    # Auto-link existing JWT-era accounts by email if no firebase_uid match
    client = _find_or_link_client(session, uid, request)

    if client is None:
        return {"authenticated": True, "has_fleet": False}

    cid = client.id
    has_facilities = session.scalar(
        select(Facility.id).where(Facility.client_id == cid).limit(1)
    ) is not None
    has_vehicles = session.scalar(
        select(Vehicle.id).where(Vehicle.client_id == cid).limit(1)
    ) is not None
    has_drivers = session.scalar(
        select(DriverProfile.id).where(DriverProfile.client_id == cid).limit(1)
    ) is not None
    has_objectives = session.scalar(
        select(Objective.id).where(Objective.client_id == cid).limit(1)
    ) is not None

    sim = session.scalar(
        select(ClientSimulation).where(ClientSimulation.client_id == cid)
    )

    return {
        "authenticated": True,
        "has_fleet": all([has_facilities, has_vehicles, has_drivers, has_objectives]),
        "client_id": cid,
        "company_name": client.company_name or client.name,
        "simulation_status": sim.status if sim else None,
    }


@router.post("/onboarding-setup")
def onboarding_setup(request: Request, session: Session = Depends(get_session)):
    """Create IntegrationClient on first Firebase sign-in. Called before CSV upload."""
    uid = resolve_firebase_uid(request)
    if uid is None:
        raise HTTPException(status_code=401, detail="Firebase auth required")

    existing = session.scalar(
        select(IntegrationClient).where(IntegrationClient.firebase_uid == uid)
    )
    if existing is not None:
        return {"created": False, "client_id": existing.id}

    # The get_or_create_client in upload handles actual creation.
    # This endpoint just confirms the user is authenticated.
    return {"created": False, "ready": True}


from pydantic import BaseModel
import secrets
import hashlib
from middleware.api_key_auth import API_KEY_SALT

class QuickRegisterRequest(BaseModel):
    company_name: str
    email: str

@router.post("/quick-register")
def quick_register(req: QuickRegisterRequest, session: Session = Depends(get_session)):
    """1-Click signup for demo purposes. Generates an IntegrationClient instantly."""
    api_key = f"regc_{secrets.token_hex(24)}"
    api_key_hash = hashlib.sha256(f"{API_KEY_SALT}:{api_key}".encode()).hexdigest()
    
    client = IntegrationClient(
        name=req.company_name,
        company_name=req.company_name,
        contact_email=req.email,
        api_key_hash=api_key_hash,
        api_key_prefix=api_key[:8],
        rate_limit_per_minute=5000,
        enabled=True,
    )
    session.add(client)
    session.commit()
    session.refresh(client)
    
    return {
        "client_id": client.id,
        "company_name": client.company_name,
        "api_key": api_key,
        "slug": client.company_name.lower().replace(" ", "-"),
    }

@router.post("/login/firebase")
def login_firebase(
    request: Request,
    client: IntegrationClient = Depends(get_or_create_client),
):
    """Logs in using a Firebase token and returns client details."""
    return {
        "client_id": client.id,
        "company_name": client.company_name,
        "api_key": None,
        "slug": client.company_name.lower().replace(" ", "-"),
    }
