import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet.heat";

export function HeatmapLayer({ points, options = {} }) {
  const map = useMap();
  const layerRef = useRef(null);

  useEffect(() => {
    if (!map || !points?.length) {
      if (layerRef.current) {
        map?.removeLayer(layerRef.current);
        layerRef.current = null;
      }
      return;
    }

    const heat = L.heatLayer(points, {
      radius: options.radius ?? 35,
      blur: options.blur ?? 20,
      maxZoom: options.maxZoom ?? 10,
      max: options.max ?? 1.0,
      gradient: options.gradient ?? {
        0.0: "#22c55e",
        0.25: "#84cc16",
        0.5: "#f59e0b",
        0.7: "#f97316",
        0.9: "#dc2626",
      },
      minOpacity: options.minOpacity ?? 0.4,
    });

    heat.addTo(map);
    layerRef.current = heat;

    return () => {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
    };
  }, [map, points, options]);

  return null;
}
