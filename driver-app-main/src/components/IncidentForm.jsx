import { useState } from "react";
import { Panel, Input, Select } from "./common/UiPrimitives";

const INCIDENT_TYPES = [
  ["road_blockage", "Road Blockage"],
  ["strike", "Strike"],
  ["delay", "Delay"],
  ["port_congestion", "Port Congestion"],
  ["weather", "Weather"],
];

const CITIES = [
  ["Chennai", "Chennai"],
  ["Mumbai", "Mumbai"],
  ["Delhi", "Delhi"],
  ["Kolkata", "Kolkata"],
  ["Bangalore", "Bangalore"],
  ["Hyderabad", "Hyderabad"],
];

export function IncidentForm({ vehicle, onSubmit }) {
  const [showForm, setShowForm] = useState(false);
  const [city, setCity] = useState("Chennai");
  const [incidentType, setIncidentType] = useState("road_blockage");
  const [severity, setSeverity] = useState("0.7");
  const [note, setNote] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    if (!vehicle) return;
    await onSubmit({
      city,
      incident_type: incidentType,
      severity: Number(severity),
      note,
      vehicle_id: vehicle.id,
    });
    setNote("");
    setShowForm(false);
  }

  if (!showForm) {
    return (
      <Panel title="Report Incident">
        <button type="button" className="primary block" onClick={() => setShowForm(true)}>
          Open Incident Form
        </button>
      </Panel>
    );
  }

  return (
    <Panel title="Report Incident">
      <form className="incident-form" onSubmit={handleSubmit}>
        <div className="incident-form-grid">
          <Select label="City" value={city} options={CITIES} onChange={setCity} />
          <Select
            label="Incident Type"
            value={incidentType}
            options={INCIDENT_TYPES}
            onChange={setIncidentType}
          />
          <Input label="Severity (0-1)" value={severity} onChange={setSeverity} />
          <Input
            label="Note"
            value={note}
            onChange={setNote}
            required={false}
            placeholder="Optional details..."
          />
        </div>
        <div className="action-row">
          <button type="submit" className="primary">
            Submit Incident
          </button>
          <button type="button" className="secondary" onClick={() => setShowForm(false)}>
            Cancel
          </button>
        </div>
      </form>
    </Panel>
  );
}
