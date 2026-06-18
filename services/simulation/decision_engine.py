"""Decision engine for scoring dispatch options during simulation."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from models import Facility, Objective, PortLink, RouteTemplate, Vehicle
from services.simulation.models import CandidateDecision


class DecisionEngine:
    def effective_available_units(
        self,
        facility_id: int,
        facilities: dict[int, Facility],
        port_links: list[PortLink],
        inbound_reserved: dict[int, int],
    ) -> int:
        facility = facilities[facility_id]
        reserved_total = inbound_reserved.get(facility_id, 0)
        if facility.facility_type != "warehouse":
            return facility.base_capacity_units - facility.current_inventory_units - reserved_total

        linked_links = [link for link in port_links if link.warehouse_id == facility_id and link.active]
        static_reserved = sum(link.reserved_capacity_units for link in linked_links)
        dynamic_spillover = 0
        for link in linked_links:
            port = facilities[link.port_id]
            threshold_units = port.base_capacity_units * (link.spillover_threshold_pct / 100)
            port_pressure = max(0.0, port.current_inventory_units - threshold_units)
            dynamic_spillover += int(min(link.max_spillover_units, port_pressure))
        return (
            facility.base_capacity_units
            - facility.current_inventory_units
            - static_reserved
            - dynamic_spillover
            - reserved_total
        )

    def score_dispatch_options(
        self,
        *,
        sim_time: datetime,
        vehicle: Vehicle,
        objective: Objective,
        current_facility: Facility,
        facilities: dict[int, Facility],
        port_links: list[PortLink],
        inbound_reserved: dict[int, int],
        route_data: dict[int, RouteTemplate],
        risk_lookup: dict[int, dict[str, float]],
    ) -> CandidateDecision:
        original_destination_id = objective.destination_facility_id
        baseline_route = route_data[original_destination_id]
        baseline_risk = risk_lookup[original_destination_id]
        baseline_available = self.effective_available_units(
            original_destination_id, facilities, port_links, inbound_reserved
        )
        baseline_projected_units = baseline_available - vehicle.payload_capacity_units
        baseline_overload_risk = max(
            0.0,
            -baseline_projected_units / max(vehicle.payload_capacity_units, 1),
        )
        baseline_cost = self._total_cost(
            objective=objective,
            vehicle=vehicle,
            route=baseline_route,
            facility=facilities[original_destination_id],
            effective_available=baseline_available,
            risk=baseline_risk,
            original_duration=baseline_route.duration_minutes,
        )

        candidates: list[CandidateDecision] = []
        candidate_ids = [objective.destination_facility_id, *objective.fallback_facility_ids]
        for destination_id in candidate_ids:
            destination = facilities[destination_id]
            route = route_data[destination_id]
            risk = risk_lookup[destination_id]
            available_units = self.effective_available_units(
                destination_id, facilities, port_links, inbound_reserved
            )
            projected_units = available_units - vehicle.payload_capacity_units
            hard_blocked = (
                risk["route_risk"] >= 0.97
                or destination_id not in candidate_ids
                or destination.active is False
            )
            if hard_blocked:
                continue
            overload_risk = max(0.0, -projected_units / max(vehicle.payload_capacity_units, 1))
            if overload_risk > 0.75:
                continue

            action = "continue" if destination_id == objective.destination_facility_id else (
                "reroute_port" if destination.facility_type == "port" else "reroute_warehouse"
            )
            cost = self._total_cost(
                objective=objective,
                vehicle=vehicle,
                route=route,
                facility=destination,
                effective_available=available_units,
                risk=risk,
                original_duration=baseline_route.duration_minutes,
            )
            breakdown = {
                "overload_risk": round(overload_risk, 3),
                "added_travel_minutes": round(
                    max(0.0, route.duration_minutes * risk["eta_multiplier"] - baseline_route.duration_minutes), 2
                ),
                "predicted_idle_minutes": round(max(0.0, -projected_units) * 0.18, 2),
                "co2_delta_kg": round(
                    max(0.0, route.distance_km - baseline_route.distance_km) * vehicle.emission_kg_per_km, 2
                ),
                "sla_penalty": round(
                    max(
                        0.0,
                        route.duration_minutes * risk["eta_multiplier"]
                        + objective.loading_duration_minutes
                        + objective.unloading_duration_minutes
                        - objective.sla_minutes,
                    )
                    / max(objective.sla_minutes, 1),
                    3,
                ),
                "event_severity": round(risk["route_risk"], 3),
                "downstream_congestion": round(
                    facilities[destination_id].current_inventory_units
                    / max(facilities[destination_id].base_capacity_units, 1),
                    3,
                ),
                "baseline_overload_risk": round(baseline_overload_risk, 3),
                "baseline_event_severity": round(baseline_risk["route_risk"], 3),
            }
            explanation, structured, counterfactual = self._explain(action, destination, breakdown, risk)
            candidates.append(
                CandidateDecision(
                    action=action,
                    destination_id=destination_id,
                    score=cost,
                    baseline_cost=baseline_cost,
                    recommended_cost=cost,
                    explanation=explanation,
                    breakdown=breakdown,
                    travel_minutes=route.duration_minutes,
                    route_risk=risk["route_risk"],
                    eta_multiplier=risk["eta_multiplier"],
                    structured_explanation=structured,
                    counterfactual=counterfactual,
                )
            )

        original_available = self.effective_available_units(
            original_destination_id, facilities, port_links, inbound_reserved
        )
        wait_minutes = max(
            40.0,
            (vehicle.payload_capacity_units - max(original_available, 0)) * 0.12
            + baseline_risk["route_risk"] * 60,
        )
        candidates.append(
            CandidateDecision(
                action="wait",
                destination_id=current_facility.id,
                score=baseline_cost + wait_minutes * 0.65,
                baseline_cost=baseline_cost,
                recommended_cost=baseline_cost + wait_minutes * 0.65,
                explanation=(
                    f"Wait at {current_facility.name} for {int(wait_minutes)} minutes to reduce "
                    f"destination overload and port spillover pressure."
                ),
                breakdown={
                    "overload_risk": round(max(0.0, -original_available / max(vehicle.payload_capacity_units, 1)), 3),
                    "added_travel_minutes": 0.0,
                    "predicted_idle_minutes": round(wait_minutes, 2),
                    "co2_delta_kg": 0.0,
                    "sla_penalty": round(wait_minutes / max(objective.sla_minutes, 1), 3),
                    "event_severity": round(baseline_risk["route_risk"], 3),
                    "downstream_congestion": round(
                        facilities[original_destination_id].current_inventory_units
                        / max(facilities[original_destination_id].base_capacity_units, 1),
                        3,
                    ),
                    "baseline_overload_risk": round(baseline_overload_risk, 3),
                    "baseline_event_severity": round(baseline_risk["route_risk"], 3),
                },
                travel_minutes=0.0,
                route_risk=baseline_risk["route_risk"],
                eta_multiplier=1.0,
                structured_explanation={
                    "insights": ["Waiting reduces pressure downstream", f"Facility capacity constrained by {max(0, vehicle.payload_capacity_units - original_available)} units"],
                    "impact": [f"Idle time increased by {int(wait_minutes)} minutes", "Avoided severe downstream congestion"]
                },
                counterfactual="If dispatch proceeded -> High overload risk and gridlock at destination.",
            )
        )
        candidates.append(
            CandidateDecision(
                action="defer_dispatch",
                destination_id=current_facility.id,
                score=baseline_cost + objective.dispatch_interval_minutes * 0.82,
                baseline_cost=baseline_cost,
                recommended_cost=baseline_cost + objective.dispatch_interval_minutes * 0.82,
                explanation=(
                    "Defer this dispatch cycle and let downstream lanes clear before sending "
                    "another loaded vehicle."
                ),
                breakdown={
                    "overload_risk": 0.0,
                    "added_travel_minutes": 0.0,
                    "predicted_idle_minutes": float(objective.dispatch_interval_minutes),
                    "co2_delta_kg": 0.0,
                    "sla_penalty": round(objective.dispatch_interval_minutes / max(objective.sla_minutes, 1), 3),
                    "event_severity": round(baseline_risk["route_risk"], 3),
                    "downstream_congestion": 0.0,
                    "baseline_overload_risk": round(baseline_overload_risk, 3),
                    "baseline_event_severity": round(baseline_risk["route_risk"], 3),
                },
                travel_minutes=0.0,
                route_risk=baseline_risk["route_risk"],
                eta_multiplier=1.0,
                structured_explanation={
                    "insights": ["Lane clearing needed", "Severe bottleneck detected"],
                    "impact": [f"Dispatch deferred by {int(objective.dispatch_interval_minutes)} minutes"]
                },
                counterfactual="If dispatch proceeded -> Guaranteed bottleneck and SLA violation.",
            )
        )
        return min(candidates, key=lambda candidate: candidate.score)

    def _total_cost(
        self,
        *,
        objective: Objective,
        vehicle: Vehicle,
        route: RouteTemplate,
        facility: Facility,
        effective_available: int,
        risk: dict[str, float],
        original_duration: float,
    ) -> float:
        overload_penalty = max(0.0, vehicle.payload_capacity_units - max(effective_available, 0)) * 5.0
        added_travel = max(0.0, route.duration_minutes * risk["eta_multiplier"] - original_duration) * 1.50
        congestion_penalty = (
            facility.current_inventory_units / max(facility.base_capacity_units, 1)
        ) * 150.0
        co2_penalty = route.distance_km * vehicle.emission_kg_per_km * 0.05
        minutes_late = max(
            0.0,
            route.duration_minutes * risk["eta_multiplier"]
            + objective.loading_duration_minutes
            + objective.unloading_duration_minutes
            - objective.sla_minutes,
        )
        sla_penalty = (500.0 if minutes_late > 0 else 0.0) + (minutes_late * 2.0)
        event_penalty = risk["route_risk"] * 1000.0
        return round(
            overload_penalty + added_travel + congestion_penalty + co2_penalty + sla_penalty + event_penalty,
            2,
        )

    def _explain(
        self,
        action: str,
        destination: Facility,
        breakdown: dict[str, float],
        risk: dict[str, float],
    ) -> tuple[str, dict[str, Any], str]:
        if action == "continue":
            explanation = (
                f"Continue to {destination.name}; capacity remains viable and combined weather/news "
                f"risk stays at {risk['route_risk']:.2f}."
            )
            structured = {
                "insights": ["Capacity is viable", "Risk is acceptable"],
                "impact": ["No immediate intervention required"]
            }
            counterfactual = "If baseline was rejected -> Unnecessary delay or cost added."
            return explanation, structured, counterfactual
            
        explanation = (
            f"{action.replace('_', ' ')} to {destination.name} because overload risk is "
            f"{breakdown['overload_risk']:.2f}, event severity is {breakdown['event_severity']:.2f}, "
            f"and downstream congestion is {breakdown['downstream_congestion']:.2f}."
        )
        
        impact = []
        if breakdown.get("added_travel_minutes", 0) > 0:
            impact.append(f"Travel time increased by {breakdown['added_travel_minutes']} minutes")
        else:
            impact.append("Travel time optimal")
            
        if breakdown.get("overload_risk", 0) < breakdown.get("baseline_overload_risk", 0):
            impact.append("Overload risk reduced compared to baseline")
            
        if breakdown.get("co2_delta_kg", 0) < 0:
            impact.append(f"CO2 footprint reduced by {abs(breakdown['co2_delta_kg'])} kg")
            
        structured = {
            "insights": [
                f"Event severity: {breakdown.get('event_severity', 0):.2f}",
                f"Baseline overload risk was {breakdown.get('baseline_overload_risk', 0):.2f}"
            ],
            "impact": impact
        }
        
        counterfactual = f"If baseline was selected -> Potential overload (risk: {breakdown.get('baseline_overload_risk', 0):.2f}) or severe delay (risk: {breakdown.get('baseline_event_severity', 0):.2f})."
        
        return explanation, structured, counterfactual