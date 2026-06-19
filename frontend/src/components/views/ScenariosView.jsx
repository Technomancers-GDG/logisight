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

function ComparisonTable({ comparison }) {
  if (!comparison) return null;
  const { baseline, ai, improvement } = comparison;

  const rows = [
    { label: "On-Time Delivery", key: "on_time_delivery_pct", unit: "%", green: "higher" },
    { label: "Avg Delay", key: "average_delay_minutes", unit: "min", green: "lower" },
    { label: "Avg Cost per Trip", key: "average_cost_usd", unit: "$", green: "lower" },
    { label: "Overflow Events", key: "overflow_events", unit: "", green: "lower" },
    { label: "Reroutes Applied", key: "reroute_count", unit: "", green: "higher" },
    { label: "Idle Minutes Saved", key: "idle_minutes_prevented", unit: "min", green: "higher" },
    { label: "CO₂ Saved", key: "co2_saved_kg", unit: "kg", green: "higher" },
    { label: "Stockouts Prevented", key: "stockouts_prevented", unit: "", green: "higher" },
  ];

  function delta(baselineVal, aiVal, key) {
    const diff = aiVal - baselineVal;
    const pct = baselineVal !== 0 ? ((diff / Math.abs(baselineVal)) * 100).toFixed(1) : "-";
    const isGood = key === "average_delay_minutes" || key === "overflow_events" || key === "average_cost_usd"
      ? diff < 0 : diff > 0;
    return { diff: (diff > 0 ? "+" : "") + diff.toFixed(1), pct, isGood };
  }

  return (
    <div style={{ marginTop: "1rem", background: "#0f172a", borderRadius: "8px", padding: "1rem" }}>
      <h4 style={{ color: "#f8fafc", margin: "0 0 0.75rem 0", fontSize: "0.95rem" }}>
        Baseline vs AI-Optimized
      </h4>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #334155" }}>
            <th style={{ textAlign: "left", padding: "0.5rem", color: "#94a3b8" }}>Metric</th>
            <th style={{ textAlign: "right", padding: "0.5rem", color: "#f87171" }}>Baseline</th>
            <th style={{ textAlign: "right", padding: "0.5rem", color: "#34d399" }}>AI Optimized</th>
            <th style={{ textAlign: "right", padding: "0.5rem", color: "#94a3b8" }}>Delta</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const bv = baseline[r.key] ?? 0;
            const av = ai[r.key] ?? 0;
            const d = delta(bv, av, r.key);
            return (
              <tr key={r.key} style={{ borderBottom: "1px solid #1e293b" }}>
                <td style={{ padding: "0.4rem 0.5rem", color: "#f8fafc" }}>{r.label}</td>
                <td style={{ padding: "0.4rem 0.5rem", textAlign: "right", color: "#fca5a5" }}>
                  {bv.toFixed(1)}{r.unit && <span style={{ color: "#64748b", marginLeft: "2px" }}>{r.unit}</span>}
                </td>
                <td style={{ padding: "0.4rem 0.5rem", textAlign: "right", color: "#6ee7b7" }}>
                  {av.toFixed(1)}{r.unit && <span style={{ color: "#64748b", marginLeft: "2px" }}>{r.unit}</span>}
                </td>
                <td style={{
                  padding: "0.4rem 0.5rem", textAlign: "right",
                  color: d.isGood ? "#34d399" : "#f87171", fontWeight: 600,
                }}>
                  {d.diff}{d.pct !== "-" && <span style={{ color: "#64748b", fontWeight: 400, marginLeft: "2px" }}>({d.pct}%)</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {improvement?.on_time_delta_pct !== undefined && (
        <div style={{ marginTop: "0.75rem", padding: "0.5rem", background: "#1e293b", borderRadius: "6px", fontSize: "0.8rem", color: "#94a3b8", textAlign: "center" }}>
          Summary: {improvement.on_time_delta_pct > 0 ? "+" : ""}{improvement.on_time_delta_pct}% on-time | {improvement.delay_reduction_minutes > 0 ? "-" : ""}{improvement.delay_reduction_minutes} min avg delay |
          Cost delta: {baseline.average_cost_usd - ai.average_cost_usd > 0 ? "-$" + (baseline.average_cost_usd - ai.average_cost_usd).toFixed(1) : "+$" + (ai.average_cost_usd - baseline.average_cost_usd).toFixed(1)}
        </div>
      )}
    </div>
  );
}

export function ScenariosView({ scenarios = [], apiFetch, scenarioComparison, setScenarioComparison }) {
  const [selected, setSelected] = useState(null);
  const [running, setRunning] = useState(false);
  const [severitySlider, setSeveritySlider] = useState(5);

  async function runScenario(id, scenarioKey) {
    setRunning(true);
    try {
      await apiFetch("/api/scenarios/" + id + "/trigger", {
        method: "POST",
        body: JSON.stringify({ severity_override: severitySlider / 10 }),
      });
      if (scenarioKey) {
        const comp = await apiFetch("/api/scenarios/" + scenarioKey + "/compare");
        if (setScenarioComparison) setScenarioComparison(comp);
      }
    } catch {}
    setRunning(false);
  }

  return (
    <div className="view-scenarios" style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "1rem" }}>
      <Panel title="What-If Scenarios">
        <div style={{ marginBottom: "1rem", padding: "0.75rem", background: "#0f172a", borderRadius: "8px" }}>
          <label style={{ color: "#94a3b8", fontSize: "0.85rem", display: "block", marginBottom: "0.35rem" }}>
            Severity Override: <strong style={{ color: "#f8fafc" }}>{severitySlider}/10</strong>
          </label>
          <input
            type="range" min="1" max="10" value={severitySlider}
            onChange={(e) => setSeveritySlider(Number(e.target.value))}
            style={{ width: "100%", accentColor: "#ef4444", cursor: "pointer" }}
          />
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.7rem", color: "#64748b", marginTop: "0.15rem" }}>
            <span>Minor</span><span>Severe</span>
          </div>
        </div>
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
                onClick={() => runScenario(selected.id, selected.scenario_key)}
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

              {scenarioComparison && <ComparisonTable comparison={scenarioComparison} />}
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
