import { Panel } from "../common/UiPrimitives";

export function CloudView() {
  return (
    <div className="view-cloud" style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "400px" }}>
      <Panel title="Google Cloud Integration">
        <div style={{ textAlign: "center", padding: "3rem", color: "#94a3b8" }}>
          <h3 style={{ color: "#f8fafc", marginBottom: "1rem" }}>Coming Soon</h3>
          <p style={{ marginBottom: "1rem" }}>
            Google Cloud integration (Firebase, PubSub, Vertex AI, BigQuery) is planned for Phase 5.
          </p>
          <p style={{ fontSize: "0.85rem", color: "#64748b" }}>
            The platform currently runs on PostgreSQL + Redis with optional Gemini/Groq for LLM enhancement.
          </p>
        </div>
      </Panel>
    </div>
  );
}
