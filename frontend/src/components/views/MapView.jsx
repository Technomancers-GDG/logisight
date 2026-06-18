import React, { useMemo, useState } from "react";
import { MapContainer, Marker, Polyline, Popup, TileLayer, Circle, useMapEvents, useMap } from "react-leaflet";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import L from "leaflet";
import { Panel, Select } from "../common/UiPrimitives";

const DEFAULT_CENTER = [22.5937, 78.9629];
const DEFAULT_ZOOM = 5;
const INDIA_BOUNDS = [
  [6.5, 68.0],
  [37.0, 97.5],
];
const INDIA_LAT_MIN = 6.5;
const INDIA_LAT_MAX = 37.0;
const INDIA_LON_MIN = 68.0;
const INDIA_LON_MAX = 97.5;
const VEHICLE_SPREAD_DEGREES = 0.04;
const MARKER_GROUP_PRECISION = 3;

function isInIndiaBounds(lat, lon) {
  return (
    Number.isFinite(lat) && Number.isFinite(lon) &&
    lat >= INDIA_LAT_MIN && lat <= INDIA_LAT_MAX &&
    lon >= INDIA_LON_MIN && lon <= INDIA_LON_MAX
  );
}

function toNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function hasCoordinates(item) {
  return toNumber(item?.latitude) !== null && toNumber(item?.longitude) !== null;
}

function toLatLng(item) {
  const latitude = toNumber(item?.latitude);
  const longitude = toNumber(item?.longitude);
  if (latitude === null || longitude === null) return null;
  return [latitude, longitude];
}

function distanceKm(startPoint, endPoint) {
  const earthRadiusKm = 6371;
  const toRadians = (degrees) => (degrees * Math.PI) / 180;
  const latDelta = toRadians(endPoint[0] - startPoint[0]);
  const lonDelta = toRadians(endPoint[1] - startPoint[1]);
  const startLat = toRadians(startPoint[0]);
  const endLat = toRadians(endPoint[0]);
  const value =
    Math.sin(latDelta / 2) * Math.sin(latDelta / 2) +
    Math.cos(startLat) * Math.cos(endLat) * Math.sin(lonDelta / 2) * Math.sin(lonDelta / 2);
  const arc = 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value));
  return earthRadiusKm * arc;
}

function pathDistanceKm(points) {
  if (!Array.isArray(points) || points.length < 2) return 0;
  let total = 0;
  for (let index = 1; index < points.length; index += 1) {
    total += distanceKm(points[index - 1], points[index]);
  }
  return total;
}

function pointAlongPath(points, progressPct) {
  if (!Array.isArray(points) || points.length === 0) return null;
  if (points.length === 1) return points[0];
  const clampedProgress = Math.max(0, Math.min(100, Number(progressPct) || 0));
  if (clampedProgress === 0) return points[0];
  if (clampedProgress === 100) return points[points.length - 1];
  const segmentLengths = [];
  let totalLength = 0;
  for (let index = 1; index < points.length; index += 1) {
    const length = distanceKm(points[index - 1], points[index]);
    segmentLengths.push(length);
    totalLength += length;
  }
  if (totalLength <= 0) return points[0];
  let remaining = (clampedProgress / 100) * totalLength;
  for (let index = 0; index < segmentLengths.length; index += 1) {
    const segmentLength = segmentLengths[index];
    if (remaining <= segmentLength || index === segmentLengths.length - 1) {
      const ratio = segmentLength <= 0 ? 0 : remaining / segmentLength;
      const start = points[index];
      const end = points[index + 1];
      return [start[0] + (end[0] - start[0]) * ratio, start[1] + (end[1] - start[1]) * ratio];
    }
    remaining -= segmentLength;
  }
  return points[points.length - 1];
}

