import { Panel } from "../common/UiPrimitives";

export function ComparisonView() {
  return (
    <div className="view-comparison" style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "400px" }}>
      <Panel title="AI vs Baseline Comparison">
        <div style={{ textAlign: "center", padding: "3rem", color: "#94a3b8" }}>
          <h3 style={{ color: "#f8fafc", marginBottom: "1rem" }}>Coming Soon</h3>
          <p style={{ marginBottom: "1rem" }}>
            Statistical A/B comparison between rule-based and ML-based routing is planned for Phase 5.
          </p>
          <p style={{ fontSize: "0.85rem", color: "#64748b" }}>
            This will include on-time delivery comparison, delay reduction, CO2 savings,
            and per-trip scatter analysis with statistical significance testing.
          </p>
        </div>
      </Panel>
    </div>
  );
}
