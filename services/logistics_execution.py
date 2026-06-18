from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import DriverProfile, LogisticsNode, LogisticsRoute, Shipment, Vehicle
from schemas import AssignRouteRequest, AssignmentResponse, RouteOptionRead


class LogisticsExecutionService:
    """Persists route assignment and reroute execution state."""

    def assign_route(self, session: Session, payload: AssignRouteRequest) -> AssignmentResponse:
        if payload.driver_id is not None and session.get(DriverProfile, payload.driver_id) is None:
            raise ValueError(f"Driver {payload.driver_id} does not exist")
        if payload.vehicle_id is not None and session.get(Vehicle, payload.vehicle_id) is None:
            raise ValueError(f"Vehicle {payload.vehicle_id} does not exist")

        origin_node = self._find_node(session, payload.origin_node_id)
        destination_node = self._find_node(session, payload.destination_node_id)
        shipment = self._get_or_create_shipment(session, payload, origin_node, destination_node)
        route = self._create_route(
            session=session,
            shipment=shipment,
            route_option=payload.route,
            origin_node=origin_node,
            destination_node=destination_node,
            origin_node_key=payload.origin_node_id,
            destination_node_key=payload.destination_node_id,
            driver_id=payload.driver_id,
            vehicle_id=payload.vehicle_id,
            status="assigned",
        )

        shipment.current_route_id = route.id
        shipment.status = "assigned"
        shipment.assigned_driver_id = payload.driver_id
        shipment.assigned_vehicle_id = payload.vehicle_id
        shipment.updated_at = datetime.now(UTC).replace(tzinfo=None)
        session.commit()
        session.refresh(shipment)
        session.refresh(route)

        response_route = payload.route.model_copy(update={"route_id": route.id})
        return AssignmentResponse(
            shipment_id=shipment.id,
            shipment_reference=shipment.shipment_reference,
            route_id=route.id,
            status=shipment.status,
            assigned_driver_id=shipment.assigned_driver_id,
            assigned_vehicle_id=shipment.assigned_vehicle_id,
            route=response_route,
        )

    def create_reroute(
        self,
        *,
        session: Session,
        shipment: Shipment,
        route_option: RouteOptionRead,
        origin_node_key: str,
        destination_node_key: str,
    ) -> LogisticsRoute:
        origin_node = self._find_node(session, origin_node_key)
        destination_node = self._find_node(session, destination_node_key)
        previous_route = None
        if shipment.current_route_id is not None:
            previous_route = session.get(LogisticsRoute, shipment.current_route_id)
            if previous_route is not None:
                previous_route.status = "superseded"

        route = self._create_route(
            session=session,
            shipment=shipment,
            route_option=route_option,
            origin_node=origin_node,
            destination_node=destination_node,
            origin_node_key=origin_node_key,
            destination_node_key=destination_node_key,
            driver_id=shipment.assigned_driver_id,
            vehicle_id=shipment.assigned_vehicle_id,
            status="rerouted",
        )
        shipment.current_route_id = route.id
        shipment.current_location_node_key = origin_node_key
        shipment.destination_node_key = destination_node_key
        shipment.destination_node_id = destination_node.id if destination_node else None
        shipment.status = "rerouted"
        shipment.updated_at = datetime.now(UTC).replace(tzinfo=None)
        session.commit()
        session.refresh(route)
        return route

    def route_option_from_model(self, route: LogisticsRoute) -> RouteOptionRead:
        data = dict(route.route_data or {})
        data["route_id"] = route.id
        return RouteOptionRead(**data)

    def _get_or_create_shipment(
        self,
        session: Session,
        payload: AssignRouteRequest,
        origin_node: LogisticsNode | None,
        destination_node: LogisticsNode | None,
    ) -> Shipment:
        if payload.shipment_id is not None:
            shipment = session.get(Shipment, payload.shipment_id)
            if shipment is None:
                raise ValueError(f"Shipment {payload.shipment_id} does not exist")
            return shipment

        reference = payload.shipment_reference or f"SHP-{uuid4().hex[:10].upper()}"
        existing = session.scalar(select(Shipment).where(Shipment.shipment_reference == reference))
        if existing is not None:
            return existing

        shipment = Shipment(
            shipment_reference=reference,
            origin_node_id=origin_node.id if origin_node else None,
            destination_node_id=destination_node.id if destination_node else None,
            origin_node_key=payload.origin_node_id,
            destination_node_key=payload.destination_node_id,
            current_location_node_key=payload.origin_node_id,
            cargo_type=payload.cargo_type,
            quantity_units=payload.quantity_units,
            status="created",
            assigned_driver_id=payload.driver_id,
            assigned_vehicle_id=payload.vehicle_id,
            shipment_metadata=dict(payload.metadata),
        )
        session.add(shipment)
        session.flush()
        return shipment

    def _create_route(
        self,
        *,
        session: Session,
        shipment: Shipment,
        route_option: RouteOptionRead,
        origin_node: LogisticsNode | None,
        destination_node: LogisticsNode | None,
        origin_node_key: str,
        destination_node_key: str,
        driver_id: int | None,
        vehicle_id: int | None,
        status: str,
    ) -> LogisticsRoute:
        route_key = "->".join(route_option.node_sequence)
        route = LogisticsRoute(
            route_key=route_key,
            shipment_id=shipment.id,
            origin_node_id=origin_node.id if origin_node else None,
            destination_node_id=destination_node.id if destination_node else None,
            origin_node_key=origin_node_key,
            destination_node_key=destination_node_key,
            node_sequence=route_option.node_sequence,
            edge_sequence=route_option.edge_sequence,
            transport_modes=route_option.transport_modes,
            total_cost=route_option.total_cost,
            total_time=route_option.total_time,
            total_risk=route_option.total_risk,
            score=route_option.score,
            status=status,
            assigned_driver_id=driver_id,
            assigned_vehicle_id=vehicle_id,
            route_data=route_option.model_dump(),
        )
        session.add(route)
        session.flush()
        return route

    @staticmethod
    def _find_node(session: Session, node_key: str) -> LogisticsNode | None:
        return session.scalar(select(LogisticsNode).where(LogisticsNode.node_key == node_key))
