import { useState, useEffect } from "react";

const TEMPLATES = {
  facilities: { label: "Facilities", icon: "\ud83d\udce6", endpoint: "/api/v1/client/upload/facilities", fields: "name,city,facility_type,latitude,longitude,base_capacity_units" },
  vehicles: { label: "Vehicles", icon: "\ud83d\ude9b", endpoint: "/api/v1/client/upload/vehicles", fields: "identifier,vehicle_type,payload_capacity_units,home_facility_name,average_speed_kmph" },
  drivers: { label: "Drivers", icon: "\ud83d\udc64", endpoint: "/api/v1/client/upload/drivers", fields: "name,active" },
  objectives: { label: "Objectives", icon: "\ud83d\udccb", endpoint: "/api/v1/client/upload/objectives", fields: "name,commodity,origin_facility_name,destination_facility_name,dispatch_interval_minutes,sla_minutes,priority" },
};

const ORDER = ["facilities", "vehicles", "drivers", "objectives"];

function apiFetch(apiKey, firebaseToken, path, options = {}) {
  const { headers: optHeaders, ...rest } = options;
  const isGet = !options.method || options.method.toUpperCase() === "GET";
  
  const authHeaders = {};
  if (apiKey) authHeaders["X-API-Key"] = apiKey;
  if (firebaseToken) authHeaders["Authorization"] = `Bearer ${firebaseToken}`;

  return fetch(path, {
    headers: {
      ...(isGet ? {} : { "Content-Type": "text/csv" }),
      ...authHeaders,
      ...(optHeaders || {}),
    },
    ...rest,
  }).then(r => { if (!r.ok) throw new Error(r.status === 401 ? "Authentication failed" : "Upload failed"); return r.json(); });
}

