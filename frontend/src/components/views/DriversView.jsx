import React, { useState } from "react";
import { Panel } from "../common/UiPrimitives";

function driverTone(overrideRating) {
  if (overrideRating < 0.7) {
    return "danger";
  }
  if (overrideRating <= 1.0) {
    return "warning";
  }
  return "good";
}

function decisionOutcome(decision) {
  if (decision.rating_delta > 0) {
    return "better";
  }
  if (decision.rating_delta < 0) {
    return "worse";
  }
  return "neutral";
}

export function DriversView({ drivers, vehicles, decisions, handleDriverQuickUpdate }) {
  const [expandedDriverId, setExpandedDriverId] = useState(null);

  async function onBiasChange(driver, field, nextValue) {
    await handleDriverQuickUpdate(driver.id, {
      [field]: Number(nextValue),
    });
  }

  return (
    <section className="grid-two">
      <Panel title="Driver Profiles">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Override Rating</th>
                <th scope="col">Confidence</th>
                <th scope="col">Accept Bias</th>
                <th scope="col">Active</th>
                <th scope="col"># Vehicles</th>
              </tr>
            </thead>
            <tbody>
              {drivers.map((driver) => {
                const assignedVehicles = vehicles.filter(
                  (vehicle) => vehicle.driver_profile_id === driver.id,
                );
                const isExpanded = expandedDriverId === driver.id;

                return (
                  <React.Fragment key={driver.id}>
                    <tr role="button" tabIndex={0} onClick={() => setExpandedDriverId(isExpanded ? null : driver.id)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setExpandedDriverId(isExpanded ? null : driver.id); } }}>
                      <td>{driver.name}</td>
                      <td>
                        <span className={`status-badge ${driverTone(driver.override_rating)}`}>
                          {(driver.override_rating ?? 1.0).toFixed(2)}
                        </span>
                      </td>
                      <td>{((driver.confidence ?? 0.5) * 100).toFixed(0)}%</td>
                      <td>{((driver.accept_recommendation_bias ?? 0.5) * 100).toFixed(0)}%</td>
                      <td>{driver.active ? "yes" : "no"}</td>
                      <td>{assignedVehicles.length}</td>
                    </tr>
                    {isExpanded ? (
                      <tr key={`${driver.id}-details`}>
                        <td colSpan={6}>
                          <div className="lane-stack">
                            <div className="lane-card">
                              <div className="lane-head">
                                <h3>Assigned Vehicles</h3>
                              </div>
                              <div className="chip-row">
                                {assignedVehicles.length === 0
                                  ? "No assigned vehicles"
                                  : assignedVehicles.map((vehicle) => (
                                      <span key={vehicle.id} className="chip">
                                        {vehicle.identifier}
                                      </span>
                                    ))}
                              </div>
                            </div>

                            <div className="lane-card">
                              <div className="lane-head">
                                <h3>Recent Decisions</h3>
                              </div>
                              <div className="lane-stack">
                                {decisions
                                  .filter((decision) => decision.driver_profile_id === driver.id)
                                  .slice(0, 6)
                                  .map((decision) => (
                                    <div key={decision.id} className="event-card">
                                      <div className="event-top">
                                        <strong>{decision.decision}</strong>
                                        <span className={`status-badge ${decisionOutcome(decision) === "better" ? "good" : decisionOutcome(decision) === "worse" ? "danger" : "warning"}`}>
                                          {decisionOutcome(decision)}
                                        </span>
                                      </div>
                                      <small>
                                        rating delta {decision.rating_delta.toFixed(2)}
                                      </small>
                                      <p>{decision.note || "No note provided"}</p>
                                    </div>
                                  ))}
                              </div>
                            </div>

                            <div className="lane-card">
                              <div className="lane-head">
                                <h3>Bias Tuning</h3>
                              </div>
                              <label className="field">
                                <span>Override Rating: {(driver.override_rating ?? 1.0).toFixed(2)}</span>
                                <input
                                  type="range"
                                  min="0.4"
                                  max="1.5"
                                  step="0.01"
                                  value={driver.override_rating}
                                  onChange={(event) => onBiasChange(driver, "override_rating", event.target.value)}
                                />
                              </label>
                              <label className="field">
                                <span>Confidence: {(driver.confidence ?? 0.5).toFixed(2)}</span>
                                <input
                                  type="range"
                                  min="0"
                                  max="1"
                                  step="0.01"
                                  value={driver.confidence}
                                  onChange={(event) => onBiasChange(driver, "confidence", event.target.value)}
                                />
                              </label>
                              <label className="field">
                                <span>
                                  Accept Recommendation Bias: {(driver.accept_recommendation_bias ?? 0.5).toFixed(2)}
                                </span>
                                <input
                                  type="range"
                                  min="0"
                                  max="1"
                                  step="0.01"
                                  value={driver.accept_recommendation_bias}
                                  onChange={(event) =>
                                    onBiasChange(driver, "accept_recommendation_bias", event.target.value)
                                  }
                                />
                              </label>
                            </div>
                          </div>
                        </td>
                      </tr>
                    ) : null}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Driver Insights">
        <div className="lane-stack">
          {drivers.map((driver) => {
            const driverDecisions = decisions.filter(
              (decision) => decision.driver_profile_id === driver.id,
            );
            const accepted = driverDecisions.filter((decision) => decision.decision === "accepted").length;
            const ignored = driverDecisions.filter((decision) => decision.decision === "ignored").length;

            return (
              <div className="lane-card" key={driver.id}>
                <div className="lane-head">
                  <h3>{driver.name}</h3>
                  <span className={`status-badge ${driverTone(driver.override_rating)}`}>
                    {(driver.override_rating ?? 1.0).toFixed(2)}
                  </span>
                </div>
                <div className="lane-meta">
                  <span>Decisions: {driverDecisions.length}</span>
                  <span>Accepted: {accepted}</span>
                  <span>Ignored: {ignored}</span>
                </div>
              </div>
            );
          })}
        </div>
      </Panel>
    </section>
  );
}
