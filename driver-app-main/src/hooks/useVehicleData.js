import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "./useApiFetch";

export function useVehicleData() {
  const [facilities, setFacilities] = useState([]);
  const [objectives, setObjectives] = useState([]);
  const [routeTemplates, setRouteTemplates] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refreshAll = useCallback(async () => {
    try {
      const [facilityData, objectiveData, routeData, recData] = await Promise.all([
        apiFetch("/api/facilities"),
        apiFetch("/api/objectives"),
        apiFetch("/api/routes"),
        apiFetch("/api/recommendations"),
      ]);
      setFacilities(facilityData ?? []);
      setObjectives(objectiveData ?? []);
      setRouteTemplates(routeData ?? []);
      setRecommendations(recData ?? []);
      setError("");
    } catch (fetchError) {
      setError(fetchError.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshAll();
    const intervalId = setInterval(refreshAll, 12000);
    return () => clearInterval(intervalId);
  }, [refreshAll]);

  return { facilities, objectives, routeTemplates, recommendations, setRecommendations, loading, error, refreshAll };
}
