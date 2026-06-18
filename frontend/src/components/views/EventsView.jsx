import { Panel } from "../common/UiPrimitives";

const SIM_EVENT_LABELS = {
  dispatch: "Dispatch Started",
  load_complete: "Loading Complete",
  arrive: "Delivery Arrived",
  unload_complete: "Unload Complete",
  rest_complete: "Driver Rest Complete",
};

const SIM_EVENT_DESCRIPTIONS = {
  dispatch: "Vehicle dispatched from origin facility.",
  load_complete: "Loading finished, vehicle en route to destination.",
  arrive: "Vehicle arrived at destination facility.",
  unload_complete: "Unloading completed, inventory updated.",
  rest_complete: "Driver rest period ended.",
};

function formatSimEvent(e) {
  const eventType = e.event_type ?? "";
  const title = SIM_EVENT_LABELS[eventType] || eventType.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  const description = SIM_EVENT_DESCRIPTIONS[eventType] || "";
  const timestamp = e.processed_time
    ? new Date(e.processed_time.endsWith("Z") ? e.processed_time : e.processed_time + "Z").toLocaleString()
    : null;
  const impactScore = e.payload?.impact_score ?? null;
  return { title, description, timestamp, impactScore };
}

export function EventsView({ events = [] }) {
  const displayEvents = events.slice(0, 20);

  return (
    <div className="view-events">
      <Panel title="Active Events Feed">
        {displayEvents.length === 0 ? (
          <div className="empty">No events recorded yet.</div>
        ) : (
          <div className="event-stack">
            {displayEvents.map((e, i) => {
              const isNewsEvent = e.headline != null;
              if (isNewsEvent) {
                return (
                  <div className="event-card" key={i}>
                    <div className="event-top"><strong>{e.city}</strong><span>{e.category}</span></div>
                    <p>{e.headline}</p>
                    <small>{e.impact_type} • impact {Number(e.impact_score ?? 0).toFixed(2)}</small>
                  </div>
                );
              }

              const sim = formatSimEvent(e);
              return (
                <div className="event-card" key={i}>
                  <div className="event-top">
                    <strong>{sim.title}</strong>
                    <span>{e.event_type}</span>
                  </div>
                  {sim.description && <p>{sim.description}</p>}
                  <small>
                    {sim.timestamp ? `${sim.timestamp}` : ""}
                    {sim.impactScore != null ? ` • impact ${Number(sim.impactScore).toFixed(2)}` : ""}
                  </small>
                </div>
              );
            })}
          </div>
        )}
      </Panel>
    </div>
  );
}
