import { useState, useCallback } from "react";

const STORAGE_KEY = "driver_vehicle";

export function useDriverAuth() {
  const [vehicle, setVehicle] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const login = useCallback((v) => {
    setVehicle(v);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(v));
  }, []);

  const logout = useCallback(() => {
    setVehicle(null);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return { vehicle, login, logout };
}
