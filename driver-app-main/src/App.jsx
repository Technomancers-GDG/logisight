import { useState, useCallback } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useDriverAuth } from "./hooks/useDriverAuth";
import { useVehicleData } from "./hooks/useVehicleData";
import { useWebSocket } from "./hooks/useWebSocket";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";

function AppShell() {
  const { vehicle, login, logout } = useDriverAuth();
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const {
    facilities,
    objectives,
    routeTemplates,
    recommendations,
    setRecommendations,
  } = useVehicleData();

  const wsSnapshot = useWebSocket("/ws/operations");

  const clearBanners = useCallback(() => {
    setError("");
    setMessage("");
  }, []);

  if (!vehicle) {
    return (
      <LoginPage
        onLogin={login}
        error={error}
        setError={(msg) => {
          setError(msg);
          clearBanners();
        }}
      />
    );
  }

  return (
    <DashboardPage
      vehicle={vehicle}
      onLogout={logout}
      facilities={facilities}
      objectives={objectives}
      routeTemplates={routeTemplates}
      recommendations={recommendations}
      setRecommendations={setRecommendations}
      wsSnapshot={wsSnapshot}
      message={message}
      error={error}
      setMessage={setMessage}
      setError={(msg) => {
        setError(msg);
        clearBanners();
      }}
    />
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/*" element={<AppShell />} />
      </Routes>
    </BrowserRouter>
  );
}
