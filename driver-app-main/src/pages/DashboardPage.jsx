import { useState } from "react";
import { DriverMapView } from "../components/DriverMapView";
import { InstructionsPanel } from "../components/InstructionsPanel";
import { IncidentForm } from "../components/IncidentForm";
import { DriverAIChat } from "../components/DriverAIChat";
import { BottomNav } from "../components/BottomNav";
import { apiFetch } from "../hooks/useApiFetch";

function formatAction(action) {
  return String(action || "").replaceAll("_", " ").toUpperCase();
}

export function DashboardPage({
  vehicle,
  onLogout,
  facilities,
  objectives,
  routeTemplates,
  recommendations,
  wsSnapshot,
  setRecommendations,
  message,
  error,
  setMessage,
  setError,
}) {
  const [decisionLoading, setDecisionLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("route");
  const [chatOpen, setChatOpen] = useState(false);

  async function handleDecision(recommendationId, decision) {
    setDecisionLoading(true);
    try {
      await apiFetch(`/api/recommendations/${recommendationId}/decision`, {
        method: "POST",
        body: JSON.stringify({ decision }),
      });
      setMessage(`Reroute ${decision === "accept" ? "accepted" : "ignored"}.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setDecisionLoading(false);
    }
  }

  async function handleGenericDecision(recommendationId, decision) {
    try {
      const backendDecision = decision === "accepted" ? "accepted" : "ignored";
      await apiFetch("/api/driver/decision", {
        method: "POST",
        body: JSON.stringify({
          recommendation_id: recommendationId,
          decision: backendDecision,
          note: `Driver ${decision === "accepted" ? "accepted" : "ignored"} instruction from mobile app.`,
        }),
      });
      setMessage(`Instruction ${decision}.`);
      const recs = await apiFetch("/api/recommendations");
      setRecommendations(recs);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleIncidentSubmit(payload) {
    try {
      // Map to V2 disruption API
      const disruptionPayload = {
        disruption_type: payload.incident_type || "manual",
        city: payload.city || "",
        severity: (payload.severity || 0.7),
        note: payload.note || "",
      };
      await apiFetch("/api/v2/disruptions", {
        method: "POST",
        body: JSON.stringify(disruptionPayload),
      });
      setMessage("Incident reported successfully.");
    } catch (err) {
      setError(err.message);
    }
  }

  const otherInstructions = (recommendations ?? []).filter(
    (r) =>
      r.vehicle_id === vehicle.id &&
      r.status === "suggested" &&
      !String(r.action || "").startsWith("reroute")
  );

  const hasBanner = message || error;

  return (
    <div className={`app-shell${hasBanner ? " has-banner" : ""}`}>
      {/* Sticky Header */}
      <header className="app-header">
        <div className="app-header-left">
          <div>
            <p className="eyebrow">Driver Portal</p>
            <h1>Dashboard</h1>
          </div>
        </div>
        <div className="app-header-right">
          <span className="vehicle-id">{vehicle.identifier}</span>
          <button type="button" className="secondary small" onClick={onLogout}>
            Sign Out
          </button>
        </div>
      </header>

      {message && <div className="banner success">{message}</div>}
      {error && <div className="banner error">{error}</div>}

      <main className="view-stack">
        {/* Mobile: full-screen AI chat when AI tab is active */}
        {activeTab === "ai" ? (
          <DriverAIChat onBack={() => setActiveTab("route")} />
        ) : (
          <div className="driver-dashboard-grid">
            <div className="driver-dashboard-top">
              <div className={activeTab === "route" ? "" : "hide-mobile"}>
                <DriverMapView
                  vehicle={vehicle}
                  facilities={facilities}
                  objectives={objectives}
                  routeTemplates={routeTemplates}
                  recommendations={recommendations}
                  wsSnapshot={wsSnapshot}
                  onDecision={handleDecision}
                  decisionLoading={decisionLoading}
                />
              </div>
            </div>

            <div className="driver-side-stack">
              <div className={activeTab === "tasks" ? "" : "hide-mobile"}>
                <InstructionsPanel
                  instructions={otherInstructions}
                  onAccept={(id) => handleGenericDecision(id, "accepted")}
                  onIgnore={(id) => handleGenericDecision(id, "ignored")}
                />
              </div>

              <div className={activeTab === "incidents" ? "" : "hide-mobile"}>
                <IncidentForm vehicle={vehicle} onSubmit={handleIncidentSubmit} />
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Desktop: floating FAB + chat panel */}
      {!chatOpen && (
        <button
          type="button"
          className="driver-chat-fab"
          onClick={() => setChatOpen(true)}
          title="Open AI Assistant"
        >
          ✨
        </button>
      )}

      {chatOpen && (
        <div className="driver-chat-floating">
          <DriverAIChat onBack={() => setChatOpen(false)} />
        </div>
      )}

      <BottomNav active={activeTab} onTabChange={(tab) => { setActiveTab(tab); if (tab !== "ai") setChatOpen(false); }} />
    </div>
  );
}
