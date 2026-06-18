from __future__ import annotations

from datetime import UTC, datetime
from statistics import mean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import DriverDecision, DriverIncident, DriverMetric, DriverProfile, LogisticsRoute
from schemas import RouteOptionRead
from services.logistics_telemetry import TelemetrySimulationService


class DriverPerformanceService:
    """Explainable driver scoring from route execution and telemetry estimates."""

    def __init__(self, telemetry_service: TelemetrySimulationService | None = None) -> None:
        self.telemetry_service = telemetry_service or TelemetrySimulationService()

    def get_or_compute_driver_metrics(
        self,
        session: Session,
        driver_id: int,
        *,
        refresh: bool = False,
    ) -> DriverMetric:
        driver = session.get(DriverProfile, driver_id)
        if driver is None:
            raise ValueError(f"Driver {driver_id} does not exist")

        existing = session.scalar(select(DriverMetric).where(DriverMetric.driver_id == driver_id))
        if existing is not None and not refresh:
            return existing
        return self.compute_and_store_driver_metrics(session, driver)

    def list_driver_metrics(self, session: Session, *, refresh: bool = False) -> list[DriverMetric]:
        drivers = session.scalars(select(DriverProfile).where(DriverProfile.active.is_(True)).order_by(DriverProfile.id)).all()
        metrics = [
            self.get_or_compute_driver_metrics(session, driver.id, refresh=refresh)
            for driver in drivers
        ]
        return sorted(metrics, key=lambda metric: metric.reliability_score, reverse=True)

    def compute_and_store_driver_metrics(self, session: Session, driver: DriverProfile) -> DriverMetric:
        samples = self._route_samples(session, driver.id)
        incident_risk = self._incident_risk(session, driver.id)
        decision_adjustment = self._decision_adjustment(session, driver.id)

        if samples:
            efficiency_score = mean(sample["efficiency_score"] for sample in samples)
            idle_time_score = mean(sample["idle_time_score"] for sample in samples)
            route_adherence_score = mean(sample["route_adherence_score"] for sample in samples)
            fuel_score = mean(sample["fuel_score"] for sample in samples)
            route_risk = mean(sample["risk_score"] for sample in samples)
        else:
            # Cold-start uses the existing driver profile as a prior, so new
            # drivers are usable but not treated as top performers without data.
            prior = min(1.0, max(0.35, float(driver.override_rating or 0.75)))
            confidence = min(1.0, max(0.0, float(driver.confidence or 0.5)))
            efficiency_score = 0.68 + prior * 0.18
            idle_time_score = 0.72 + confidence * 0.12
            route_adherence_score = 0.70 + min(1.0, float(driver.accept_recommendation_bias or 0.5)) * 0.16
            fuel_score = 0.74
            route_risk = 0.25

        risk_score = self._clamp(route_risk + incident_risk - decision_adjustment * 0.08)
        reliability_score = self._clamp(
            efficiency_score * 0.30
            + route_adherence_score * 0.25
            + idle_time_score * 0.20
            + fuel_score * 0.10
            + (1.0 - risk_score) * 0.15
            + decision_adjustment * 0.05
        )

        metric = session.scalar(select(DriverMetric).where(DriverMetric.driver_id == driver.id))
        if metric is None:
            metric = DriverMetric(driver_id=driver.id)
            session.add(metric)

        metric.efficiency_score = round(efficiency_score, 3)
        metric.reliability_score = round(reliability_score, 3)
        metric.route_adherence_score = round(route_adherence_score, 3)
        metric.idle_time_score = round(idle_time_score, 3)
        metric.risk_score = round(risk_score, 3)
        metric.classification_label = self.classify(reliability_score)
        metric.sample_count = len(samples)
        metric.scoring_metadata = {
            "formula": "0.30*efficiency + 0.25*adherence + 0.20*idle + 0.10*fuel + 0.15*(1-risk) + 0.05*driver_decision_adjustment",
            "route_sample_count": len(samples),
            "incident_risk": round(incident_risk, 3),
            "driver_decision_adjustment": round(decision_adjustment, 3),
            "latest_sample": samples[0] if samples else None,
        }
        metric.updated_at = datetime.now(UTC).replace(tzinfo=None)
        session.commit()
        session.refresh(metric)
        return metric

    def recommend_driver_for_assignment(
        self,
        session: Session,
        *,
        high_value: bool = False,
        time_sensitive: bool = False,
    ) -> DriverMetric | None:
        metrics = self.list_driver_metrics(session, refresh=False)
        if not metrics:
            return None

        if high_value or time_sensitive:
            high_reliability = [metric for metric in metrics if metric.reliability_score >= 0.8]
            return high_reliability[0] if high_reliability else metrics[0]
        return metrics[0]

    def _route_samples(self, session: Session, driver_id: int) -> list[dict[str, Any]]:
        routes = session.scalars(
            select(LogisticsRoute)
            .where(LogisticsRoute.assigned_driver_id == driver_id)
            .order_by(LogisticsRoute.updated_at.desc())
            .limit(25)
        ).all()
        samples: list[dict[str, Any]] = []
        for route in routes:
            try:
                route_option = self._route_option_from_model(route)
            except Exception:
                continue
            metadata = dict(route.route_data or {}).get("metadata", {}) or {}
            telemetry = self.telemetry_service.simulate(
                route=route_option,
                payload_tons=float(metadata.get("payload_tons", 20.0) or 20.0),
                shipment_id=route.shipment_id,
                route_id=route.id,
            )
            expected_time = max(float(route.total_time or route_option.total_time or 1.0), 1.0)
            actual_time = float(
                metadata.get(
                    "actual_time_minutes",
                    expected_time + telemetry.delay_minutes,
                )
                or expected_time
            )
            idle_time = float(
                metadata.get(
                    "idle_time_minutes",
                    max(0.0, telemetry.delay_minutes * 0.35 + self._route_wait_minutes(route_option)),
                )
                or 0.0
            )
            route_deviation = float(
                metadata.get(
                    "route_deviation_pct",
                    max(0.0, min(0.35, route_option.total_risk * 0.08)),
                )
                or 0.0
            )
            actual_fuel = float(metadata.get("actual_fuel_liters", telemetry.fuel_usage_liters) or telemetry.fuel_usage_liters)
            expected_fuel = max(float(telemetry.fuel_usage_liters or 1.0), 1.0)
            fuel_ratio = actual_fuel / expected_fuel

            samples.append(
                {
                    "route_id": route.id,
                    "expected_time": round(expected_time, 2),
                    "actual_time": round(actual_time, 2),
                    "idle_time": round(idle_time, 2),
                    "route_deviation": round(route_deviation, 3),
                    "fuel_usage_liters": round(actual_fuel, 2),
                    "efficiency_score": self._efficiency_score(actual_time, expected_time),
                    "idle_time_score": self._idle_score(idle_time, expected_time),
                    "route_adherence_score": self._adherence_score(route_deviation),
                    "fuel_score": self._fuel_score(fuel_ratio),
                    "risk_score": self._sample_risk_score(route_option.total_risk, route_deviation, idle_time, expected_time),
                }
            )
        return samples

    @staticmethod
    def _route_option_from_model(route: LogisticsRoute) -> RouteOptionRead:
        data = dict(route.route_data or {})
        data["route_id"] = route.id
        return RouteOptionRead(**data)

    @staticmethod
    def _route_wait_minutes(route: RouteOptionRead) -> float:
        return sum(
            float(segment.switching_delay_applied or 0.0) + float(segment.time_window_violation_minutes or 0.0)
            for segment in route.segments
        )

    def _incident_risk(self, session: Session, driver_id: int) -> float:
        incidents = session.scalars(
            select(DriverIncident)
            .where(DriverIncident.driver_profile_id == driver_id)
            .order_by(DriverIncident.reported_at.desc())
            .limit(10)
        ).all()
        if not incidents:
            return 0.0
        return self._clamp(mean(float(incident.severity or 0.0) for incident in incidents) * 0.30)

    def _decision_adjustment(self, session: Session, driver_id: int) -> float:
        decisions = session.scalars(
            select(DriverDecision)
            .where(DriverDecision.driver_profile_id == driver_id)
            .order_by(DriverDecision.decided_at.desc())
            .limit(20)
        ).all()
        if not decisions:
            return 0.0
        accepted = sum(1 for decision in decisions if decision.decision == "accepted")
        return accepted / max(len(decisions), 1)

    def _efficiency_score(self, actual_time: float, expected_time: float) -> float:
        ratio = actual_time / max(expected_time, 1.0)
        if ratio <= 1.0:
            return 1.0
        return self._clamp(1.0 - (ratio - 1.0) * 1.4)

    def _idle_score(self, idle_time: float, expected_time: float) -> float:
        idle_ratio = idle_time / max(expected_time, 1.0)
        return self._clamp(1.0 - idle_ratio * 2.0)

    def _adherence_score(self, route_deviation: float) -> float:
        return self._clamp(1.0 - route_deviation * 2.5)

    def _fuel_score(self, fuel_ratio: float) -> float:
        if fuel_ratio <= 1.0:
            return 1.0
        return self._clamp(1.0 - (fuel_ratio - 1.0) * 1.2)

    def _sample_risk_score(
        self,
        route_risk: float,
        route_deviation: float,
        idle_time: float,
        expected_time: float,
    ) -> float:
        idle_ratio = idle_time / max(expected_time, 1.0)
        return self._clamp(route_risk * 0.45 + route_deviation * 0.35 + idle_ratio * 0.20)

    @staticmethod
    def classify(reliability_score: float) -> str:
        if reliability_score > 0.8:
            return "high"
        if reliability_score > 0.6:
            return "medium"
        return "low"

    @staticmethod
    def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
        return min(upper, max(lower, float(value)))
