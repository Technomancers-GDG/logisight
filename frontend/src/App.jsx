import { lazy, Suspense } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { LandingView } from "./components/landing/LandingView";

const DashboardShell = lazy(() => import("./components/DashboardShell"));
const ClientPortal = lazy(() => import("./pages/ClientPortal"));

export default function App() {
  const location = useLocation();

  if (location.pathname === "/") {
    return <LandingView />;
  }

  if (location.pathname.startsWith("/client")) {
    return (
      <Suspense fallback={<div className="loading">Loading...</div>}>
        <ClientPortal />
      </Suspense>
    );
  }

  if (location.pathname === "/dashboard") {
    return (
      <Suspense fallback={<div className="loading">Loading...</div>}>
        <DashboardShell user={null} onLogout={() => { window.location.href = "/"; }} clientContext={null} />
      </Suspense>
    );
  }

  if (location.pathname === "/login") {
    return <Navigate to="/" replace />;
  }

  return <Navigate to="/" replace />;
}
