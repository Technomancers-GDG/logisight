from __future__ import annotations

from datetime import UTC, datetime

from schemas import RouteOptionRead, TelemetrySimulationResponse


class TelemetrySimulationService:
    """Simple deterministic telemetry estimates for route monitoring demos."""

    FUEL_LITERS_PER_KM = {
        "road": 0.34,
        "rail": 0.08,
        "water": 0.045,
    }
    EMISSIONS_KG_PER_LITER = 2.68

    def simulate(
        self,
        *,
        route: RouteOptionRead,
        payload_tons: float,
        shipment_id: int | None = None,
        route_id: int | None = None,
    ) -> TelemetrySimulationResponse:
        fuel = 0.0
        details: dict[str, float] = {}
        for segment in route.segments:
            # If distance is missing, estimate distance from mode speed and time.
            distance = segment.distance_km
            if distance is None:
                speed = 42.0 if segment.transport_mode == "road" else 55.0 if segment.transport_mode == "rail" else 18.0
                distance = speed * (segment.time / 60.0)
            load_factor = 1.0 + min(payload_tons, 60.0) / 300.0
            segment_fuel = distance * self.FUEL_LITERS_PER_KM.get(segment.transport_mode, 0.34) * load_factor
            fuel += segment_fuel
            details[segment.edge_id] = round(segment_fuel, 2)

        delay = min(240.0, route.total_time * min(route.total_risk, 1.0) * 0.18)
        emissions = fuel * self.EMISSIONS_KG_PER_LITER
        return TelemetrySimulationResponse(
            shipment_id=shipment_id,
            route_id=route_id,
            fuel_usage_liters=round(fuel, 2),
            delay_minutes=round(delay, 2),
            emissions_kg=round(emissions, 2),
            generated_at=datetime.now(UTC).replace(tzinfo=None),
            details={
                "segment_fuel_liters": details,
                "risk_delay_model": "total_time * capped_total_risk * 0.18",
            },
        )