function UploadTile({ category, config, onComplete, completed, apiKey, firebaseToken, autoFillData }) {
  const [csvText, setCsvText] = useState("");
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    if (autoFillData) {
      setCsvText(autoFillData);
    }
  }, [autoFillData]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const handleImport = async () => {
    if (!csvText.trim()) return;
    setImporting(true);
    setError("");
    try {
      const resp = await apiFetch(apiKey, firebaseToken, config.endpoint, {
        method: "POST",
        body: csvText.trim(),
        headers: { "Content-Type": "text/csv" },
      });
      setResult(resp);
      if (resp.success) onComplete(category);
    } catch (err) {
      setError(err.message);
    } finally {
      setImporting(false);
    }
  };

  return (
    <div style={{ background: "#1a2332", border: completed ? "2px solid #059669" : "1px solid #2a3342", borderRadius: 12, padding: 20 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <span style={{ fontSize: 24 }}>{config.icon}</span>
        <div>
          <h3 style={{ color: "#f4f7fb", margin: 0, fontSize: 16 }}>{config.label}</h3>
        </div>
        {completed && <span style={{ marginLeft: "auto", color: "#10b981", fontSize: 20 }}>&#10003;</span>}
      </div>
      {!completed ? (
        <>
          <textarea
            value={csvText}
            onChange={e => setCsvText(e.target.value)}
            placeholder={`Paste CSV data here:\n${config.fields}`}
            rows={5}
            style={{ width: "100%", padding: 10, background: "#111827", border: "1px solid #374151", borderRadius: 6, color: "#f4f7fb", fontSize: 12, fontFamily: "monospace", resize: "vertical" }}
          />
          <button onClick={handleImport} disabled={importing || !csvText.trim()}
            style={{ marginTop: 10, padding: "8px 16px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 13 }}>
            {importing ? "Importing..." : "Import"}
          </button>
          {error && <div style={{ marginTop: 8, color: "#fca5a5", fontSize: 12 }}>{error}</div>}
          {result && (
            <div style={{ marginTop: 8, fontSize: 12, color: result.success ? "#6ee7b7" : "#fca5a5" }}>
              {result.imported} imported. {result.errors?.length || 0} errors.
            </div>
          )}
        </>
      ) : (
        <div style={{ color: "#6ee7b7", fontSize: 14 }}>Upload complete</div>
      )}
    </div>
  );
}

export default function OnboardingWizard({ apiKey, firebaseToken, onComplete }) {
  const [completed, setCompleted] = useState({});
  const [allDone, setAllDone] = useState(false);
  const [autoFillData, setAutoFillData] = useState({});

  const handleDemoImport = async () => {
    const data = {};
    for (const cat of ORDER) {
      try {
        const res = await fetch(`/sim-test/${cat}.csv`);
        if (res.ok) {
          data[cat] = await res.text();
        }
      } catch (err) {
        console.error("Failed to load demo CSV for", cat, err);
      }
    }
    setAutoFillData(data);
  };

  useEffect(() => {
    async function loadStatus() {
      if (!apiKey && !firebaseToken) return;
      try {
        const s = await apiFetch(apiKey, firebaseToken, "/api/v1/client/upload-status");
        const c = {};
        if (s.facilities) c.facilities = true;
        if (s.vehicles) c.vehicles = true;
        if (s.drivers) c.drivers = true;
        if (s.objectives) c.objectives = true;
        setCompleted(c);
        if (s.all_complete) {
          setAllDone(true);
          onComplete?.();
        }
      } catch {
        setCompleted({});
        setAllDone(false);
      }
    }
    loadStatus();
  }, [apiKey, firebaseToken, onComplete]);

  const handleComplete = (category) => {
    setCompleted(c => {
      const next = { ...c, [category]: true };
      if (ORDER.every(k => next[k])) setAllDone(true);
      return next;
    });
  };

  const doneCount = ORDER.filter(k => completed[k]).length;

  return (
    <div style={{ minHeight: "100vh", background: "#101622", padding: 40 }}>
      <div style={{ maxWidth: 900, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div className="logo-mark large" style={{ margin: "0 auto 12px", background: "#2563eb" }}>L</div>
          <h2 style={{ color: "#f4f7fb", margin: 0 }}>Set Up Your Fleet</h2>
          <p style={{ color: "#8b8d93", marginTop: 8 }}>
            Upload all 4 categories to activate your operations dashboard.
          </p>
        </div>

        <div style={{ display: "flex", gap: 8, marginBottom: 24, justifyContent: "center" }}>
          {ORDER.map((k, i) => (
            <div key={k} style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ color: completed[k] ? "#10b981" : "#6b7280", fontSize: 13 }}>
                {completed[k] ? "\u2713" : "\u2014"} {TEMPLATES[k].label}
              </span>
              {i < 3 && <span style={{ color: "#374151" }}>&#8594;</span>}
            </div>
          ))}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 16 }}>
          {ORDER.map(category => (
            <UploadTile key={category} category={category} config={TEMPLATES[category]} onComplete={handleComplete} completed={!!completed[category]} apiKey={apiKey} firebaseToken={firebaseToken} autoFillData={autoFillData[category]} />
          ))}
        </div>

        {allDone && (
          <div style={{ textAlign: "center", marginTop: 32 }}>
            <div style={{ background: "#065f46", borderRadius: 12, padding: 24 }}>
              <span style={{ fontSize: 36 }}>&#127881;</span>
              <h3 style={{ color: "#6ee7b7", margin: "8px 0" }}>Your operations are now live!</h3>
              <button
                onClick={() => onComplete?.()}
                style={{ padding: "12px 24px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 6, fontSize: 15, fontWeight: 600, cursor: "pointer" }}>
                Go to Dashboard
              </button>
            </div>
          </div>
        )}

        {!allDone && (
          <div style={{ position: "fixed", bottom: 40, right: 40 }}>
            <button
              onClick={handleDemoImport}
              title="for demo purpose only"
              style={{
                padding: "10px 20px",
                background: "#10b981",
                color: "#fff",
                border: "none",
                borderRadius: 8,
                cursor: "pointer",
                fontSize: 14,
                fontWeight: "bold",
                boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)"
              }}
            >
              Import
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
