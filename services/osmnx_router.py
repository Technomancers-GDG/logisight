"""Three-tier route planner: OSRM API -> OSMnx precomputed cache -> geodesic estimate.

Tier 1 — OSRM (online API, default enabled via ROUTE_USE_OSRM=true).
Tier 2 — OSMnx precomputed cache (static in-memory graph loaded from
         pre-downloaded ``.graphml`` files; requires osmnx installed).
Tier 3 — Haversine-based geodesic estimate with road-factor adjustment.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from models import Facility, RouteTemplate
from services.route_planner import RoutePlanner, encode_polyline, haversine_km

logger = logging.getLogger(__name__)

# Lazy cache of pre-downloaded OSMnx graphs keyed by city name.
_osmnx_graphs: dict[str, object] = {}


def _load_cached_graphs(graphs_dir: str) -> dict[str, object]:
    """Walk *graphs_dir* for ``.graphml`` files and load them into memory.

    Returns a dict mapping city name (lowercase) to the ``networkx.MultiDiGraph``.
    Silently skips files that can't be parsed.
    """
    graphs: dict[str, object] = {}
    gdir = Path(graphs_dir)
    if not gdir.is_dir():
        return graphs

    try:
        import osmnx as ox
    except ImportError:
        logger.warning("osmnx not installed — cannot load cached graphs from %s", graphs_dir)
        return graphs

    for fpath in sorted(gdir.glob("*.graphml")):
        city = fpath.stem.lower()
        try:
            graph = ox.load_graphml(str(fpath))
            graphs[city] = graph
            logger.info("Loaded cached OSMnx graph for '%s' (%s)", city, fpath)
        except Exception as exc:
            logger.warning("Failed to load OSMnx graph %s: %s", fpath, exc)
    return graphs


class OsmnxRouter(RoutePlanner):
    """Extends RoutePlanner with an OSMnx precomputed cache tier.

    The cache uses in-memory ``networkx.MultiDiGraph`` objects loaded from
    ``.graphml`` files that were pre-downloaded by the
    ``scripts/precompute_osmnx_routes.py --save-graphs`` command.
    """

    def __init__(self, osrm_base_url: str | None = None) -> None:
        super().__init__(osrm_base_url)
        self.use_osmnx = settings.route_use_osmnx
        # Populate the module-level cache on first instantiation.
        if self.use_osmnx and not _osmnx_graphs:
            _osmnx_graphs.update(_load_cached_graphs(settings.osmnx_graphs_dir))

    def get_or_create_template(
        self, session: Session, origin: Facility, destination: Facility
    ) -> RouteTemplate:
        key = self.route_key(origin.id, destination.id)
        existing = session.scalar(
            select(RouteTemplate).where(RouteTemplate.route_key == key)
        )
        if existing is not None:
            session.expunge(existing)
            return existing

        route_data = None

        # Tier 1 — OSRM API (online)
        if self.use_osrm:
            route_data = self._fetch_osrm_route(origin, destination)

        # Tier 2 — OSMnx precomputed cache
        if route_data is None and self.use_osmnx:
            route_data = self._fetch_osmnx_cached(session, origin, destination)

        # Tier 3 — Haversine estimate
        if route_data is None:
            route_data = self._estimated_route(origin, destination)

        route = RouteTemplate(
            route_key=key,
            origin_facility_id=origin.id,
            destination_facility_id=destination.id,
            distance_km=route_data["distance_km"],
            duration_minutes=route_data["duration_minutes"],
            encoded_polyline=route_data["encoded_polyline"],
            steps=route_data["steps"],
            source=route_data["source"],
            refreshed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(route)
        session.flush()
        session.expunge(route)
        return route

    async def get_or_create_template_async(
        self, session: Session, origin: Facility, destination: Facility
    ) -> RouteTemplate:
        """Async variant — event-loop-friendly, calls ``_fetch_osrm_route_async``."""
        key = self.route_key(origin.id, destination.id)
        existing = session.scalar(
            select(RouteTemplate).where(RouteTemplate.route_key == key)
        )
        if existing is not None:
            session.expunge(existing)
            return existing

        route_data = None

        if self.use_osrm:
            route_data = await self._fetch_osrm_route_async(origin, destination)

        if route_data is None and self.use_osmnx:
            route_data = self._fetch_osmnx_cached(session, origin, destination)

        if route_data is None:
            route_data = self._estimated_route(origin, destination)

        route = RouteTemplate(
            route_key=key,
            origin_facility_id=origin.id,
            destination_facility_id=destination.id,
            distance_km=route_data["distance_km"],
            duration_minutes=route_data["duration_minutes"],
            encoded_polyline=route_data["encoded_polyline"],
            steps=route_data["steps"],
            source=route_data["source"],
            refreshed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(route)
        session.flush()
        session.expunge(route)
        return route

    def _fetch_osmnx_cached(
        self, session: Session, origin: Facility, destination: Facility
    ) -> dict[str, object] | None:
        """Look up a precomputed OSMnx route.

        Preferential order:
          1. In-memory ``networkx`` graph (fastest — no DB/disk hit).
          2. RouteTemplate table (persistent fallback).
        """
        # Tier 2a — In-memory networkx graph (pre-loaded .graphml).
        orig_city = str(origin.city).strip().lower()
        dest_city = str(destination.city).strip().lower()
        if orig_city == dest_city and orig_city in _osmnx_graphs:
            result = self._route_on_graph(
                _osmnx_graphs[orig_city],
                origin.latitude, origin.longitude,
                destination.latitude, destination.longitude,
            )
            if result is not None:
                return result

        # Tier 2b — RouteTemplate table (persistent fallback).
        key = self.route_key(origin.id, destination.id)
        cached = session.scalar(
            select(RouteTemplate).where(
                RouteTemplate.route_key == key,
                RouteTemplate.source == "osmnx",
            )
        )
        if cached is None:
            return None

        return {
            "distance_km": cached.distance_km,
            "duration_minutes": cached.duration_minutes,
            "encoded_polyline": cached.encoded_polyline,
            "steps": cached.steps or [],
            "source": "osmnx",
        }

    def _route_on_graph(
        self,
        graph: object,
        orig_lat: float, orig_lon: float,
        dest_lat: float, dest_lon: float,
    ) -> dict[str, object] | None:
        """Snap lat/lng to nearest graph nodes and compute the shortest path."""
        try:
            import networkx as nx
            import osmnx as ox
        except ImportError:
            return None
        try:
            orig_node = ox.distance.nearest_nodes(graph, orig_lon, orig_lat)
            dest_node = ox.distance.nearest_nodes(graph, dest_lon, dest_lat)
        except Exception:
            return None
        try:
            route = nx.shortest_path(graph, orig_node, dest_node, weight="length")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
        coords = [(graph.nodes[n]["y"], graph.nodes[n]["x"]) for n in route]
        total_m = 0.0
        for i in range(1, len(coords)):
            total_m += haversine_km(*coords[i - 1], *coords[i]) * 1000  # type: ignore[arg-type]
        distance_km = round(total_m / 1000, 2)
        return {
            "distance_km": distance_km,
            "duration_minutes": round(distance_km / 48.0 * 60, 2),
            "encoded_polyline": encode_polyline(coords),
            "steps": [],
            "source": "osmnx",
        }
