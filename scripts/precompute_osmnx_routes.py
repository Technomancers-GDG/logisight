#!/usr/bin/env python3
"""Precompute OSMnx road-network routes between all facility pairs.

Usage:
    python -m scripts.precompute_osmnx_routes  [--db DATABASE_URL]

This script:
  1. Loads all facilities from the database.
  2. For each unique city, downloads the walkable road network (5 km buffer)
     via OSMnx.
  3. Computes the shortest driving path (length in metres) between every
     pair of facilities.
  4. Stores the result as RouteTemplate rows with source='osmnx'.

Requires ``osmnx``, ``networkx``, and ``geoalchemy2`` (optional).
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt

logger = logging.getLogger(__name__)

OSMNX_AVAILABLE = False
try:
    import osmnx as ox
    import networkx as nx

    OSMNX_AVAILABLE = True
except ImportError:
    ox = None  # type: ignore[assignment]
    nx = None

# Default 12 demo cities for precomputation
DEMO_CITIES = [
    "Chennai", "Mumbai", "Delhi", "Kolkata", "Bangalore",
    "Hyderabad", "Ahmedabad", "Pune", "Jaipur", "Lucknow",
    "Surat", "Vadodara",
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    return 2 * radius_km * asin(sqrt(a))


def encode_polyline(points: list[tuple[float, float]]) -> str:
    def encode_val(val: int) -> str:
        val = ~(val << 1) if val < 0 else (val << 1)
        res = ""
        while val >= 0x20:
            res += chr((0x20 | (val & 0x1F)) + 63)
            val >>= 5
        res += chr(val + 63)
        return res

    res = ""
    last_lat, last_lng = 0, 0
    for lat, lng in points:
        res += encode_val(int(round((lat - last_lat) * 1e5)))
        res += encode_val(int(round((lng - last_lng) * 1e5)))
        last_lat, last_lng = lat, lng
    return res


def _download_city_graph(city: str, save_dir: str | None = None) -> object | None:
    """Download OSMnx graph for a city with a 5 km walkable buffer.

    When *save_dir* is provided, the graph is also persisted as a
    ``.graphml`` file so subsequent runs can load it from disk without
    hitting the OSM servers.
    """
    if not OSMNX_AVAILABLE:
        logger.warning("osmnx not installed — skipping city %s", city)
        return None
    try:
        query = f"{city}, India"
        logger.info("Downloading OSMnx graph for %s ...", query)
        graph = ox.graph_from_place(query, network_type="drive", buffer_dist=5000)
        logger.info("Graph for %s: %d nodes, %d edges", city, graph.number_of_nodes(), graph.number_of_edges())

        if save_dir:
            from pathlib import Path
            save_path = Path(save_dir) / f"{city.lower()}.graphml"
            save_path.parent.mkdir(parents=True, exist_ok=True)
            ox.save_graphml(graph, str(save_path))
            logger.info("Saved graph to %s", save_path)

        return graph
    except Exception as exc:
        logger.warning("Failed to download OSMnx graph for %s: %s", city, exc)
        return None


def _route_on_graph(
    graph: object,
    orig_lat: float, orig_lon: float,
    dest_lat: float, dest_lon: float,
) -> dict | None:
    """Snap lat/lng to nearest graph nodes and route via shortest path."""
    try:
        orig_node = ox.distance.nearest_nodes(graph, orig_lon, orig_lat)
        dest_node = ox.distance.nearest_nodes(graph, dest_lon, dest_lat)
    except Exception:
        return None

    try:
        route = nx.shortest_path(graph, orig_node, dest_node, weight="length")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None

    # Extract node coordinates along the route
    coords = []
    total_m = 0.0
    for node_id in route:
        node = graph.nodes[node_id]
        coords.append((node["y"], node["x"]))

    for i in range(1, len(coords)):
        total_m += haversine_km(*coords[i - 1], *coords[i]) * 1000

    distance_km = round(total_m / 1000, 2)
    duration_minutes = round(distance_km / 48.0 * 60, 2)  # avg 48 km/h

    return {
        "distance_km": distance_km,
        "duration_minutes": duration_minutes,
        "encoded_polyline": encode_polyline(coords),
        "source": "osmnx",
        "steps": [
            {"name": "OSMnx route", "distance_km": distance_km, "duration_minutes": duration_minutes},
        ],
    }


def precompute_all(
    db_url: str | None = None,
    cities: list[str] | None = None,
    dry_run: bool = False,
    save_graphs_dir: str | None = None,
) -> int:
    """Main entry point: load facilities, compute routes, store in DB."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session as SASession
    from config import settings as cfg
    from models import Base, Facility, RouteTemplate

    url = db_url or cfg.database_url
    engine = create_engine(url)
    Base.metadata.create_all(engine)

    cities_to_process = cities or DEMO_CITIES
    facility_groups: dict[str, list[Facility]] = {}

    with SASession(engine) as session:
        all_facilities = session.scalars(select(Facility)).all()
        for facility in all_facilities:
            city_name = str(facility.city).strip()
            if city_name in cities_to_process or not cities:
                facility_groups.setdefault(city_name, []).append(facility)

    total_pairs = 0
    stored_count = 0

    for city_name, facilities in facility_groups.items():
        if len(facilities) < 2:
            continue

        graph = _download_city_graph(city_name, save_dir=save_graphs_dir)
        if graph is None and not dry_run:
            logger.warning("No graph for %s — skipping intra-city routes", city_name)

        with SASession(engine) as session:
            for i, origin in enumerate(facilities):
                for j, destination in enumerate(facilities):
                    if i >= j:
                        continue

                    key = f"{origin.id}:{destination.id}"
                    existing = session.scalar(
                        select(RouteTemplate).where(
                            RouteTemplate.route_key == key,
                            RouteTemplate.source == "osmnx",
                        )
                    )
                    if existing is not None:
                        continue

                    total_pairs += 1
                    route_data = None

                    if graph is not None:
                        route_data = _route_on_graph(
                            graph,
                            origin.latitude, origin.longitude,
                            destination.latitude, destination.longitude,
                        )

                    if route_data is None:
                        total_m = haversine_km(
                            origin.latitude, origin.longitude,
                            destination.latitude, destination.longitude,
                        ) * 1000
                        distance_km = round(max(1.0, total_m / 1000 * 1.22), 2)
                        coords = [(origin.latitude, origin.longitude), (destination.latitude, destination.longitude)]
                        route_data = {
                            "distance_km": distance_km,
                            "duration_minutes": round(distance_km / 48.0 * 60, 2),
                            "encoded_polyline": encode_polyline(coords),
                            "source": "estimated",
                            "steps": [],
                        }

                    if dry_run:
                        logger.info(
                            "[DRY-RUN] %s -> %s: %s km (%s)",
                            origin.name, destination.name,
                            route_data["distance_km"], route_data["source"],
                        )
                        continue

                    route = RouteTemplate(
                        route_key=key,
                        origin_facility_id=origin.id,
                        destination_facility_id=destination.id,
                        distance_km=route_data["distance_km"],
                        duration_minutes=route_data["duration_minutes"],
                        encoded_polyline=route_data["encoded_polyline"],
                        steps=route_data.get("steps", []),
                        source=route_data["source"],
                        refreshed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    )
                    session.add(route)
                    stored_count += 1

            session.commit()

    logger.info("Done. Total pairs processed: %d, stored: %d", total_pairs, stored_count)
    return stored_count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    import argparse

    parser = argparse.ArgumentParser(description="Precompute OSMnx routes between facilities")
    parser.add_argument("--db", type=str, default=None, help="Database URL (default: from config)")
    parser.add_argument("--dry-run", action="store_true", help="Print routes without storing")
    parser.add_argument("--save-graphs", type=str, default=None, help="Directory to save .graphml graph files")
    args = parser.parse_args()

    count = precompute_all(db_url=args.db, dry_run=args.dry_run, save_graphs_dir=args.save_graphs)
    logger.info("Precomputed and stored %d OSMnx route(s).", count)
