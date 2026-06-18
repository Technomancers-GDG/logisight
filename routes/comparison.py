from typing import Any

from fastapi import APIRouter, Query
from database import SessionLocal
from app_state import simulation_engine

router = APIRouter(prefix="/api/comparison", tags=["Comparison"])


def _build_scenario() -> "Scenario":
    """Build a scenario object from the simulation's active disruption events.
    
    If no active disruptions exist, returns a default mild scenario so the
    comparison endpoint always returns meaningful data.
    """
    active = simulation_engine._active_event_feed() if hasattr(simulation_engine, "_active_event_feed") else []
    top_disruption = active[0] if active else None

    if top_disruption:
        city = top_disruption.get("city", "")
        severity = min(0.99, max(0.0, top_disruption.get("impact_score", 0.5)))
        eta_multiplier = 1.0 + severity * 0.4
    else:
        city = ""
        severity = 0.05
        eta_multiplier = 1.02

    return Scenario(
        event_city=city,
        severity=severity,
        eta_multiplier=eta_multiplier,
    )


class Scenario:
    """Lightweight scenario container for comparison engine."""
    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


@router.get("/summary")
def get_comparison_summary() -> dict[str, Any]:
    with SessionLocal() as session:
        scenario = _build_scenario()
        result = simulation_engine.compare_scenario(session, scenario)
        if "trips" in result:
            del result["trips"]
        return result


@router.get("/per-trip")
def get_per_trip_comparison() -> dict[str, Any]:
    with SessionLocal() as session:
        scenario = _build_scenario()
        result = simulation_engine.compare_scenario(session, scenario)
        return {"trips": result.get("trips", [])}


@router.get("/by-objective")
def get_comparison_by_objective() -> dict[str, Any]:
    with SessionLocal() as session:
        scenario = _build_scenario()
        result = simulation_engine.compare_scenario(session, scenario)
        trips = result.get("trips", [])

        by_obj: dict[str, list[dict[str, Any]]] = {}
        for t in trips:
            obj_id = str(t["objective_id"])
            if obj_id not in by_obj:
                by_obj[obj_id] = []
            by_obj[obj_id].append(t)

        return {"objectives": by_obj}


@router.get("/by-disruption")
def get_comparison_by_disruption() -> dict[str, Any]:
    with SessionLocal() as session:
        calm_scenario = Scenario(event_city="", severity=0.0, eta_multiplier=1.0)
        disrupted_scenario = _build_scenario()

        calm_res = simulation_engine.compare_scenario(session, calm_scenario)
        disrupted_res = simulation_engine.compare_scenario(session, disrupted_scenario)

        def _with_abs(r: dict[str, Any]) -> dict[str, Any]:
            return {
                "baseline": r.get("baseline", {}),
                "ai": r.get("ai", {}),
                "improvement": r.get("improvement", {}),
            }

        return {
            "calm": _with_abs(calm_res),
            "disrupted": _with_abs(disrupted_res),
        }
