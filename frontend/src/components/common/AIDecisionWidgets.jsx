import { useEffect, useRef, useState } from "react";

function emptyText(value, fallback = "-") {
  return value === null || value === undefined || value === "" ? fallback : value;
}

/* ------------------------------------------------------------------ */
/* AIDecisionPanel — shows the latest AI decision with storytelling    */
/* ------------------------------------------------------------------ */
export function AIDecisionPanel({ decision, confidence }) {
  const safeDecision = decision ?? {
    title: "Monitoring active logistics routes",
    reason: "Waiting for the next AI route decision.",
    impact: ["No route change recommended yet"],
    confidence: 92,
  };
  const impactItems = Array.isArray(safeDecision.impact) ? safeDecision.impact : [safeDecision.impact];
  const resolvedConfidence = Math.round(confidence ?? safeDecision.confidence ?? 0);

  // Flash animation when decision changes
  const [isNew, setIsNew] = useState(false);
  const prevIdRef = useRef(null);
  useEffect(() => {
    const id = safeDecision.id ?? safeDecision.title;
    if (prevIdRef.current && prevIdRef.current !== id) {
      setIsNew(true);
      const t = setTimeout(() => setIsNew(false), 2000);
      return () => clearTimeout(t);
    }
    prevIdRef.current = id;
  }, [safeDecision.id, safeDecision.title]);

  const confidenceColor =
    resolvedConfidence >= 85 ? "#047857" : resolvedConfidence >= 65 ? "#92400e" : "#991b1b";
  const confidenceBg =
    resolvedConfidence >= 85 ? "#dcfce7" : resolvedConfidence >= 65 ? "#fef3c7" : "#fee2e2";
  const confidenceBorder =
    resolvedConfidence >= 85 ? "#86efac" : resolvedConfidence >= 65 ? "#fbbf24" : "#fca5a5";

  return (
    <div className={`decision-explanation-panel ${isNew ? "decision-flash" : ""}`}>
      <div className="decision-panel-topline">
        <span className="decision-kicker">
          <span className="decision-kicker-dot" />
          Latest AI Decision
        </span>
        {resolvedConfidence > 0 && (
          <span
            className="ai-confidence-badge"
            style={{
              background: confidenceBg,
              color: confidenceColor,
              borderColor: confidenceBorder,
            }}
          >
            <span className="confidence-pulse" style={{ background: confidenceColor }} />
            AI Confidence: {resolvedConfidence}%
          </span>
        )}
      </div>

      <div className="decision-title">→ {emptyText(safeDecision.title)}</div>

      <div className="decision-section">
        <span>Reason</span>
        <p>{emptyText(safeDecision.reason)}</p>
      </div>

      <div className="decision-section">
        <span>Business Impact</span>
        <ul className="impact-list-styled">
          {impactItems.map((item, index) => (
            <li key={`${item}-${index}`}>
              <span className="impact-checkmark">✓</span>
              {item}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* RouteComparisonBlock — before vs after comparison panel             */
/* ------------------------------------------------------------------ */
export function RouteComparisonBlock({ comparison, previousRoute }) {
  const before = comparison?.before ?? previousRoute;
  const after = comparison?.after;
  if (!before || !after) return null;

  return (
    <div className="route-comparison-block">
      <div className="route-compare-header">
        <span className="route-compare-eyebrow">Route Comparison</span>
      </div>
      <div className="route-compare-cards-row">
        <div className="route-compare-card before">
          <span className="compare-label">Before</span>
          <strong>{before.label}</strong>
          <div className="compare-metrics">
            <span className="compare-cost">{before.cost}</span>
            <span className="compare-sep">·</span>
            <span className="compare-time">{before.time}</span>
          </div>
        </div>

        <div className="route-compare-arrow">
          <span>→</span>
          <span className="compare-arrow-label">AI Chose</span>
        </div>

        <div className="route-compare-card after">
          <span className="compare-label">After</span>
          <strong>{after.label}</strong>
          <div className="compare-metrics">
            <span className="compare-cost">{after.cost}</span>
            <span className="compare-sep">·</span>
            <span className="compare-time">{after.time}</span>
          </div>
          <span className="compare-badge-improved">Optimized</span>
        </div>
      </div>

      {comparison?.decision && (
        <div className="route-compare-decision">
          <span className="compare-label">Decision Rationale</span>
          <p>{comparison.decision}</p>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* AIActivityFeed — live scrollable event feed                         */
/* ------------------------------------------------------------------ */
export function AIActivityFeed({ events = [] }) {
  const containerRef = useRef(null);
  const prevLengthRef = useRef(events.length);

  // Auto-scroll to top when new events arrive
  useEffect(() => {
    if (events.length > prevLengthRef.current && containerRef.current) {
      containerRef.current.scrollTo({ top: 0, behavior: "smooth" });
    }
    prevLengthRef.current = events.length;
  }, [events.length]);

  const visibleEvents = events.slice(0, 20);

  if (!visibleEvents.length) {
    return (
      <div className="ai-feed-empty">
        <span className="ai-feed-empty-icon">🔍</span>
        <span>No AI actions recorded yet.</span>
      </div>
    );
  }

  return (
    <div className="ai-activity-feed" aria-label="Recent AI actions" ref={containerRef}>
      {visibleEvents.map((event, idx) => {
        const isRecent = idx === 0;
        return (
          <div className={`ai-feed-item ${isRecent ? "ai-feed-item-recent" : ""}`} key={event.id}>
            <span className="ai-feed-time">{event.time}</span>
            <div className="ai-feed-content">
              <strong>{event.title}</strong>
              {event.detail && <p>{event.detail}</p>}
            </div>
            {isRecent && <span className="ai-feed-new-badge">New</span>}
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* AIRerouteToast — popup notification for reroute events              */
/* ------------------------------------------------------------------ */
export function AIRerouteToast({ toasts, onDismiss }) {
  if (!toasts || toasts.length === 0) return null;
  return (
    <div className="toast-container" aria-live="polite">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`ai-toast ai-toast-${toast.type ?? "reroute"}`}
          role="alert"
        >
          <div className="toast-icon">{toast.type === "warning" ? "⚠" : "🧠"}</div>
          <div className="toast-body">
            <strong>{toast.title}</strong>
            {toast.detail && <p>{toast.detail}</p>}
          </div>
          <button
            className="toast-dismiss"
            onClick={() => onDismiss(toast.id)}
            aria-label="Dismiss notification"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
