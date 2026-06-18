import { useEffect, useState } from "react";
import { Panel } from "../common/UiPrimitives";

export function InventoryView({ inventoryForecast, proactiveDispatches, facilityLookup }) {
  const invData = inventoryForecast || [];

  if (invData.length === 0) {
    return (
      <div className="view-inventory">
        <Panel title="Inventory AI Forecast">
          <div className="empty" style={{ textAlign: "center", padding: "3rem", color: "#64748b" }}>
            No inventory forecast data available. Simulation needs to run to generate forecasts.
          </div>
        </Panel>
      </div>
    );
  }

  return (
    <div className="view-inventory" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div className="inventory-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1rem" }}>
        {invData.map((fac) => {
          const f = facilityLookup?.[fac.facility_id];
          return (
            <Panel key={fac.facility_id} title={fac.facility_name}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, fontSize: "0.85rem", color: "#94a3b8" }}>
                <span>{f?.city || "Unknown City"} | {f?.facility_type || "Facility"}</span>
                <span>Trend: <strong style={{ color: fac.trend === "increasing" ? "#ef4444" : (fac.trend === "decreasing" ? "#10b981" : "#eab308") }}>{fac.trend}</strong></span>
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem", marginTop: "1rem" }}>
                <tbody>
                  <tr style={{ borderBottom: "1px solid #1e293b" }}>
                    <td style={{ padding: "8px 4px", color: "#94a3b8" }}>Current Inventory</td>
                    <td style={{ padding: "8px 4px", textAlign: "right", color: "#f8fafc" }}>{f?.current_inventory_units ?? 0} units</td>
                  </tr>
                  <tr style={{ borderBottom: "1px solid #1e293b" }}>
                    <td style={{ padding: "8px 4px", color: "#94a3b8" }}>Predicted Demand</td>
                    <td style={{ padding: "8px 4px", textAlign: "right", color: "#f59e0b" }}>{fac.predicted_demand_units} units</td>
                  </tr>
                  <tr style={{ borderBottom: "1px solid #1e293b" }}>
                    <td style={{ padding: "8px 4px", color: "#94a3b8" }}>Safety Stock Level</td>
                    <td style={{ padding: "8px 4px", textAlign: "right", color: "#64748b" }}>{fac.safety_stock_units} units</td>
                  </tr>
                  <tr style={{ borderBottom: "1px solid #1e293b" }}>
                    <td style={{ padding: "8px 4px", color: "#94a3b8" }}>Reorder Point</td>
                    <td style={{ padding: "8px 4px", textAlign: "right", color: "#64748b" }}>{fac.reorder_point} units</td>
                  </tr>
                  <tr style={{ borderBottom: "1px solid #1e293b" }}>
                    <td style={{ padding: "8px 4px", color: "#94a3b8" }}>Recommended Dispatches</td>
                    <td style={{ padding: "8px 4px", textAlign: "right", color: "#3b82f6" }}>{fac.recommended_dispatch_count} trucks</td>
                  </tr>
                </tbody>
              </table>
            </Panel>
          );
        })}
      </div>
      {proactiveDispatches && proactiveDispatches.length > 0 && (
        <Panel title="Proactive Dispatches">
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #334155" }}>
                <th style={{ padding: "8px 4px", color: "#94a3b8", textAlign: "left" }}>Origin</th>
                <th style={{ padding: "8px 4px", color: "#94a3b8", textAlign: "left" }}>Destination</th>
                <th style={{ padding: "8px 4px", color: "#94a3b8", textAlign: "right" }}>Units</th>
                <th style={{ padding: "8px 4px", color: "#94a3b8", textAlign: "center" }}>Urgency</th>
                <th style={{ padding: "8px 4px", color: "#94a3b8", textAlign: "left" }}>Reason</th>
              </tr>
            </thead>
            <tbody>
              {proactiveDispatches.map((pd, i) => (
                <tr key={i} style={{ borderBottom: "1px solid #1e293b" }}>
                  <td style={{ padding: "8px 4px" }}>{facilityLookup?.[pd.origin_facility_id]?.name || pd.origin_facility_id}</td>
                  <td style={{ padding: "8px 4px" }}>{facilityLookup?.[pd.destination_facility_id]?.name || pd.destination_facility_id}</td>
                  <td style={{ padding: "8px 4px", textAlign: "right", color: "#f8fafc" }}>{pd.recommended_units}</td>
                  <td style={{ padding: "8px 4px", textAlign: "center" }}>
                    <span style={{ 
                      background: pd.urgency === "high" ? "#7f1d1d" : (pd.urgency === "medium" ? "#713f12" : "#1e3a8a"), 
                      color: pd.urgency === "high" ? "#fca5a5" : (pd.urgency === "medium" ? "#fde047" : "#bfdbfe"),
                      padding: "2px 6px", borderRadius: "4px", fontSize: "0.75rem", textTransform: "uppercase"
                    }}>
                      {pd.urgency}
                    </span>
                  </td>
                  <td style={{ padding: "8px 4px", color: "#94a3b8" }}>{pd.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </div>
  );
}
