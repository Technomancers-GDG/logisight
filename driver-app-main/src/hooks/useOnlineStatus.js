import { useState, useEffect, useCallback } from "react";

const STORAGE_KEY = "driver_connectivity_override";

export function useOnlineStatus() {
  const [simulatedOffline, setSimulatedOffline] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === "true";
    } catch {
      return false;
    }
  });

  const [browserOnline, setBrowserOnline] = useState(navigator.onLine);

  useEffect(() => {
    const handleOnline = () => setBrowserOnline(true);
    const handleOffline = () => setBrowserOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  const isOnline = !simulatedOffline && browserOnline;

  const toggleSimulatedOffline = useCallback(() => {
    setSimulatedOffline((prev) => {
      const next = !prev;
      try {
        if (next) {
          localStorage.setItem(STORAGE_KEY, "true");
        } else {
          localStorage.removeItem(STORAGE_KEY);
        }
      } catch {}
      return next;
    });
  }, []);

  return {
    isOnline,
    isSimulatedOffline: simulatedOffline,
    isBrowserOnline: browserOnline,
    toggleSimulatedOffline,
  };
}
