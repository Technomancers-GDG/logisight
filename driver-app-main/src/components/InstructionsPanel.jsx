import { Panel } from "./common/UiPrimitives";

function formatTime(isoString) {
  if (!isoString) return "-";
  try {
    return new Date(isoString).toLocaleString();
  } catch {
    return "-";
  }
}

function formatAction(action) {
  return String(action || "").replaceAll("_", " ").toUpperCase();
}

export function InstructionsPanel({ instructions, onAccept, onIgnore }) {
  return (
    <Panel title={`Other Instructions (${instructions.length})`}>
      {instructions.length === 0 ? (
        <div className="empty">No additional instructions pending.</div>
      ) : (
        <div className="instructions-stack">
          {instructions.map((inst) => (
            <div key={inst.recommendation_id} className="instruction-card">
              <div className="instruction-header">
                <div className="instruction-meta">
                  <strong>{inst.vehicle_identifier}</strong>
                  <span className="instruction-action-label">
                    {formatAction(inst.action)}
                  </span>
                </div>
                <span className="instruction-time">{formatTime(inst.created_at)}</span>
              </div>
              <p className="instruction-text">{inst.explanation}</p>
              <div className="instruction-actions">
                <button
                  type="button"
                  className="primary small"
                  onClick={() => onAccept(inst.recommendation_id)}
                >
                  Accept
                </button>
                <button
                  type="button"
                  className="secondary small"
                  onClick={() => onIgnore(inst.recommendation_id)}
                >
                  Ignore
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}
