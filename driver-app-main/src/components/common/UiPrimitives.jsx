export function Panel({ title, children, variant, className = "" }) {
  const cls = ["panel", variant, className].filter(Boolean).join(" ");
  return (
    <section className={cls}>
      {title && (
        <div className="panel-head">
          <h2>{title}</h2>
        </div>
      )}
      {children}
    </section>
  );
}

export function Input({ label, value, onChange, required = true, placeholder }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        placeholder={placeholder}
      />
    </label>
  );
}

export function Select({ label, value, options, onChange, required = true }) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} required={required}>
        <option value="">Select</option>
        {options.map(([optVal, optLabel]) => (
          <option key={optVal} value={optVal}>
            {optLabel}
          </option>
        ))}
      </select>
    </label>
  );
}

export function MetricCard({ label, value, sub, accent }) {
  return (
    <div className={`metric-card${accent ? " accent" : ""}`}>
      <span className="metric-label">{label}</span>
      <span className="metric-value">{value}</span>
      {sub && <span className="metric-sub">{sub}</span>}
    </div>
  );
}

export function StatusBadge({ status }) {
  const s = String(status ?? "").toLowerCase();
  let cls = "decision";
  if (s === "accepted" || s === "active" || s === "success") cls += " accepted";
  else if (s === "rejected" || s === "error") cls += " rejected";
  return <span className={cls}>{status}</span>;
}