function decodePolyline(encoded, precision = 5) {
  if (!encoded) return [];
  const coordinates = [];
  let index = 0;
  let latitude = 0;
  let longitude = 0;
  const factor = 10 ** precision;
  while (index < encoded.length) {
    let result = 0;
    let shift = 0;
    let byte;
    do {
      if (index >= encoded.length) return coordinates;
      byte = encoded.charCodeAt(index) - 63;
      index += 1;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    const latitudeChange = (result & 1) !== 0 ? ~(result >> 1) : result >> 1;
    latitude += latitudeChange;
    result = 0;
    shift = 0;
    do {
      if (index >= encoded.length) return coordinates;
      byte = encoded.charCodeAt(index) - 63;
      index += 1;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    const longitudeChange = (result & 1) !== 0 ? ~(result >> 1) : result >> 1;
    longitude += longitudeChange;
    coordinates.push([latitude / factor, longitude / factor]);
  }
  return coordinates;
}

function spreadPoint(point, index, total) {
  if (!point || total <= 1) return point;
  const [latitude, longitude] = point;
  const angle = (2 * Math.PI * index) / total;
  const ringMultiplier = 1 + Math.floor(index / 8) * 0.45;
  const radius = VEHICLE_SPREAD_DEGREES * ringMultiplier;
  const safeCos = Math.max(Math.cos((latitude * Math.PI) / 180), 0.25);
  return [latitude + Math.sin(angle) * radius, longitude + (Math.cos(angle) * radius) / safeCos];
}

function createFacilityIcon(facilityType) {
  const kind = facilityType === "port" ? "port" : "warehouse";
  const label = kind === "port" ? "PT" : "WH";
  return L.divIcon({
    html: `<div class="map-pin map-pin-facility ${kind}"><span>${label}</span></div>`,
    className: "map-pin-wrap",
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  });
}

function MapResizeObserver() {
  const map = useMap();
  React.useEffect(() => {
    if (!map) return;
    const observer = new ResizeObserver(() => {
      map.invalidateSize();
    });
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map]);
  return null;
}

const __vehicleIconCache = {};
function getVehicleIcon(status, identifier, selected = false) {
  const key = `${status}-${identifier}-${selected}`;
  if (!__vehicleIconCache[key]) {
    const statusClass = String(status || "idle").toLowerCase().replaceAll("_", "-");
    const selectedClass = selected ? "selected" : "";
    const shortId = String(identifier || "TRK").replace(/[^A-Za-z0-9]/g, "").slice(-3) || "TRK";
    __vehicleIconCache[key] = L.divIcon({
      html: `<div class="map-pin map-pin-vehicle ${statusClass} ${selectedClass}"><span>${shortId}</span></div>`,
      className: "map-pin-wrap",
      iconSize: [42, 24],
      iconAnchor: [21, 12],
    });
  }
  return __vehicleIconCache[key];
}

function getVehicleEventHandlers(vehicleId, setFilterVehicleId, setHighlightedVehicleId) {
  return {
    click: () => {
      const id = String(vehicleId);
      setFilterVehicleId(id);
      setHighlightedVehicleId(id);
    },
  };
}

function eventSeverity(impactScore) {
  const score = Number(impactScore) || 0;
  if (score >= 0.75) return "high";
  if (score >= 0.45) return "medium";
  return "low";
}

function getRiskColor(risk, category) {
  if (category && String(category).toLowerCase().includes("cascade")) return "#8b5cf6"; // Purple AI cascade
  if (risk >= 0.6) return "#dc2626";
  if (risk >= 0.3) return "#f59e0b";
  return "#22c55e";
}

function getRiskRadius(risk) {
  return 8000 + risk * 40000;
}

function routeRiskLevel(risk) {
  const value = Number(risk) || 0;
  if (value >= 0.6) return "high";
  if (value >= 0.3) return "medium";
  return "low";
}

function isReroutedRoute(route) {
  return String(route?.recommendationAction || "").toLowerCase().includes("reroute");
}

function MapClickHandler({ onMapClick }) {
  useMapEvents({
    click: onMapClick,
  });
  return null;
}


export function MapView({
  facilities = [],
  vehicles = [],
  objectives = [],
  recommendations = [],
  activeEvents = [],
  routeTemplates = [],
  riskForecast = [],
  vehicleCount = 0,
  onScaleFleet,
  isScalingFleet = false,
}) {
  const [filterVehicleId, setFilterVehicleId] = useState("");
  const [highlightedVehicleId, setHighlightedVehicleId] = useState("");
  const [filterObjectiveId, setFilterObjectiveId] = useState("");
  const [showDisruptions, setShowDisruptions] = useState(true);
  const [showRoutePaths, setShowRoutePaths] = useState(true);
  const [showRiskHeatmap, setShowRiskHeatmap] = useState(true);
  const [showAllRoutes, setShowAllRoutes] = useState(true);

  const objectiveLookup = useMemo(() => Object.fromEntries(objectives.map((o) => [o.id, o])), [objectives]);

  const facilityLookup = useMemo(() => {
    const lookup = {};
    facilities.forEach((f) => {
      if (hasCoordinates(f) && isInIndiaBounds(Number(f.latitude), Number(f.longitude))) lookup[f.id] = f;
    });
    return lookup;
  }, [facilities]);

  const routeTemplateLookup = useMemo(() => {
    const lookup = {};
    routeTemplates.forEach((t) => {
      if (t?.route_key) {
        const decodedRoutePoints = t.encoded_polyline ? decodePolyline(t.encoded_polyline, 5) : [];
        lookup[t.route_key] = { ...t, decodedRoutePoints };
      }
    });
    return lookup;
  }, [routeTemplates]);

  const riskByCity = useMemo(() => {
    const lookup = {};
    riskForecast.forEach((rf) => {
      const key = String(rf.city || "").trim().toLowerCase();
      if (!key) return;
      lookup[key] = Math.max(Number(rf.risk ?? 0), lookup[key] ?? 0);
    });
    return lookup;
  }, [riskForecast]);

  const liveRoutes = useMemo(() => {
    const transformed = [];
    vehicles.forEach((vehicle) => {
      const vehicleId = toNumber(vehicle.vehicle_id ?? vehicle.id);
      if (vehicleId === null) return;
      const objectiveId = toNumber(vehicle.objective_id ?? vehicle.current_objective_id ?? vehicle.default_objective_id);
      const objective = objectiveId !== null ? objectiveLookup[objectiveId] : null;
      const currentFacilityId = toNumber(vehicle.current_facility_id);
      const nextFacilityId = toNumber(vehicle.next_facility_id);
      const status = String(vehicle.status ?? "idle").toLowerCase();
      const progress = Math.max(0, Math.min(100, Number(vehicle.progress_pct ?? vehicle.current_progress_pct ?? 0)));
      const payloadUnits = Number(vehicle.payload_units ?? 0);
      const currentFacility = currentFacilityId !== null ? facilityLookup[currentFacilityId] : null;
      const nextFacility = nextFacilityId !== null ? facilityLookup[nextFacilityId] : null;
      const objectiveOrigin = objective ? facilityLookup[objective.origin_facility_id] : null;
      const objectiveDestination = objective ? facilityLookup[objective.destination_facility_id] : null;

      let startFacility = currentFacility;
      if (!startFacility) {
        if (status === "in_transit" && objective && nextFacility) {
          if (nextFacility.id === objective.destination_facility_id) startFacility = objectiveOrigin ?? objectiveDestination ?? nextFacility;
          else if (nextFacility.id === objective.origin_facility_id) startFacility = objectiveDestination ?? objectiveOrigin ?? nextFacility;
          else startFacility = payloadUnits > 0 ? (objectiveOrigin ?? objectiveDestination ?? nextFacility) : (objectiveDestination ?? objectiveOrigin ?? nextFacility);
        } else startFacility = objectiveOrigin ?? objectiveDestination ?? nextFacility;
      }
      let endFacility = nextFacility;
      if (!endFacility) {
        if (status === "in_transit" && objective) endFacility = payloadUnits > 0 ? (objectiveDestination ?? objectiveOrigin ?? startFacility) : (objectiveOrigin ?? objectiveDestination ?? startFacility);
        else endFacility = objectiveDestination ?? startFacility;
      }
      if (status !== "in_transit") endFacility = startFacility;

      let startPoint = startFacility ? toLatLng(startFacility) : null;
      const endPoint = endFacility ? toLatLng(endFacility) : startPoint;
      if (!startPoint && endPoint) startPoint = endPoint;
      if (!startPoint || !endPoint) return;

      const routeKey = startFacility && endFacility ? `${startFacility.id}:${endFacility.id}` : null;
      const routeTemplate = routeKey ? routeTemplateLookup[routeKey] : null;
      const decodedRoutePoints = routeTemplate?.decodedRoutePoints || [];
      const rawRoutePoints = decodedRoutePoints.length >= 2 ? decodedRoutePoints : [startPoint, endPoint];
      const routePoints = rawRoutePoints.filter((p) => Array.isArray(p) && p.length === 2 && isInIndiaBounds(p[0], p[1]));
      const safeRoutePoints = routePoints.length >= 2 ? routePoints : [startPoint, endPoint].filter((p) => isInIndiaBounds(p[0], p[1]));
      if (safeRoutePoints.length < 2) return;
      const markerPoint = status === "in_transit" ? (pointAlongPath(safeRoutePoints, progress) ?? startPoint) : startPoint;
      if (!isInIndiaBounds(markerPoint[0], markerPoint[1])) return;
      const recommendation = recommendations.find((r) => Number(r.vehicle_id) === vehicleId && String(r.action || "").startsWith("reroute"));
      const startRisk = riskByCity[String(startFacility?.city || "").trim().toLowerCase()] ?? 0;
      const endRisk = riskByCity[String(endFacility?.city || "").trim().toLowerCase()] ?? 0;
      const routeRisk = Math.max(startRisk, endRisk, Number(recommendation?.score_breakdown?.event_severity ?? 0));

      transformed.push({
        vehicleId,
        identifier: vehicle.identifier || `Truck ${vehicleId}`,
        status,
        objectiveId,
        objectiveName: objective?.name || "Unassigned objective",
        progress,
        payloadUnits,
        currentPoint: markerPoint,
        routePoints: safeRoutePoints,
        routeSource: routeTemplate?.source || "derived",
        recommendationAction: vehicle.recommendation_action || recommendation?.action || null,
        routeRisk,
        riskLevel: routeRiskLevel(routeRisk),
      });
    });

    const spreadRoutes = transformed.filter(r => r.currentPoint).map((route) => ({ ...route, displayPoint: route.currentPoint }));
    const groups = {};
    spreadRoutes.forEach((route, index) => {
      const key = `${route.currentPoint[0].toFixed(MARKER_GROUP_PRECISION)},${route.currentPoint[1].toFixed(MARKER_GROUP_PRECISION)}`;
      if (!groups[key]) groups[key] = [];
      groups[key].push(index);
    });
    Object.values(groups).forEach((indices) => {
      indices.forEach((routeIndex, indexInGroup) => {
        spreadRoutes[routeIndex].displayPoint = spreadPoint(spreadRoutes[routeIndex].currentPoint, indexInGroup, indices.length);
      });
    });
    return spreadRoutes;
  }, [vehicles, objectiveLookup, facilityLookup, routeTemplateLookup, riskByCity, recommendations]);

  const selectedVehicleId = highlightedVehicleId || filterVehicleId;
  const visibleRoutes = useMemo(() => liveRoutes.filter((route) => {
    if (filterVehicleId && String(route.vehicleId) !== filterVehicleId) return false;
    if (filterObjectiveId && String(route.objectiveId) !== filterObjectiveId) return false;
    return true;
  }), [liveRoutes, filterVehicleId, filterObjectiveId]);

  const selectedRoute = useMemo(() => {
    if (!selectedVehicleId) return null;
    return liveRoutes.find((route) => String(route.vehicleId) === selectedVehicleId) ?? null;
  }, [selectedVehicleId, liveRoutes]);

  const selectedRoutePath = useMemo(() => {
    if (!showRoutePaths || !selectedRoute) return null;
    const points = selectedRoute.routePoints.filter(
      (p) => Array.isArray(p) && p.length === 2 && Number.isFinite(p[0]) && Number.isFinite(p[1])
    );
    return points.length >= 2 ? points : null;
  }, [showRoutePaths, selectedRoute]);

  const disruptionEvents = useMemo(() => activeEvents.filter((e) => Number(e.impact_score ?? 0) >= 0.2).sort((a, b) => Number(b.impact_score ?? 0) - Number(a.impact_score ?? 0)).slice(0, 8), [activeEvents]);

  const mapStats = useMemo(() => {
    const reroutesPending = recommendations.filter((r) => r.status === "suggested" && String(r.action || "").startsWith("reroute")).length;
    const routeSpanKm = liveRoutes.reduce((sum, route) => sum + pathDistanceKm(route.routePoints), 0);
    return { facilitiesOnMap: Object.keys(facilityLookup).length, activeVehicles: liveRoutes.filter((r) => r.status !== "idle").length, pendingReroutes: reroutesPending, routeSpanKm };
  }, [facilityLookup, liveRoutes, recommendations]);

  const facilitiesByCity = useMemo(() => {
    const grouped = {};
    facilities.forEach((f) => { if (!grouped[f.city]) grouped[f.city] = []; grouped[f.city].push(f); });
    return grouped;
  }, [facilities]);

  return (
    <section className="map-layout">
      <Panel title="Route & Facility Map with Risk Heatmap">
        <div className="map-controls">
          <div className="control-row">
            <Select label="Filter Vehicle" value={filterVehicleId} options={[["", "All Vehicles"], ...liveRoutes.map((r) => [String(r.vehicleId), r.identifier])]} onChange={(value) => { setFilterVehicleId(value); setHighlightedVehicleId(value ? String(value) : ""); }} />
            <Select label="Filter Objective" value={filterObjectiveId} options={[["", "All Objectives"], ...objectives.map((o) => [String(o.id), o.name])]} onChange={setFilterObjectiveId} />
          </div>
          <div className="control-row checkbox-row">
            <label className="checkbox-label"><input type="checkbox" checked={showDisruptions} onChange={(e) => setShowDisruptions(e.target.checked)} /><span>Show Disruption Zones</span></label>
            <label className="checkbox-label"><input type="checkbox" checked={showRoutePaths} onChange={(e) => setShowRoutePaths(e.target.checked)} /><span>Show Selected Route Path</span></label>
            <label className="checkbox-label"><input type="checkbox" checked={showRiskHeatmap} onChange={(e) => setShowRiskHeatmap(e.target.checked)} /><span>Show Risk Heatmap</span></label>
            <label className="checkbox-label"><input type="checkbox" checked={showAllRoutes} onChange={(e) => setShowAllRoutes(e.target.checked)} /><span>Show All Routes</span></label>
          </div>
          {onScaleFleet ? (
            <div className="scale-controls">
              <div className="scale-summary">Fleet size: <strong>{vehicleCount}</strong> trucks</div>
              <div className="scale-actions">
                <button type="button" className="scale-btn" disabled={isScalingFleet} onClick={() => onScaleFleet(60)}>Regional 60</button>
                <button type="button" className="scale-btn" disabled={isScalingFleet} onClick={() => onScaleFleet(140)}>National 140</button>
                <button type="button" className="scale-btn" disabled={isScalingFleet} onClick={() => onScaleFleet(260)}>Enterprise 260</button>
                <button type="button" className="scale-btn" disabled={isScalingFleet} onClick={() => onScaleFleet(1000)}>Mega Corp 1000</button>
              </div>
              <div className="scale-note">Scaling adds trucks and drivers, rebalances objective assignments, and restarts simulation.</div>
            </div>
          ) : null}
          <div className="route-hint">Toggle "Show All Routes" to see all active route paths on the map. Click a truck marker or use the dropdown to highlight a specific route.</div>
          <div className="route-risk-legend">
            <span><i className="risk-dot low" />Low risk</span>
            <span><i className="risk-dot medium" />Medium risk</span>
            <span><i className="risk-dot high" />High risk</span>
            <span><i className="dash-sample" />Rerouted segment</span>
          </div>
        </div>

        <div className="map-container">
          <MapContainer center={DEFAULT_CENTER} zoom={DEFAULT_ZOOM} scrollWheelZoom maxBounds={INDIA_BOUNDS} maxBoundsViscosity={1.0} minZoom={5} maxZoom={12} worldCopyJump={false}>
            <MapResizeObserver />
            <MapClickHandler onMapClick={() => { setFilterVehicleId(""); setHighlightedVehicleId(""); }} />
            <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            {selectedRoutePath ? (
              <>
                <Polyline key={`shadow-${selectedVehicleId}`} positions={selectedRoutePath} color="#111827" weight={8} opacity={0.25} />
                <Polyline
                  key={`route-${selectedVehicleId}`}
                  positions={selectedRoutePath}
                  color={getRiskColor(selectedRoute?.routeRisk ?? 0)}
                  weight={5}
                  opacity={0.9}
                  lineJoin="round"
                  dashArray={isReroutedRoute(selectedRoute) ? "10 8" : undefined}
                />
              </>
            ) : null}

            {/* All in-transit routes at low opacity */}
            {showAllRoutes && !selectedVehicleId && liveRoutes.filter((r) => r.status === "in_transit" && r.routePoints.length >= 2).slice(0, 120).map((route) => {
              const pts = route.routePoints.filter((p) => Array.isArray(p) && p.length === 2 && Number.isFinite(p[0]) && Number.isFinite(p[1]));
              if (pts.length < 2) return null;
              return (
                <Polyline
                  key={`all-route-${route.vehicleId}`}
                  positions={pts}
                  color={getRiskColor(route.routeRisk)}
                  weight={2.5}
                  opacity={isReroutedRoute(route) ? 0.55 : 0.28}
                  dashArray={isReroutedRoute(route) ? "8 6" : undefined}
                />
              );
            })}

            {/* Active Disruption Circles */}
            {showDisruptions && disruptionEvents.map((event, i) => {
              const facility = facilities.find((f) => String(f.city).trim().toLowerCase() === String(event.city).trim().toLowerCase() && hasCoordinates(f) && isInIndiaBounds(Number(f.latitude), Number(f.longitude)));
              if (!facility) return null;
              
              const cascadeMatch = event.headline?.match(/Cascade from (.+?) → (.+?):/);
              let cascadeDest = null;
              if (cascadeMatch) {
                cascadeDest = facilities.find((f) => f.name === cascadeMatch[2].trim() && hasCoordinates(f) && isInIndiaBounds(Number(f.latitude), Number(f.longitude)));
              }

              return (
                <React.Fragment key={`disruption-group-${i}`}>
                  <Circle
                    center={[Number(facility.latitude), Number(facility.longitude)]}
                    radius={getRiskRadius(event.impact_score)}
                    color={getRiskColor(event.impact_score, event.category)}
                    fillColor={getRiskColor(event.impact_score, event.category)}
                    fillOpacity={0.3}
                    weight={3}
                    opacity={0.8}
                    className="pulse-risk-circle"
                  >
                    <Popup>
                      <strong>{event.city} Disruption</strong><br />
                      Impact: {(event.impact_score * 100).toFixed(1)}%<br />
                      Type: {event.kind}<br />
                      Headline: {event.headline}
                    </Popup>
                  </Circle>
                  {cascadeDest && (
                    <Polyline
                      positions={[[Number(facility.latitude), Number(facility.longitude)], [Number(cascadeDest.latitude), Number(cascadeDest.longitude)]]}
                      color="#8b5cf6"
                      weight={6}
                      dashArray="15 15"
                      className="cascade-wave-line"
                    >
                       <Popup>AI Detected Cascade Wave</Popup>
                    </Polyline>
                  )}
                </React.Fragment>
              );
            })}

            {/* Risk Heatmap Circles */}
            {showRiskHeatmap && riskForecast.map((rf, i) => {
              const facility = facilities.find((f) => String(f.city).trim().toLowerCase() === String(rf.city).trim().toLowerCase() && hasCoordinates(f) && isInIndiaBounds(Number(f.latitude), Number(f.longitude)));
              if (!facility) return null;
              return (
                <Circle
                  key={`risk-${i}`}
                  center={[Number(facility.latitude), Number(facility.longitude)]}
                  radius={getRiskRadius(rf.risk)}
                  color={getRiskColor(rf.risk)}
                  fillColor={getRiskColor(rf.risk)}
                  fillOpacity={0.15}
                  weight={2}
                  opacity={0.5}
                >
                  <Popup>
                    <strong>{rf.city} Risk Forecast</strong><br />
                    Risk: {(rf.risk * 100).toFixed(1)}%<br />
                    ETA Multiplier: {(rf.eta_multiplier ?? 1).toFixed(2)}x<br />
                    Closure Risk: {(rf.closure_risk * 100).toFixed(1)}%<br />
                    Factors: {rf.factors?.join(", ")}
                  </Popup>
                </Circle>
              );
            })}

            {facilities.map((facility) => hasCoordinates(facility) && isInIndiaBounds(Number(facility.latitude), Number(facility.longitude)) && (
              <Marker key={`facility-${facility.id}`} position={[Number(facility.latitude), Number(facility.longitude)]} icon={createFacilityIcon(facility.facility_type)}>
                <Popup>
                  <strong>{facility.name}</strong><br />
                  {facility.city} - {facility.facility_type}<br />
                  Inventory: {facility.current_inventory_units}/{facility.base_capacity_units}
                </Popup>
              </Marker>
            ))}

            {visibleRoutes.map((route) => {
              const isSelected = String(route.vehicleId) === selectedVehicleId;
              return (
                <Marker key={`vehicle-${route.vehicleId}`} position={route.displayPoint} icon={getVehicleIcon(route.status, route.identifier, isSelected)} eventHandlers={getVehicleEventHandlers(route.vehicleId, setFilterVehicleId, setHighlightedVehicleId)}>
                  <Popup className="dark-sleek-popup">
                    <div style={{ padding: "4px 8px", backgroundColor: "#0f172a", color: "#f8fafc", borderRadius: "8px", minWidth: "180px", margin: "-14px -20px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #334155", paddingBottom: "8px", marginBottom: "8px" }}>
                        <strong style={{ color: "#3b82f6", fontSize: "1.1rem" }}>{route.identifier}</strong>
                        <span style={{ fontSize: "0.7rem", backgroundColor: "#1e293b", color: "#cbd5e1", padding: "2px 6px", borderRadius: "10px", textTransform: "uppercase" }}>{route.status.replace("_", " ")}</span>
                      </div>
                      <div style={{ fontSize: "0.85rem", color: "#e2e8f0", marginBottom: "6px", lineHeight: "1.3" }}>
                        <span style={{ color: "#94a3b8", display: "block", fontSize: "0.75rem", textTransform: "uppercase" }}>Objective</span> 
                        {route.objectiveName}
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", color: "#cbd5e1", marginBottom: "6px" }}>
                        <span style={{ color: "#94a3b8" }}>Progress:</span> 
                        <strong>{route.progress.toFixed(0)}%</strong>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", color: "#cbd5e1", marginBottom: "6px" }}>
                        <span style={{ color: "#94a3b8" }}>Source:</span> 
                        <span>{route.routeSource}</span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", marginTop: "8px", borderTop: "1px solid #334155", paddingTop: "8px", fontWeight: 600 }}>
                        <span style={{ color: "#94a3b8", fontWeight: 400 }}>Risk Level:</span> 
                        <span style={{ color: getRiskColor(route.routeRisk) }}>{route.riskLevel.toUpperCase()} ({Math.round((route.routeRisk || 0) * 100)}%)</span>
                      </div>
                      {isReroutedRoute(route) && (
                        <div style={{ marginTop: "10px", backgroundColor: "rgba(59, 130, 246, 0.15)", color: "#60a5fa", border: "1px solid rgba(59, 130, 246, 0.3)", padding: "4px 8px", borderRadius: "6px", fontSize: "0.8rem", textAlign: "center", fontWeight: 600 }}>
                          ✨ AI Rerouted
                        </div>
                      )}
                    </div>
                  </Popup>
                </Marker>
              );
            })}
          </MapContainer>
        </div>

        <div className="map-info-card">
          <h4>Map Overview</h4>
          <div className="info-grid">
            <div className="info-item"><span className="label">Facilities Mapped</span><span className="value">{mapStats.facilitiesOnMap}</span></div>
            <div className="info-item"><span className="label">Active Vehicles</span><span className="value">{mapStats.activeVehicles}</span></div>
            <div className="info-item"><span className="label">Reroute Recommendations</span><span className="value">{mapStats.pendingReroutes}</span></div>
            <div className="info-item"><span className="label">Route Span</span><span className="value">{mapStats.routeSpanKm.toFixed(0)} km</span></div>
          </div>
          {selectedRoute ? <div className="selected-route-meta">Selected route: <strong>{selectedRoute.identifier}</strong> ({selectedRoute.routeSource})</div> : null}
        </div>
      </Panel>

      <Panel title="Active Routes">
        {visibleRoutes.length === 0 ? <div className="empty">No active routes to display.</div> : (
          <div className="routes-list">
            {visibleRoutes.map((route) => (
              <div key={`active-route-${route.vehicleId}`} className="route-card" role="button" tabIndex={0} onClick={() => { setFilterVehicleId(String(route.vehicleId)); setHighlightedVehicleId(String(route.vehicleId)); }} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setFilterVehicleId(String(route.vehicleId)); setHighlightedVehicleId(String(route.vehicleId)); } }}>
                <div className="route-header"><strong>{route.identifier}</strong><span className={`route-status ${route.status.replaceAll("_", "-")}`}>{route.status.replaceAll("_", " ").toUpperCase()}</span></div>
                <div className="route-details"><span className="route-objective">{route.objectiveName}</span><span>{route.payloadUnits} units</span></div>
                <div className="route-details">
                  <span className="route-source">Route source: {route.routeSource}</span>
                  <span className={`route-risk-pill ${route.riskLevel}`}>{route.riskLevel} risk</span>
                </div>
                <div className="route-progress"><div className="progress-bar-mini"><div className="progress-fill-mini" style={{ width: `${route.progress}%` }} /></div><span className="progress-label">{route.progress.toFixed(0)}% complete</span></div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel title="Facility Network">
        <div className="facility-summary">
          <h4>Facilities by City</h4>
          <div className="cities-grid">
            {Object.entries(facilitiesByCity).map(([city, cityFacilities]) => (
              <div key={city} className="city-card">
                <div className="city-header"><span className="city-name">{city}</span><span className="facility-count">{cityFacilities.length}</span></div>
                <div className="facility-types">
                  {cityFacilities.map((facility, index) => (
                    <span key={index} className={`type-badge ${facility.facility_type}`} title={facility.name}>{facility.facility_type === "warehouse" ? "WH" : "PT"}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </Panel>

      {showDisruptions && (
        <Panel title="Active Disruption Zones">
          {disruptionEvents.length === 0 ? <div className="empty">No weather or news disruptions exceed the alert threshold right now.</div> : (
            <div className="disruption-zones">
              {disruptionEvents.map((event, index) => (
                <div className="disruption-card" key={`${event.city}-${event.kind}-${index}`}>
                  <div className="disruption-header"><h5>{event.city}</h5><span className={`disruption-severity ${eventSeverity(event.impact_score)}`}>{event.kind} impact</span></div>
                  <p className="disruption-desc">{event.headline}</p>
                  <div className="affected-facilities"><strong>Impact type:</strong> {event.impact_type} <strong>Score:</strong> {Number(event.impact_score || 0).toFixed(2)}</div>
                </div>
              ))}
            </div>
          )}
        </Panel>
      )}
    </section>
  );
}
