import { useState, useEffect } from "react";
import { Panel } from "../common/UiPrimitives";
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis,
  CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";

const API_BASE = import.meta.env.VITE_API_BASE ?? import.meta.env.VITE_API_BASE_URL ?? "";

const paretoData = [
  { cost: 120, time: 480, risk: 85, name: "Route A (Baseline)" },
  { cost: 105, time: 510, risk: 60, name: "Route B" },
  { cost: 95,  time: 540, risk: 35, name: "Route C (AI)" },
  { cost: 135, time: 420, risk: 92, name: "Route D" },
  { cost: 110, time: 465, risk: 55, name: "Route E" },
  { cost: 88,  time: 555, risk: 25, name: "Route F (Optimal)" },
];

function ParetoChart({ data }) {
  const points = data ?? paretoData;
  return (
    <div style={{ background: "#0f172a", borderRadius: "8px", padding: "1rem", marginTop: "1rem" }}>
      <h4 style={{ color: "#94a3b8", margin: "0 0 0.75rem 0", fontSize: "0.9rem" }}>
        Route Trade-off Analysis (Cost vs Time vs Risk)
      </h4>
      <ResponsiveContainer width="100%" height={280}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="cost" name="Cost (₹K)" stroke="#64748b" tick={{ fill: "#94a3b8", fontSize: 12 }} />
          <YAxis dataKey="time" name="Time (min)" stroke="#64748b" tick={{ fill: "#94a3b8", fontSize: 12 }} />
          <ZAxis dataKey="risk" range={[60, 400]} name="Risk Score" />
          <Tooltip
            contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: "6px", color: "#f8fafc" }}
            formatter={(value, name) => {
              const labels = { cost: "₹" + value + "K", time: value + " min", risk: value + "%" };
              return [labels[name] ?? value, name];
            }}
          />
          <Legend wrapperStyle={{ color: "#94a3b8", fontSize: 12 }} />
          <Scatter name="Routes" data={points} fill="#3b82f6" stroke="#2563eb" />
        </ScatterChart>
      </ResponsiveContainer>
      <div style={{ display: "flex", gap: "1rem", justifyContent: "center", fontSize: "0.8rem", color: "#64748b", marginTop: "0.5rem" }}>
        <span>⬤ Bubble size = Risk score</span>
        <span style={{ color: "#10b981" }}>◆ Lower-left = Better tradeoff</span>
      </div>
    </div>
  );
}

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

      <div>
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

        {selected && <ParetoChart data={null} />}
      </div>
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
