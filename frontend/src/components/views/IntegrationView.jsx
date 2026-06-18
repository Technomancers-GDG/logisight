import { useState, useEffect, useCallback } from "react";
import { Panel } from "../common/UiPrimitives";

const WEBHOOK_EVENTS = [
  "shipment.created",
  "shipment.updated",
  "shipment.delivered",
  "vehicle.status_changed",
  "driver.status_changed",
  "inventory.low_stock",
  "risk.alert",
];

export function IntegrationView({ apiFetch, t }) {
  const [keyInfo, setKeyInfo] = useState(null);
  const [fullKey, setFullKey] = useState(null);
  const [copied, setCopied] = useState(false);
  const [webhooks, setWebhooks] = useState([]);
  const [deliveries, setDeliveries] = useState([]);
  const [clients, setClients] = useState([]);
  const [loadingClients, setLoadingClients] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newUrl, setNewUrl] = useState("");
  const [newEvents, setNewEvents] = useState(["shipment.created"]);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  const loadKey = useCallback(async () => {
    try { setKeyInfo((await apiFetch("/api/v1/integration/manage/key")).data); } catch {}
  }, [apiFetch]);

  const loadWebhooks = useCallback(async () => {
    try { setWebhooks((await apiFetch("/api/v1/integration/webhooks")).items); } catch {}
  }, [apiFetch]);

  const loadDeliveries = useCallback(async () => {
    try { setDeliveries((await apiFetch("/api/v1/integration/webhooks/deliveries?limit=20")).items); } catch {}
  }, [apiFetch]);

  const loadClients = useCallback(async () => {
    setLoadingClients(true);
    try {
      const res = await apiFetch("/api/v1/integration/manage/clients");
      setClients(res.data || []);
    } catch {}
    setLoadingClients(false);
  }, [apiFetch]);

  useEffect(() => { loadKey(); loadWebhooks(); loadDeliveries(); loadClients(); }, [loadKey, loadWebhooks, loadDeliveries, loadClients]);

  const handleRegenerate = async () => {
    setError(""); setMsg("");
    try {
      const res = await apiFetch("/api/v1/integration/manage/key/regenerate", { method: "POST" });
      setFullKey(res.data.api_key);
      setKeyInfo({ ...keyInfo, api_key_prefix: res.data.api_key_prefix });
      setMsg(t.keyRegenerated);
    } catch (e) { setError(e.message); }
  };

  const handleCopy = () => {
    if (fullKey) { navigator.clipboard.writeText(fullKey); setCopied(true); setTimeout(() => setCopied(false), 2000); }
  };

  const toggleEvent = (ev) => {
    setNewEvents((prev) => prev.includes(ev) ? prev.filter((e) => e !== ev) : [...prev, ev]);
  };

  const handleCreate = async () => {
    if (!newUrl) return;
    setError(""); setMsg("");
    try {
      await apiFetch("/api/v1/integration/webhooks", { method: "POST", body: JSON.stringify({ url: newUrl, events: newEvents }) });
      setNewUrl(""); setNewEvents(["shipment.created"]); setCreating(false);
      await loadWebhooks();
      setMsg("Webhook created");
    } catch (e) { setError(e.message); }
  };

  const handleDelete = async (id) => {
    setError(""); setMsg("");
    try {
      await apiFetch(`/api/v1/integration/webhooks/${id}`, { method: "DELETE" });
      await loadWebhooks();
      setMsg("Webhook deleted");
    } catch (e) { setError(e.message); }
  };

  return (
    <div className="view-integration" style={{ maxWidth: 860, margin: "0 auto" }}>
      <h2 style={{ marginBottom: 24 }}>{t.logisightApi}</h2>

      {error && <div className="banner error" style={{ marginBottom: 16 }}>{error}</div>}
      {msg && <div className="banner success" style={{ marginBottom: 16 }}>{msg}</div>}

      {/* Client List */}
      <Panel title="Client Portal Accounts">
        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <button className="sim-btn" onClick={() => window.open("/client/register", "_blank")}>Register New Client</button>
          <button className="sim-btn" onClick={() => window.open("/client/login", "_blank")}>Open Portal</button>
        </div>
        {loadingClients ? <p style={{ color: "var(--muted)" }}>Loading...</p> : (
          <div style={{ overflowX: "auto" }}>
            <table className="data-table" style={{ width: "100%", fontSize: "0.85rem" }}>
              <thead>
                <tr>
                  <th>Company</th>
                  <th>Email</th>
                  <th>API Key</th>
                  <th>Status</th>
                  <th>Fac.</th>
                  <th>Veh.</th>
                  <th>Drv.</th>
                  <th>Obj.</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {clients.length === 0 ? (
                  <tr><td colSpan={9} style={{ textAlign: "center", color: "var(--muted)", padding: 24 }}>No client accounts registered</td></tr>
                ) : clients.filter(c => c.email).map((c) => (
                  <tr key={c.id}>
                    <td style={{ fontWeight: 600 }}>{c.name}</td>
                    <td style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>{c.email}</td>
                    <td style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>{c.api_key_prefix}***</td>
                    <td>
                      <span style={{
                        display: "inline-block", padding: "2px 8px", borderRadius: 4, fontSize: "0.75rem",
                        background: c.simulation_status === "running" ? "var(--success-bg, #064e3b)" : "var(--surface)",
                        color: c.simulation_status === "running" ? "var(--success, #10b981)" : "var(--muted)",
                      }}>{c.simulation_status || "inactive"}</span>
                    </td>
                    <td>{c.facilities}</td>
                    <td>{c.vehicles}</td>
                    <td>{c.drivers}</td>
                    <td>{c.objectives}</td>
                    <td style={{ whiteSpace: "nowrap", fontSize: "0.8rem" }}>{c.created_at?.slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <div style={{ height: 24 }} />

      {/* API Key */}
      <Panel title={t.developerApiKey}>
        <p style={{ color: "var(--muted)", marginBottom: 16 }}>{t.apiKeyDescription}</p>
        {fullKey ? (
          <div style={{ marginBottom: 16 }}>
            <div style={{
              background: "var(--bg)", padding: "12px 16px", borderRadius: 8,
              fontFamily: "monospace", fontSize: "0.85rem", wordBreak: "break-all",
              border: "1px solid var(--border)", marginBottom: 12,
            }}>{fullKey}</div>
            <button className="sim-btn primary" onClick={handleCopy}>
              {copied ? t.keyCopied : t.copyKey}
            </button>
          </div>
        ) : (
          <div style={{
            background: "var(--bg)", padding: "12px 16px", borderRadius: 8,
            fontFamily: "monospace", fontSize: "0.85rem", marginBottom: 12,
            border: "1px solid var(--border)", color: "var(--muted)",
          }}>
            {keyInfo?.api_key_prefix
              ? `${keyInfo.api_key_prefix}•••••••••••••••••••••••••••••••••••••••••`
              : "—"}
          </div>
        )}
        <button className="sim-btn" onClick={handleRegenerate}>{t.regenerateKey}</button>
      </Panel>

      <div style={{ height: 24 }} />

      {/* Webhooks */}
      <Panel title={t.developerWebhooks}>
        {webhooks.length === 0 && !creating && (
          <p style={{ color: "var(--muted)", marginBottom: 16 }}>{t.noWebhooks}</p>
        )}

        {webhooks.map((wh) => (
          <div key={wh.id} style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            padding: "12px 0", borderBottom: "1px solid var(--border)",
          }}>
            <div>
              <div style={{ fontFamily: "monospace", fontSize: "0.85rem", marginBottom: 4 }}>{wh.url}</div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {wh.events.map((ev) => (
                  <span key={ev} style={{
                    fontSize: "0.75rem", background: "var(--surface)", padding: "2px 8px",
                    borderRadius: 4, border: "1px solid var(--border)",
                  }}>{ev}</span>
                ))}
              </div>
            </div>
            <button className="sim-btn" style={{ flexShrink: 0 }} onClick={() => handleDelete(wh.id)}>
              {t.deleteWebhook}
            </button>
          </div>
        ))}

        {creating ? (
          <div style={{ marginTop: 16 }}>
            <div className="field">
              <span>{t.webhookUrl}</span>
              <input value={newUrl} onChange={(e) => setNewUrl(e.target.value)} placeholder="https://example.com/webhook" />
            </div>
            <div className="field">
              <span>{t.webhookEvents}</span>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                {WEBHOOK_EVENTS.map((ev) => (
                  <label key={ev} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: "0.85rem", cursor: "pointer" }}>
                    <input type="checkbox" checked={newEvents.includes(ev)} onChange={() => toggleEvent(ev)} />
                    {ev}
                  </label>
                ))}
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button className="sim-btn primary" onClick={handleCreate}>{t.createWebhook}</button>
              <button className="sim-btn" onClick={() => setCreating(false)}>Cancel</button>
            </div>
          </div>
        ) : (
          <button className="sim-btn" style={{ marginTop: 16 }} onClick={() => setCreating(true)}>
            {t.createWebhook}
          </button>
        )}
      </Panel>

      <div style={{ height: 24 }} />

      {/* Delivery Log */}
      <Panel title={t.developerLogs}>
        <div style={{ overflowX: "auto" }}>
          <table className="data-table" style={{ width: "100%", fontSize: "0.85rem" }}>
            <thead>
              <tr>
                <th>Event</th>
                <th>Webhook</th>
                <th>Status</th>
                <th>Attempts</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {deliveries.length === 0 ? (
                <tr><td colSpan={5} style={{ textAlign: "center", color: "var(--muted)", padding: 24 }}>No deliveries yet</td></tr>
              ) : deliveries.map((d) => (
                <tr key={d.id}>
                  <td style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>{d.event_type}</td>
                  <td style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.webhook_url}</td>
                  <td>
                    <span style={{
                      display: "inline-block", padding: "2px 8px", borderRadius: 4, fontSize: "0.75rem",
                      background: d.status === "delivered" ? "var(--success-bg, #064e3b)" : d.status === "failed" ? "var(--error-bg, #7f1d1d)" : "var(--surface)",
                      color: d.status === "delivered" ? "var(--success, #10b981)" : d.status === "failed" ? "var(--error, #ef4444)" : "var(--muted)",
                    }}>{d.status}</span>
                  </td>
                  <td>{d.attempts ?? 1}</td>
                  <td style={{ whiteSpace: "nowrap" }}>{d.created_at ? new Date(d.created_at + "Z").toLocaleString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
