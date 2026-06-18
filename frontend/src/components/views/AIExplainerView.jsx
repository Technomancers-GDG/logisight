import { useState, useEffect, useMemo } from "react";
import { Panel } from "../common/UiPrimitives";

function formatTimeOnly(dateStr) {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatCompact(n) {
  const v = Number(n) || 0;
  if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
  if (v >= 1e3) return (v / 1e3).toFixed(1) + "K";
  return v.toFixed(2);
}

export function AIExplainerView({ apiFetch, recommendations, dashboard, vehicles, facilityLookup }) {
  const [selectedRecId, setSelectedRecId] = useState(null);
  const [aiActivity, setAiActivity] = useState(null);

  useEffect(() => {
    apiFetch("/api/metrics/ai-activity")
      .then(setAiActivity)
      .catch(() => {});
  }, [apiFetch]);

  const activeRecs = recommendations || [];
  const selectedRec = activeRecs.find(r => r.id === selectedRecId) || activeRecs[0];
  const metrics = dashboard?.metrics || {};
  const completedTrips = metrics.completed_trips ?? aiActivity?.completed_trips ?? 0;
  const totalDecisions = (aiActivity?.rl_engine?.train_step ?? 0) + activeRecs.length;

  const correctRate = useMemo(() => {
    if (aiActivity?.driver_acceptance_rate != null) return aiActivity.driver_acceptance_rate;
    if (aiActivity?.rl_sla_success_rate_pct != null) return aiActivity.rl_sla_success_rate_pct;
    return null;
  }, [aiActivity]);

  if (activeRecs.length === 0 && !aiActivity) {
    return <div className="loading">Awaiting AI decisions to explain...</div>;
  }

  return (
    <section className="analytics-layout explainer-view">
      <div className="view-header" style={{ marginBottom: "2rem" }}>
        <h2>Decision Explainability Engine</h2>
        <p style={{ color: "#94a3b8" }}>Transparent breakdown of the factors influencing AI rerouting and dispatch decisions.</p>
      </div>

      {/* ── Section 4: AI Performance Summary ── */}
      <div className="metrics-summary" style={{ marginBottom: "2rem" }}>
        <div className="metric-card">
          <span className="metric-label">AI Decisions Made</span>
          <span className="metric-value">{totalDecisions}</span>
          <span className="metric-unit">this session</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Reroutes Executed</span>
          <span className="metric-value">{metrics.reroute_count ?? aiActivity?.reroute_count ?? 0}</span>
          <span className="metric-unit">AI-optimized trips</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">CO₂ Saved</span>
          <span className="metric-value">{metrics.co2_saved_kg ? `${Math.round(metrics.co2_saved_kg)} kg` : "—"}</span>
          <span className="metric-unit">vs baseline routing</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Stockouts Prevented</span>
          <span className="metric-value">{metrics.stockouts_prevented ?? aiActivity?.stockouts_prevented ?? 0}</span>
          <span className="metric-unit">facilities saved</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Acceptance Rate</span>
          <span className="metric-value">{correctRate != null ? `${correctRate}%` : "—"}</span>
          <span className="metric-unit">driver / AI alignment</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">On-Time Delivery</span>
          <span className="metric-value">{metrics.on_time_delivery_pct != null ? `${metrics.on_time_delivery_pct}%` : "—"}</span>
          <span className="metric-unit">SLA compliance</span>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "1.5rem" }}>
        <div className="rec-list" style={{ display: "flex", flexDirection: "column", gap: "0.75rem", maxHeight: "calc(100vh - 200px)", overflowY: "auto", paddingRight: "0.5rem" }}>
          {activeRecs.length === 0 && (
            <div className="panel" style={{ padding: "2rem", textAlign: "center", color: "#94a3b8" }}>
              No recent recommendations — start the simulation to see AI decisions.
            </div>
          )}
          {activeRecs.map(rec => (
            <div 
              key={rec.id} 
              className={`metric-card ${selectedRec?.id === rec.id ? 'active' : ''}`}
              style={{ 
                cursor: "pointer", 
                border: selectedRec?.id === rec.id ? "1px solid #3b82f6" : "1px solid #334155",
                backgroundColor: selectedRec?.id === rec.id ? "rgba(59, 130, 246, 0.1)" : "var(--panel-bg)"
              }}
              onClick={() => setSelectedRecId(rec.id)}
            >
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                <span style={{ fontWeight: 600, color: selectedRec?.id === rec.id ? "#2563eb" : "#e2e8f0" }}>{(rec.action || "").replace(/_/g, " ").toUpperCase()}</span>
                <span style={{ color: "#475569", fontSize: "0.85rem" }}>{formatTimeOnly(rec.simulation_time)}</span>
              </div>
              <div style={{ fontSize: "0.9rem", color: "#334155", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                {rec.explanation}
              </div>
            </div>
          ))}
        </div>

        <div className="rec-details">
          {selectedRec ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
              <Panel title={`Decision Detail: ${(selectedRec.action || "").replace(/_/g, " ").toUpperCase()}`}>
                <div style={{ padding: "1rem" }}>
                  <h4 style={{ color: "#94a3b8", marginBottom: "0.5rem", textTransform: "uppercase", fontSize: "0.8rem", letterSpacing: "1px" }}>Primary Explanation</h4>
                  <p style={{ fontSize: "1.1rem", lineHeight: 1.6, color: "#0f172a", marginBottom: "1.5rem" }}>
                    {selectedRec.explanation}
                  </p>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem", marginBottom: "1.5rem" }}>
                    <div style={{ backgroundColor: "#1e293b", padding: "1rem", borderRadius: "8px", borderLeft: "4px solid #3b82f6" }}>
                      <h4 style={{ color: "#94a3b8", marginBottom: "0.75rem", fontSize: "0.85rem", textTransform: "uppercase", letterSpacing: "1px" }}>Key Insights</h4>
                      <ul style={{ margin: 0, paddingLeft: "1.2rem", color: "#cbd5e1", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                        {(selectedRec.structured_explanation?.insights || []).map((ins, i) => (
                          <li key={i}>{ins}</li>
                        ))}
                        {(!selectedRec.structured_explanation?.insights || selectedRec.structured_explanation.insights.length === 0) && (
                          <li>Standard operating procedure</li>
                        )}
                      </ul>
                    </div>

                    <div style={{ backgroundColor: "#1e293b", padding: "1rem", borderRadius: "8px", borderLeft: "4px solid #10b981" }}>
                      <h4 style={{ color: "#94a3b8", marginBottom: "0.75rem", fontSize: "0.85rem", textTransform: "uppercase", letterSpacing: "1px" }}>Predicted Impact</h4>
                      <ul style={{ margin: 0, paddingLeft: "1.2rem", color: "#cbd5e1", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                        {(selectedRec.structured_explanation?.impact || []).map((imp, i) => (
                          <li key={i}>{imp}</li>
                        ))}
                        {(!selectedRec.structured_explanation?.impact || selectedRec.structured_explanation.impact.length === 0) && (
                          <li>Minimal deviation from baseline</li>
                        )}
                      </ul>
                    </div>
                  </div>

                  <div style={{ backgroundColor: "rgba(239, 68, 68, 0.1)", padding: "1rem", borderRadius: "8px", borderLeft: "4px solid #ef4444" }}>
                    <h4 style={{ color: "#fca5a5", marginBottom: "0.5rem", fontSize: "0.85rem", textTransform: "uppercase", letterSpacing: "1px" }}>Counterfactual (What if we didn't intervene?)</h4>
                    <p style={{ color: "#7f1d1d", margin: 0 }}>
                      {selectedRec.counterfactual || "If baseline was followed -> Expected normal operations."}
                    </p>
                  </div>
                </div>
              </Panel>

              <Panel title="Scoring Breakdown">
                <div style={{ padding: "1rem" }}>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
                    {Object.entries(selectedRec.score_breakdown || {}).map(([key, value]) => (
                      <div key={key} style={{ backgroundColor: "#1e293b", padding: "0.75rem", borderRadius: "6px" }}>
                        <div style={{ color: "#94a3b8", fontSize: "0.8rem", textTransform: "uppercase", marginBottom: "0.25rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }} title={key.replace(/_/g, ' ')}>
                          {key.replace(/_/g, ' ')}
                        </div>
                        <div style={{ color: "#f8fafc", fontSize: "1.1rem", fontWeight: 600 }}>{typeof value === 'number' && !Number.isNaN(value) ? value.toFixed(3) : value ?? "—"}</div>
                      </div>
                    ))}
                    
                    <div style={{ backgroundColor: "#1e293b", padding: "0.75rem", borderRadius: "6px", border: "1px dashed #3b82f6" }}>
                        <div style={{ color: "#94a3b8", fontSize: "0.8rem", textTransform: "uppercase", marginBottom: "0.25rem" }}>TOTAL SCORE</div>
                        <div style={{ color: "#f8fafc", fontSize: "1.1rem", fontWeight: 600 }}>{(selectedRec.recommended_cost ?? 0).toFixed(2)}</div>
                    </div>
                  </div>
                </div>
              </Panel>
            </div>
          ) : (
            <div className="panel" style={{ padding: "3rem", textAlign: "center", color: "#94a3b8" }}>
              Select a decision to view explainability details.
            </div>
          )}
        </div>
      </div>

      {/* ── Section 3: Decision Outcome Tracker ── */}
      {activeRecs.length > 0 && (
        <div style={{ marginTop: "2rem" }}>
          <Panel title="Decision Outcome Tracker">
            <div style={{ padding: "1rem" }}>
              <p style={{ color: "#94a3b8", marginBottom: "1rem" }}>
                The last {Math.min(5, activeRecs.length)} AI decisions and their predicted vs actual outcomes.
              </p>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid #334155" }}>
                      <th style={{ padding: "0.5rem", textAlign: "left", color: "#94a3b8" }}>Time</th>
                      <th style={{ padding: "0.5rem", textAlign: "left", color: "#94a3b8" }}>Action</th>
                      <th style={{ padding: "0.5rem", textAlign: "left", color: "#94a3b8" }}>Baseline Cost</th>
                      <th style={{ padding: "0.5rem", textAlign: "left", color: "#94a3b8" }}>AI Cost</th>
                      <th style={{ padding: "0.5rem", textAlign: "left", color: "#94a3b8" }}>Savings</th>
                      <th style={{ padding: "0.5rem", textAlign: "left", color: "#94a3b8" }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activeRecs.slice(0, 5).map((rec) => {
                      const savings = (rec.baseline_cost || 0) - (rec.recommended_cost || 0);
                      const accepted = rec.status === "accepted";
                      return (
                        <tr key={rec.id} style={{ borderBottom: "1px solid #1e293b" }}>
                          <td style={{ padding: "0.5rem", color: "#cbd5e1" }}>{formatTimeOnly(rec.simulation_time)}</td>
                          <td style={{ padding: "0.5rem", fontWeight: 600 }}>{(rec.action || "").replace(/_/g, " ")}</td>
                          <td style={{ padding: "0.5rem", color: "#94a3b8" }}>₹{formatCompact(rec.baseline_cost || 0)}</td>
                          <td style={{ padding: "0.5rem", color: "#94a3b8" }}>₹{formatCompact(rec.recommended_cost || 0)}</td>
                          <td style={{ padding: "0.5rem", color: savings > 0 ? "#22c55e" : "#94a3b8", fontWeight: 600 }}>
                            {savings > 0 ? `₹${formatCompact(savings)}` : "—"}
                          </td>
                          <td style={{ padding: "0.5rem" }}>
                            <span style={{
                              display: "inline-block",
                              padding: "2px 10px",
                              borderRadius: "12px",
                              fontSize: "0.75rem",
                              fontWeight: 600,
                              backgroundColor: accepted ? "rgba(34, 197, 94, 0.15)" : "rgba(148, 163, 184, 0.15)",
                              color: accepted ? "#22c55e" : "#94a3b8",
                            }}>
                              {accepted ? "✓ Accepted" : rec.status === "ignored" ? "✗ Ignored" : "Pending"}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </Panel>
        </div>
      )}
    </section>
  );
}
