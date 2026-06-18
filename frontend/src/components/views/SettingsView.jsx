export function SettingsView({ lang, onSwitchLang, t, onSetSpeed, currentSpeed, isClient }) {
  const speedOptions = [1, 5, 15, 30, 60, 120, 180, 500, 1000, 5000, 100000];
  
  return (
    <div className="view-settings" style={{ maxWidth: 640, margin: "0 auto" }}>
      <h2 style={{ marginBottom: 24 }}>{t.settings}</h2>

      <div
        className="settings-card"
        style={{
          background: "var(--surface)",
          borderRadius: 12,
          padding: 24,
          border: "1px solid var(--border)",
        }}
      >
        <div style={{ marginBottom: 16 }}>
          <h3 style={{ margin: "0 0 6px", fontSize: "1.05rem" }}>{t.language}</h3>
          <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.9rem" }}>
            Choose your preferred interface language.
          </p>
        </div>

        <div style={{ display: "flex", gap: 12 }}>
          <button
            className={`sim-btn ${lang === "en" ? "primary" : ""}`}
            onClick={() => onSwitchLang("en")}
            aria-pressed={lang === "en"}
          >
            {t.english}
          </button>
          <button
            className={`sim-btn ${lang === "hi" ? "primary" : ""}`}
            onClick={() => onSwitchLang("hi")}
            aria-pressed={lang === "hi"}
          >
            {t.hindi}
          </button>
        </div>
      </div>

      {isClient && (
        <div
          className="settings-card"
          style={{
            background: "var(--surface)",
            borderRadius: 12,
            padding: 24,
            border: "1px solid var(--border)",
            marginTop: 24
          }}
        >
          <div style={{ marginBottom: 16 }}>
            <h3 style={{ margin: "0 0 6px", fontSize: "1.05rem" }}>Backend Simulation Speed</h3>
            <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.9rem" }}>
              Accelerate the simulation engine to test the platform. The actual speed is shown on the top bar in real-time.
            </p>
          </div>
          
          <select 
            className="speed-select" 
            value={currentSpeed} 
            onChange={e => onSetSpeed?.(Number(e.target.value))}
            style={{ padding: "10px", borderRadius: "8px", background: "#111", color: "#fff", border: "1px solid #333", fontSize: "1rem" }}
          >
            {speedOptions.map(s => (
              <option key={s} value={s}>{s}x {s >= 5000 ? "(TURBO)" : ""}</option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}
