import { useState, useEffect } from "react";
import { Panel } from "../common/UiPrimitives";

const API_BASE = import.meta.env.VITE_API_BASE ?? import.meta.env.VITE_API_BASE_URL ?? "";

export function ScenariosView({ scenarios = [], apiFetch }) {
  const [selected, setSelected] = useState(null);
  const [running, setRunning] = useState(false);

  async function runScenario(id) {
    setRunning(true);
    try {
      const data = await apiFetch("/api/scenarios/" + id + "/trigger", { method: "POST" });
      setSelected(data);
    } catch {}
    setRunning(false);
  }

  return (
    <div className="view-scenarios" style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "1rem" }}>
      <Panel title="What-If Scenarios">
        {scenarios.length === 0 ? (
          <div className="empty" style={{ textAlign: "center", padding: "2rem", color: "#64748b" }}>
            No scenarios defined.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {scenarios.map((s) => (
              <div key={s.id} style={{ background: "#1e293b", padding: "1rem", borderRadius: "8px", cursor: "pointer" }}
                   onClick={() => setSelected(s)}>
                <div style={{ fontWeight: 600, color: "#f8fafc", marginBottom: "0.25rem" }}>{s.name}</div>
                <div style={{ fontSize: "0.85rem", color: "#94a3b8", marginBottom: "0.5rem" }}>{s.description}</div>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <span style={{ background: "#334155", padding: "2px 8px", borderRadius: "4px", fontSize: "0.8rem", color: "#94a3b8" }}>{s.scenario_type}</span>
                  {s.last_run_at && <span style={{ background: "#065f46", padding: "2px 8px", borderRadius: "4px", fontSize: "0.8rem", color: "#6ee7b7" }}>Last run: {new Date(s.last_run_at).toLocaleTimeString()}</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel title="Comparison Results">
        {!selected ? (
          <div className="empty" style={{ textAlign: "center", padding: "3rem", color: "#64748b" }}>
            Select a scenario to view details.
          </div>
        ) : (
          <div>
            <h3 style={{ color: "#f8fafc", margin: "0 0 0.5rem 0" }}>{selected.name}</h3>
            <p style={{ color: "#94a3b8", marginBottom: "1rem" }}>{selected.description}</p>

            {selected.baseline_metrics ? (
              <div>
                <h4 style={{ color: "#94a3b8", margin: "0 0 0.5rem 0" }}>Baseline Metrics</h4>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.5rem", marginBottom: "1rem" }}>
                  <MetricCard label="On-Time %" value={selected.baseline_metrics.on_time_delivery_pct?.toFixed(1) + "%"} />
                  <MetricCard label="Active Shipments" value={selected.baseline_metrics.active_shipments} />
                  <MetricCard label="CO2 Saved" value={selected.baseline_metrics.co2_saved_kg?.toFixed(0) + " kg"} />
                </div>
              </div>
            ) : (
              <div className="empty" style={{ padding: "1rem", color: "#64748b", background: "#0f172a", borderRadius: "8px", marginBottom: "1rem" }}>
                Scenario not yet executed. Click "Run" to apply.
              </div>
            )}

            <button
              onClick={() => runScenario(selected.id)}
              disabled={running}
              style={{
                padding: "0.5rem 1.5rem",
                background: running ? "#475569" : "#3b82f6",
                color: "white",
                border: "none",
                borderRadius: "6px",
                cursor: running ? "not-allowed" : "pointer",
                fontWeight: 600,
              }}
            >
              {running ? "Running..." : "Run Scenario"}
            </button>

            {selected.scenario_metrics && (
              <div style={{ marginTop: "1rem", padding: "1rem", background: "#0f172a", borderRadius: "8px" }}>
                <div style={{ color: "#6ee7b7", fontSize: "0.85rem" }}>Scenario applied: {selected.scenario_metrics.note}</div>
                <div style={{ color: "#94a3b8", fontSize: "0.8rem", marginTop: "0.25rem" }}>City: {selected.scenario_metrics.city} | Severity: {selected.scenario_metrics.severity}</div>
              </div>
            )}
          </div>
        )}
      </Panel>
    </div>
  );
}

function MetricCard({ label, value }) {
  return (
    <div style={{ background: "#1e293b", padding: "0.75rem", borderRadius: "6px", textAlign: "center" }}>
      <div style={{ fontSize: "0.75rem", color: "#64748b", textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#f8fafc" }}>{value ?? "-"}</div>
    </div>
  );
}
