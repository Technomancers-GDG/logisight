import { useEffect, useMemo } from "react";
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Panel, MetricCard } from "./common/UiPrimitives";

const DEFAULT_CENTER = [22.5937, 78.9629];
const DEFAULT_ZOOM = 6;
const INDIA_LAT_MIN = 6.5;
const INDIA_LAT_MAX = 37.0;
const INDIA_LON_MIN = 68.0;
const INDIA_LON_MAX = 97.5;

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
  const lat = toNumber(item?.latitude);
  const lng = toNumber(item?.longitude);
  if (lat === null || lng === null) return null;
  return [lat, lng];
}

function distanceKm(a, b) {
  const R = 6371;
  const dLat = ((b[0] - a[0]) * Math.PI) / 180;
  const dLng = ((b[1] - a[1]) * Math.PI) / 180;
  const lat1 = (a[0] * Math.PI) / 180;
  const lat2 = (b[0] * Math.PI) / 180;
  const v =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(v), Math.sqrt(1 - v));
}

function pointAlongPath(points, progressPct) {
  if (!points || points.length === 0) return null;
  if (points.length === 1) return points[0];
  const clamped = Math.max(0, Math.min(100, Number(progressPct) || 0));
  if (clamped === 0) return points[0];
  if (clamped === 100) return points[points.length - 1];
  const lengths = [];
  let total = 0;
  for (let i = 1; i < points.length; i++) {
    const len = distanceKm(points[i - 1], points[i]);
    lengths.push(len);
    total += len;
  }
  if (total <= 0) return points[0];
  let remaining = (clamped / 100) * total;
  for (let i = 0; i < lengths.length; i++) {
    const seg = lengths[i];
    if (remaining <= seg || i === lengths.length - 1) {
      const ratio = seg <= 0 ? 0 : remaining / seg;
      const start = points[i];
      const end = points[i + 1];
      return [
        start[0] + (end[0] - start[0]) * ratio,
        start[1] + (end[1] - start[1]) * ratio,
      ];
    }
    remaining -= seg;
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
    const latChange = (result & 1) !== 0 ? ~(result >> 1) : result >> 1;
    latitude += latChange;
    result = 0;
    shift = 0;
    do {
      if (index >= encoded.length) return coordinates;
      byte = encoded.charCodeAt(index) - 63;
      index += 1;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    const lngChange = (result & 1) !== 0 ? ~(result >> 1) : result >> 1;
    longitude += lngChange;
    coordinates.push([latitude / factor, longitude / factor]);
  }
  return coordinates;
}

function MapCenter({ center }) {
  const map = useMap();
  useEffect(() => {
    if (center && Array.isArray(center) && center.length === 2) {
      map.setView(center, map.getZoom(), { animate: true, duration: 0.5 });
    }
  }, [center, map]);
  return null;
}

const vehicleIcon = L.divIcon({
  html: `<div style="background:#2563eb;color:#fff;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:11px;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.3);">🚛</div>`,
  className: "",
  iconSize: [28, 28],
  iconAnchor: [14, 14],
});

const originIcon = L.divIcon({
  html: `<div style="background:#22c55e;color:#fff;border-radius:50%;width:22px;height:22px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:10px;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.3);">A</div>`,
  className: "",
  iconSize: [22, 22],
  iconAnchor: [11, 11],
});

const destIcon = L.divIcon({
  html: `<div style="background:#22c55e;color:#fff;border-radius:50%;width:22px;height:22px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:10px;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.3);">B</div>`,
  className: "",
  iconSize: [22, 22],
  iconAnchor: [11, 11],
});

const altDestIcon = L.divIcon({
  html: `<div style="background:#f59e0b;color:#fff;border-radius:50%;width:22px;height:22px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:10px;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.3);">B′</div>`,
  className: "",
  iconSize: [22, 22],
  iconAnchor: [11, 11],
});

export function DriverMapView({
  vehicle,
  facilities,
  objectives,
  routeTemplates,
  recommendations,
  wsSnapshot,
  onDecision,
  decisionLoading,
}) {
  const facilityLookup = useMemo(() => {
    const map = {};
    facilities.forEach((f) => {
      if (hasCoordinates(f) && isInIndiaBounds(Number(f.latitude), Number(f.longitude))) map[f.id] = f;
    });
    return map;
  }, [facilities]);

  const objectiveLookup = useMemo(() => {
    const map = {};
    objectives.forEach((o) => {
      map[o.id] = o;
    });
    return map;
  }, [objectives]);

  const routeTemplateLookup = useMemo(() => {
    const map = {};
    routeTemplates.forEach((t) => {
      if (t?.route_key) {
        map[t.route_key] = {
          ...t,
          decoded: t.encoded_polyline ? decodePolyline(t.encoded_polyline, 5) : [],
        };
      }
    });
    return map;
  }, [routeTemplates]);

  const routeData = useMemo(() => {
    if (!vehicle) return null;

    const wsVehicle = wsSnapshot?.vehicles?.find(
      (v) => String(v.vehicle_id ?? v.id) === String(vehicle.id)
    );

    const objectiveId = toNumber(
      wsVehicle?.objective_id ?? vehicle.default_objective_id
    );
    const objective = objectiveId != null ? objectiveLookup[objectiveId] : null;

    const status = String(wsVehicle?.status ?? vehicle.status ?? "idle").toLowerCase();
    const progress = Math.max(0, Math.min(100, Number(wsVehicle?.progress_pct ?? 0)));
    const payloadUnits = Number(wsVehicle?.payload_units ?? 0);

    const currentFacilityId = toNumber(
      wsVehicle?.current_facility_id ?? vehicle.current_facility_id
    );

    const originFacility = objective ? facilityLookup[objective.origin_facility_id] : null;
    const destFacility = objective ? facilityLookup[objective.destination_facility_id] : null;

    if (!originFacility || !destFacility) {
      const currentFacility = currentFacilityId != null ? facilityLookup[currentFacilityId] : null;
      const currentPoint = currentFacility ? toLatLng(currentFacility) : null;
      if (!currentPoint) return null;
      return {
        identifier: wsVehicle?.identifier ?? vehicle.identifier ?? `Truck ${vehicle.id}`,
        status,
        objectiveName: objective?.name || "Unassigned objective",
        progress,
        payloadUnits,
        currentPoint,
        startPoint: currentPoint,
        endPoint: currentPoint,
        routePoints: [currentPoint, currentPoint],
        routeSource: "derived",
      };
    }

    const originPoint = toLatLng(originFacility);
    const destPoint = toLatLng(destFacility);
    if (!originPoint || !destPoint) return null;

    const goingToDest = payloadUnits > 0;

    let startPoint, endPoint;
    if (status === "in_transit") {
      startPoint = goingToDest ? originPoint : destPoint;
      endPoint = goingToDest ? destPoint : originPoint;
    } else {
      const currentFacility = currentFacilityId != null ? facilityLookup[currentFacilityId] : null;
      const currentPoint = currentFacility ? toLatLng(currentFacility) : originPoint;
      startPoint = currentPoint;
      endPoint = currentPoint;
    }

    const routeKey = `${originFacility.id}:${destFacility.id}`;
    const routeTemplate = routeTemplateLookup[routeKey];
    const decodedRoutePoints = routeTemplate?.decoded || [];

    let routePoints;
    if (decodedRoutePoints.length >= 2) {
      const filtered = (goingToDest ? decodedRoutePoints : [...decodedRoutePoints].reverse())
        .filter((p) => Array.isArray(p) && p.length === 2 && isInIndiaBounds(p[0], p[1]));
      routePoints = filtered.length >= 2 ? filtered : [startPoint, endPoint];
    } else {
      routePoints = [startPoint, endPoint];
    }

    const markerPoint =
      status === "in_transit"
        ? (pointAlongPath(routePoints, progress) ?? startPoint)
        : startPoint;
    if (!markerPoint || !isInIndiaBounds(markerPoint[0], markerPoint[1])) return null;

    return {
      identifier: wsVehicle?.identifier ?? vehicle.identifier ?? `Truck ${vehicle.id}`,
      status,
      objectiveName: objective?.name || "Unassigned objective",
      progress,
      payloadUnits,
      currentPoint: markerPoint,
      startPoint,
      endPoint,
      routePoints,
      routeSource: routeTemplate?.source || "derived",
      startFacilityId: status === "in_transit" ? (goingToDest ? originFacility.id : destFacility.id) : (currentFacilityId ?? originFacility.id),
      endFacilityId: status === "in_transit" ? (goingToDest ? destFacility.id : originFacility.id) : (currentFacilityId ?? originFacility.id),
    };
  }, [vehicle, wsSnapshot, facilityLookup, objectiveLookup, routeTemplateLookup]);

  const activeRecommendation = useMemo(() => {
    if (!vehicle) return null;
    return recommendations.find(
      (r) =>
        r.vehicle_id === vehicle.id &&
        r.status === "suggested" &&
        String(r.action || "").startsWith("reroute")
    );
  }, [recommendations, vehicle]);

  const altRouteData = useMemo(() => {
    if (!routeData || !activeRecommendation?.recommended_destination_id) return null;
    const altDest = facilityLookup[activeRecommendation.recommended_destination_id];
    const altDestPoint = altDest ? toLatLng(altDest) : null;
    if (!routeData.startPoint || !altDestPoint) return null;

    const altKey = `${routeData.startFacilityId ?? ""}:${activeRecommendation.recommended_destination_id}`;
    const altTmpl = routeTemplateLookup[altKey];
    const altPoints =
      altTmpl?.decoded?.length >= 2
        ? altTmpl.decoded
        : [routeData.startPoint, altDestPoint];

    return { altRoutePoints: altPoints, altDestPoint };
  }, [routeData, activeRecommendation, facilityLookup, routeTemplateLookup]);

  if (!vehicle || !routeData) {
    return (
      <Panel title="My Route">
        <div className="empty">No route data available.</div>
      </Panel>
    );
  }

  const mapCenter = routeData.currentPoint ?? routeData.startPoint ?? DEFAULT_CENTER;

  return (
    <div className="map-section">
      <Panel title="My Route">
        <div className="map-container">
          <div className="map-container inner">
            <MapContainer
              center={mapCenter}
              zoom={DEFAULT_ZOOM}
              scrollWheelZoom
              style={{ height: "100%", width: "100%" }}
            >
              <MapCenter center={mapCenter} />
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <Polyline
                positions={routeData.routePoints}
                color="#2563eb"
                weight={5}
                opacity={0.9}
              />
              {routeData.startPoint && (
                <Marker position={routeData.startPoint} icon={originIcon}>
                  <Popup>Origin</Popup>
                </Marker>
              )}
              {routeData.endPoint &&
                (routeData.endPoint[0] !== routeData.startPoint[0] ||
                  routeData.endPoint[1] !== routeData.startPoint[1]) && (
                  <Marker position={routeData.endPoint} icon={destIcon}>
                    <Popup>Destination</Popup>
                  </Marker>
                )}
              {altRouteData?.altRoutePoints && (
                <>
                  <Polyline
                    positions={altRouteData.altRoutePoints}
                    color="#f59e0b"
                    weight={5}
                    opacity={0.9}
                    dashArray="8,8"
                  />
                  {altRouteData.altDestPoint && (
                    <Marker position={altRouteData.altDestPoint} icon={altDestIcon}>
                      <Popup>Proposed Destination</Popup>
                    </Marker>
                  )}
                </>
              )}
              {routeData.currentPoint && (
                <Marker position={routeData.currentPoint} icon={vehicleIcon}>
                  <Popup>
                    <strong>{routeData.identifier}</strong>
                    <br />
                    Status: {routeData.status}
                    <br />
                    Progress: {routeData.progress.toFixed(1)}%
                    <br />
                    {routeData.objectiveName}
                  </Popup>
                </Marker>
              )}
            </MapContainer>
          </div>
        </div>

        {/* Progress bar */}
        <div className="progress-track">
          <div
            className="progress-fill"
            style={{ width: `${routeData.progress}%` }}
          />
        </div>

        <div className="driver-summary-grid">
          <MetricCard label="Vehicle" value={routeData.identifier} />
          <MetricCard label="Status" value={routeData.status} accent />
          <MetricCard label="Progress" value={`${routeData.progress.toFixed(1)}%`} />
          <MetricCard label="Objective" value={routeData.objectiveName} />
          <MetricCard label="Payload" value={`${routeData.payloadUnits} units`} />
          <MetricCard label="Route Source" value={routeData.routeSource} />
        </div>
      </Panel>

      {activeRecommendation && (
        <Panel title="Reroute Proposal">
          <div className="reroute-proposal">
            <div className="proposal-grid">
              <div>
                <span className="label">Current Destination</span>
                <strong>
                  {facilityLookup[activeRecommendation.original_destination_id]?.name || "Current"}
                </strong>
              </div>
              <div>
                <span className="label">Proposed Destination</span>
                <strong>
                  {facilityLookup[activeRecommendation.recommended_destination_id]?.name || "Alternative"}
                </strong>
              </div>
            </div>
            <p className="proposal-explanation">{activeRecommendation.explanation}</p>
            <div className="proposal-actions">
              <button
                type="button"
                className="primary"
                disabled={decisionLoading}
                onClick={() => onDecision(activeRecommendation.id, "accept")}
              >
                Accept Reroute
              </button>
              <button
                type="button"
                className="secondary"
                disabled={decisionLoading}
                onClick={() => onDecision(activeRecommendation.id, "ignore")}
              >
                Ignore
              </button>
            </div>
          </div>
        </Panel>
      )}
    </div>
  );
}
