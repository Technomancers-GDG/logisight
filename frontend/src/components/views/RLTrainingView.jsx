import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { Panel } from "../common/UiPrimitives";

/* ── colour tokens ─────────────────────────────────────────────── */
const C = {
  bg:      "#0b1121",
  panel:   "#111827",
  panel2:  "#1a2332",
  border:  "#1e293b",
  text:    "#f1f5f9",
  muted:   "#64748b",
  accent:  "#b9ff66",
  teal:    "#14b8a6",
  coral:   "#f97316",
  blue:    "#3b82f6",
  purple:  "#8b5cf6",
  amber:   "#f59e0b",
  red:     "#ef4444",
  green:   "#22c55e",
};

const ACTION_COLORS = [C.blue, C.teal, C.purple, C.amber, C.red];
const ACTION_LABELS = {
  continue: "Continue",
  reroute_warehouse: "Reroute → Warehouse",
  reroute_port: "Reroute → Port",
  wait: "Wait",
  defer_dispatch: "Defer Dispatch",
};

/* ── keyframe + scoped CSS ─────────────────────────────────────── */
const STYLE_ID = "rl-training-view-styles";

function injectStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
/* ── animations ── */
@keyframes rl-pulse { 0%,100%{opacity:1} 50%{opacity:.55} }
@keyframes rl-shimmer { 0%{background-position:-200% 0} 100%{background-position:200% 0} }
@keyframes rl-fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
@keyframes rl-slideRight { from{width:0} to{width:var(--target-w)} }
@keyframes rl-glow { 0%,100%{box-shadow:0 0 8px rgba(185,255,102,.15)} 50%{box-shadow:0 0 20px rgba(185,255,102,.35)} }

/* ── root ── */
.rl-view{
  display:flex;flex-direction:column;gap:20px;
  animation:rl-fadeIn .45s ease-out;
  color:${C.text};
}

/* ── banner ── */
.rl-banner{
  background:linear-gradient(135deg,${C.panel} 0%,${C.panel2} 100%);
  border:1px solid ${C.border};border-radius:14px;
  padding:24px 28px;position:relative;overflow:hidden;
}
.rl-banner::before{
  content:"";position:absolute;top:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,${C.accent},${C.teal},${C.coral});
}
.rl-banner-status{
  display:flex;align-items:center;gap:14px;
  font-size:1.15rem;font-weight:600;margin-bottom:18px;
}
.rl-banner-status .dot{
  width:14px;height:14px;border-radius:50%;flex-shrink:0;
}
.rl-banner-status .dot.warmup{background:${C.amber};animation:rl-pulse 1.5s ease-in-out infinite;}
.rl-banner-status .dot.active{background:${C.green};box-shadow:0 0 10px ${C.green};}

/* warmup progress */
.rl-warmup-bar{
  height:8px;border-radius:6px;background:${C.border};overflow:hidden;margin-top:6px;
}
.rl-warmup-fill{
  height:100%;border-radius:6px;
  background:linear-gradient(90deg,${C.amber},${C.accent});
  transition:width .6s ease;
  background-size:200% 100%;animation:rl-shimmer 2s linear infinite;
}

/* stats row */
.rl-stats-row{
  display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
  gap:12px;margin-top:16px;
}
.rl-stat-box{
  background:${C.bg};border:1px solid ${C.border};border-radius:10px;
  padding:12px 14px;text-align:center;
  transition:border-color .25s,transform .2s;
}
.rl-stat-box:hover{border-color:${C.accent};transform:translateY(-2px);}
.rl-stat-box .label{font-size:.75rem;color:${C.muted};text-transform:uppercase;letter-spacing:.6px;}
.rl-stat-box .value{font-size:1.35rem;font-weight:700;margin-top:4px;}

/* epsilon gauge */
.rl-epsilon-gauge{margin-top:18px;}
.rl-epsilon-gauge .title{font-size:.8rem;color:${C.muted};margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px;}
.rl-gauge-track{
  display:flex;height:28px;border-radius:8px;overflow:hidden;
  border:1px solid ${C.border};
}
.rl-gauge-exploit{
  background:linear-gradient(90deg,${C.teal},${C.blue});
  display:flex;align-items:center;justify-content:center;
  font-size:.72rem;font-weight:700;color:#fff;
  transition:width .6s ease;min-width:0;overflow:hidden;white-space:nowrap;
}
.rl-gauge-explore{
  background:linear-gradient(90deg,${C.amber},${C.coral});
  display:flex;align-items:center;justify-content:center;
  font-size:.72rem;font-weight:700;color:#fff;
  transition:width .6s ease;min-width:0;overflow:hidden;white-space:nowrap;
}
.rl-gauge-labels{display:flex;justify-content:space-between;margin-top:4px;font-size:.72rem;color:${C.muted};}

/* ── charts grid ── */
.rl-charts-grid{
  display:grid;grid-template-columns:repeat(3,1fr);gap:16px;
}
@media(max-width:1100px){.rl-charts-grid{grid-template-columns:1fr;}}
.rl-chart-card{
  background:${C.panel};border:1px solid ${C.border};border-radius:12px;
  padding:16px;animation:rl-fadeIn .5s ease-out;
  transition:border-color .25s;
}
.rl-chart-card:hover{border-color:${C.accent}44;}
.rl-chart-title{
  font-size:.85rem;font-weight:600;margin-bottom:12px;
  display:flex;align-items:center;gap:8px;
}
.rl-chart-title .dot{width:10px;height:10px;border-radius:50%;}

/* ── distribution + Q-values row ── */
.rl-insights-grid{
  display:grid;grid-template-columns:1fr 1fr;gap:16px;
}
@media(max-width:900px){.rl-insights-grid{grid-template-columns:1fr;}}

.rl-dist-card,.rl-qval-card{
  background:${C.panel};border:1px solid ${C.border};border-radius:12px;
  padding:20px;animation:rl-fadeIn .55s ease-out;
}
.rl-dist-inner{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:center;}
@media(max-width:600px){.rl-dist-inner{grid-template-columns:1fr;}}

/* exploration table */
.rl-exp-table{width:100%;border-collapse:collapse;font-size:.82rem;}
.rl-exp-table th{text-align:left;color:${C.muted};padding:6px 8px;border-bottom:1px solid ${C.border};font-weight:500;}
.rl-exp-table td{padding:6px 8px;border-bottom:1px solid ${C.border}22;}
.rl-exp-table .badge{
  display:inline-block;padding:2px 8px;border-radius:6px;font-size:.72rem;font-weight:600;
}
.badge-exploit{background:${C.teal}22;color:${C.teal};}
.badge-explore{background:${C.amber}22;color:${C.amber};}

/* ── episodes table ── */
.rl-episodes-wrap{
  background:${C.panel};border:1px solid ${C.border};border-radius:12px;
  padding:20px;animation:rl-fadeIn .6s ease-out;
  max-height:420px;overflow-y:auto;
}
.rl-episodes-wrap::-webkit-scrollbar{width:6px;}
.rl-episodes-wrap::-webkit-scrollbar-track{background:${C.bg};}
.rl-episodes-wrap::-webkit-scrollbar-thumb{background:${C.border};border-radius:3px;}
.rl-ep-table{width:100%;border-collapse:collapse;font-size:.82rem;}
.rl-ep-table thead th{
  position:sticky;top:0;background:${C.panel};
  text-align:left;padding:8px 10px;color:${C.muted};
  border-bottom:2px solid ${C.border};font-weight:600;
  text-transform:uppercase;letter-spacing:.4px;font-size:.72rem;
}
.rl-ep-table tbody tr{transition:background .2s;}
.rl-ep-table tbody tr:hover{background:${C.bg}88;}
.rl-ep-table tbody td{padding:8px 10px;border-bottom:1px solid ${C.border}44;}
.rl-ep-table .row-positive{border-left:3px solid ${C.green};}
.rl-ep-table .row-negative{border-left:3px solid ${C.red};}
.rl-ep-table .row-neutral{border-left:3px solid ${C.muted};}

.chosen-badge{
  display:inline-block;padding:2px 10px;border-radius:20px;font-size:.7rem;font-weight:700;
  text-transform:uppercase;letter-spacing:.3px;
}
.chosen-exploitation{background:${C.teal}22;color:${C.teal};}
.chosen-exploration{background:${C.amber}22;color:${C.amber};}
.chosen-rule_fallback,.chosen-rule-fallback{background:${C.purple}22;color:${C.purple};}

.sla-met{color:${C.green};font-weight:600;}
.sla-missed{color:${C.red};font-weight:600;}

/* ── controls section ── */
.rl-controls{
  display:flex;gap:12px;flex-wrap:wrap;align-items:center;
}
.rl-btn{
  padding:10px 22px;border-radius:10px;border:none;
  font-weight:600;font-size:.85rem;cursor:pointer;
  transition:all .25s;display:flex;align-items:center;gap:8px;
}
.rl-btn:disabled{opacity:.5;cursor:not-allowed;}
.rl-btn-primary{
  background:linear-gradient(135deg,${C.accent},${C.teal});
  color:${C.bg};
}
.rl-btn-primary:hover:not(:disabled){transform:translateY(-2px);box-shadow:0 4px 16px ${C.accent}44;}
.rl-btn-danger{
  background:transparent;border:1px solid ${C.red};color:${C.red};
}
.rl-btn-danger:hover:not(:disabled){background:${C.red}18;transform:translateY(-2px);}

.rl-spinner{
  display:inline-block;width:16px;height:16px;
  border:2px solid transparent;border-top-color:currentColor;border-radius:50%;
  animation:rl-spin .6s linear infinite;
}
@keyframes rl-spin{to{transform:rotate(360deg)}}

/* ── section title ── */
.rl-section-title{
  font-size:1rem;font-weight:700;margin-bottom:4px;
  display:flex;align-items:center;gap:8px;
}
.rl-view > .rl-section-title {
  color: var(--text, #111827);
}

/* ── empty / loading ── */
.rl-empty{color:${C.muted};text-align:center;padding:32px;font-style:italic;}
.rl-loading-overlay{
  display:flex;align-items:center;justify-content:center;
  padding:60px;color:${C.muted};gap:12px;font-size:.9rem;
}

/* ── custom tooltip ── */
.rl-tooltip{
  background:${C.panel}ee;border:1px solid ${C.border};border-radius:8px;
  padding:10px 14px;font-size:.78rem;color:${C.text};
  box-shadow:0 4px 20px rgba(0,0,0,.5);
}
.rl-tooltip .label{color:${C.muted};margin-bottom:4px;}
.rl-tooltip .value{font-weight:700;font-size:.9rem;}

/* ── max-q highlight bar ── */
.rl-qbar-max{filter:brightness(1.3);stroke:${C.accent};stroke-width:2px;}

/* ── training activity feed ── */
.rl-activity-wrap{
  background:${C.panel};border:1px solid ${C.border};border-radius:12px;
  padding:0;overflow:hidden;animation:rl-fadeIn .5s ease-out;
}
.rl-activity-header{
  display:grid;grid-template-columns:80px 1fr 1fr 90px 1fr 1fr;
  gap:8px;padding:10px 16px;
  background:${C.bg};border-bottom:1px solid ${C.border};
  font-size:.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.4px;color:${C.muted};
}
.rl-activity-body{
  max-height:320px;overflow-y:auto;
}
.rl-activity-body::-webkit-scrollbar{width:5px;}
.rl-activity-body::-webkit-scrollbar-track{background:${C.bg};}
.rl-activity-body::-webkit-scrollbar-thumb{background:${C.border};border-radius:3px;}
.rl-activity-row{
  display:grid;grid-template-columns:80px 1fr 1fr 90px 1fr 1fr;
  gap:8px;padding:8px 16px;font-size:.78rem;font-family:ui-monospace,monospace;
  border-bottom:1px solid ${C.border}22;
  animation:rl-fadeIn .3s ease-out both;
  transition:background .2s;
}
.rl-activity-row:hover{background:${C.bg}88;}
.rl-activity-row:last-child{border-bottom:none;}
.rl-activity-step{color:${C.accent};font-weight:600;}
.rl-na{color:${C.muted};}
@media(max-width:800px){
  .rl-activity-header,.rl-activity-row{grid-template-columns:60px 1fr 70px 1fr;font-size:.72rem;}
  .rl-activity-header span:nth-child(3),.rl-activity-header span:nth-child(6),
  .rl-activity-row span:nth-child(3),.rl-activity-row span:nth-child(6){display:none;}
}
`;
  document.head.appendChild(style);
}

/* ── custom Recharts tooltip ──────────────────────────────────── */
function ChartTooltip({ active, payload, label, formatter }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rl-tooltip">
      <div className="label">{label}</div>
      {payload.map((p, i) => (
        <div key={i} className="value" style={{ color: p.color }}>
          {p.name}: {formatter ? formatter(p.value) : (typeof p.value === "number" ? p.value.toFixed(4) : p.value)}
        </div>
      ))}
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════
   RL TRAINING VIEW — Main export
   ════════════════════════════════════════════════════════════════ */
export function RLTrainingView({ apiFetch }) {
  /* ── state ── */
  const [stats, setStats] = useState(null);
  const [history, setHistory] = useState([]);
  const [episodes, setEpisodes] = useState([]);
  const [actionDist, setActionDist] = useState([]);
  const [qValues, setQValues] = useState(null);
  const [loading, setLoading] = useState(true);
  const [training, setTraining] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState("");
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    injectStyles();
    return () => { mountedRef.current = false; };
  }, []);

  /* ── fetch helpers ── */
  const fetchAll = useCallback(async (showSpinner = false) => {
    if (showSpinner) setLoading(true);
    try {
      const [s, h, ep, ad, qv] = await Promise.all([
        apiFetch("/api/rl/stats").catch(() => null),
        apiFetch("/api/rl/training-history?limit=500").catch(() => []),
        apiFetch("/api/rl/episodes?limit=50").catch(() => []),
        apiFetch("/api/rl/action-distribution").catch(() => []),
        apiFetch("/api/rl/q-values").catch(() => null),
      ]);
      if (!mountedRef.current) return;
      setStats(s);
      setHistory(Array.isArray(h) ? h : (h?.training_steps ?? []));
      setEpisodes(Array.isArray(ep) ? ep : (ep?.episodes ?? []));
      const rawCounts = ad?.counts ?? ad?.actions ?? ad ?? {};
      setActionDist(Array.isArray(rawCounts) ? rawCounts : Object.entries(rawCounts).map(([name, count]) => ({ name, count })));
      setQValues(qv);
      setError("");
    } catch (err) {
      if (mountedRef.current) setError(err.message);
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, [apiFetch]);

  useEffect(() => {
    fetchAll(true);
    const id = setInterval(() => fetchAll(false), 5000);
    return () => clearInterval(id);
  }, [fetchAll]);

  /* ── training controls ── */
  const runBatchTraining = useCallback(async () => {
    setTraining(true);
    try {
      await apiFetch("/api/rl/train-batch", {
        method: "POST",
        body: JSON.stringify({ epochs: 100 }),
      });
      await fetchAll(false);
    } catch (err) {
      setError(err.message);
    } finally {
      if (mountedRef.current) setTraining(false);
    }
  }, [apiFetch, fetchAll]);

  const resetAgent = useCallback(async () => {
    const ok = window.confirm(
      "⚠ Reset the RL agent?\n\nThis will clear ALL learned weights, replay buffer, and training history. This action cannot be undone."
    );
    if (!ok) return;
    setResetting(true);
    try {
      await apiFetch("/api/rl/reset", { method: "POST" });
      await fetchAll(true);
    } catch (err) {
      setError(err.message);
    } finally {
      if (mountedRef.current) setResetting(false);
    }
  }, [apiFetch, fetchAll]);

  /* ── derived data ── */
  const epsilon = stats?.epsilon ?? 1;
  const explorationPct = Math.round(epsilon * 100);
  const exploitationPct = 100 - explorationPct;
  const warmup = stats?.warmup_complete === false;
  const bufferSize = stats?.buffer_size ?? stats?.replay_buffer_size ?? 0;
  const warmupTarget = 500;
  const warmupPct = Math.min(100, Math.round((bufferSize / warmupTarget) * 100));

  /* chart data */
  const lossData = useMemo(() =>
    history.filter(h => h && h.loss != null).map((h, i) => ({
      step: h.train_step ?? h.step ?? i,
      loss: h.loss,
    })),
  [history]);

  const rewardData = useMemo(() =>
    history.filter(h => h && (h.avg_reward_last_50 != null || h.reward != null)).map((h, i) => ({
      episode: h.episode ?? i,
      reward: h.avg_reward_last_50 ?? h.reward ?? 0,
    })),
  [history]);

  const epsilonData = useMemo(() =>
    history.filter(h => h && h.epsilon != null).map((h, i) => ({
      step: h.train_step ?? h.step ?? i,
      epsilon: h.epsilon,
    })),
  [history]);

  const qValueStatsData = useMemo(() =>
    history.filter(h => h && h.q_value_mean != null).map((h, i) => ({
      step: h.train_step ?? h.step ?? i,
      mean: h.q_value_mean,
      std: h.q_value_std ?? 0,
      min: (h.q_value_mean ?? 0) - (h.q_value_std ?? 0),
      max: (h.q_value_mean ?? 0) + (h.q_value_std ?? 0),
    })),
  [history]);

  const bufferGrowthData = useMemo(() =>
    history.filter(h => h && h.buffer_size != null).map((h, i) => ({
      step: h.train_step ?? h.step ?? i,
      size: h.buffer_size,
    })),
  [history]);

  const trainingActivity = useMemo(() =>
    history.slice(-20).reverse().map(h => ({
      step: h.train_step ?? 0,
      loss: h.loss,
      epsilon: h.epsilon,
      timestamp: h.timestamp,
      avgReward: h.avg_reward_last_50,
      qMean: h.q_value_mean,
    })),
  [history]);

  /* training throughput */
  const trainingThroughput = useMemo(() => {
    if (history.length < 2) return null;
    const first = history[0];
    const last = history[history.length - 1];
    const steps = (last.train_step ?? 0) - (first.train_step ?? 0);
    if (steps <= 0) return null;
    const t1 = first.timestamp ? new Date(first.timestamp).getTime() : 0;
    const t2 = last.timestamp ? new Date(last.timestamp).getTime() : 0;
    const elapsed = (t2 - t1) / 1000;
    if (elapsed <= 0) return null;
    return (steps / elapsed).toFixed(2);
  }, [history]);

  /* action distribution for pie */
  const pieData = useMemo(() => {
    if (Array.isArray(actionDist) && actionDist.length > 0) {
      return actionDist.map(a => ({
        name: ACTION_LABELS[a.name] || a.name?.replace(/_/g, " ") || "Unknown",
        value: a.count ?? a.value ?? 0,
      }));
    }
    return [];
  }, [actionDist]);

  const pieTotal = useMemo(() => pieData.reduce((s, d) => s + d.value, 0), [pieData]);

  /* Q-values for bar */
  const qBarData = useMemo(() => {
    if (!qValues) return [];
    const vals = qValues.q_values ?? qValues.values ?? qValues;
    if (!vals) return [];
    if (Array.isArray(vals)) {
      const actionNames = ["continue", "reroute_warehouse", "reroute_port", "wait", "defer_dispatch"];
      return vals.map((v, i) => ({
        action: ACTION_LABELS[actionNames[i]] || actionNames[i] || `Action ${i}`,
        value: typeof v === "number" ? v : (v?.value ?? 0),
        isMax: false,
      }));
    }
    if (typeof vals === "object") {
      return Object.entries(vals).map(([k, v]) => ({
        action: ACTION_LABELS[k] || k.replace(/_/g, " "),
        value: typeof v === "number" ? v : 0,
        isMax: false,
      }));
    }
    return [];
  }, [qValues]);

  /* mark the max Q-value */
  const qBarDataWithMax = useMemo(() => {
    if (!qBarData.length) return [];
    const maxVal = Math.max(...qBarData.map(d => d.value));
    return qBarData.map(d => ({ ...d, isMax: d.value === maxVal }));
  }, [qBarData]);

  const stateVector = qValues?.state ?? qValues?.state_vector ?? null;

  /* ── loading state ── */
  if (loading && !stats) {
    return (
      <div className="rl-view">
        <div className="rl-loading-overlay">
          <span className="rl-spinner" style={{ width: 24, height: 24, borderWidth: 3 }} />
          Loading RL Training Data…
        </div>
      </div>
    );
  }

  return (
    <div className="rl-view">
      {error && <div className="banner error" style={{ borderRadius: 10 }}>{error}</div>}

      {/* ═══════════ SECTION 1: STATUS BANNER ═══════════ */}
      <div className="rl-banner">
        <div className="rl-banner-status">
          <span className={`dot ${warmup ? "warmup" : "active"}`} />
          {warmup ? (
            <span>
              RL Agent Warming Up — <strong>{bufferSize}</strong>/{warmupTarget} experiences ({warmupPct}%)
            </span>
          ) : (
            <span>
              RL Agent Active — <strong>{stats?.total_episodes ?? 0}</strong> decisions, <strong>{stats?.total_train_steps ?? stats?.train_step ?? 0}</strong> training steps
            </span>
          )}
        </div>

        {warmup && (
          <div className="rl-warmup-bar">
            <div className="rl-warmup-fill" style={{ width: `${warmupPct}%` }} />
          </div>
        )}

        <div className="rl-stats-row">
          <div className="rl-stat-box">
            <div className="label">Epsilon (ε)</div>
            <div className="value" style={{ color: C.accent }}>{epsilon.toFixed(4)}</div>
          </div>
          <div className="rl-stat-box">
            <div className="label">Buffer Size</div>
            <div className="value" style={{ color: C.blue }}>{bufferSize.toLocaleString()}</div>
          </div>
          <div className="rl-stat-box">
            <div className="label">Train Steps</div>
            <div className="value" style={{ color: C.teal }}>{(stats?.total_train_steps ?? stats?.train_step ?? 0).toLocaleString()}</div>
          </div>
          <div className="rl-stat-box">
            <div className="label">Avg Reward (last 100)</div>
            <div className="value" style={{ color: C.coral }}>{(stats?.avg_reward_last_100 ?? stats?.avg_reward ?? 0).toFixed(3)}</div>
          </div>
        </div>

        {/* exploration / exploitation gauge */}
        <div className="rl-epsilon-gauge">
          <div className="title">Exploration vs Exploitation Balance</div>
          <div className="rl-gauge-track">
            <div className="rl-gauge-exploit" style={{ width: `${exploitationPct}%` }}>
              {exploitationPct > 12 ? `🎯 ${exploitationPct}% Learned` : ""}
            </div>
            <div className="rl-gauge-explore" style={{ width: `${explorationPct}%` }}>
              {explorationPct > 12 ? `🔍 ${explorationPct}% Random` : ""}
            </div>
          </div>
          <div className="rl-gauge-labels">
            <span>🎯 Exploitation ({exploitationPct}%)</span>
            <span>🔍 Exploration ({explorationPct}%)</span>
          </div>
        </div>
      </div>

      {/* ═══════════ SECTION 2: LEARNING CURVES ═══════════ */}
      <div className="rl-section-title">📈 Learning Curves</div>
      <div className="rl-charts-grid">
        {/* Loss Curve */}
        <div className="rl-chart-card">
          <div className="rl-chart-title">
            <span className="dot" style={{ background: C.coral }} />
            Training Loss
          </div>
          {lossData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={lossData}>
                <defs>
                  <linearGradient id="lossGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={C.coral} stopOpacity={0.35} />
                    <stop offset="100%" stopColor={C.coral} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                <XAxis dataKey="step" tick={{ fill: C.muted, fontSize: 11 }} axisLine={{ stroke: C.border }} tickLine={false} />
                <YAxis tick={{ fill: C.muted, fontSize: 11 }} axisLine={{ stroke: C.border }} tickLine={false} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="loss" stroke="none" fill="url(#lossGrad)" />
                <Line type="monotone" dataKey="loss" stroke={C.coral} strokeWidth={2} dot={false} activeDot={{ r: 4, fill: C.coral }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="rl-empty">No loss data yet — training hasn't started</div>
          )}
        </div>

        {/* Reward Curve */}
        <div className="rl-chart-card">
          <div className="rl-chart-title">
            <span className="dot" style={{ background: C.teal }} />
            Average Reward
          </div>
          {rewardData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={rewardData}>
                <defs>
                  <linearGradient id="rewardGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={C.teal} stopOpacity={0.35} />
                    <stop offset="100%" stopColor={C.teal} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                <XAxis dataKey="episode" tick={{ fill: C.muted, fontSize: 11 }} axisLine={{ stroke: C.border }} tickLine={false} />
                <YAxis tick={{ fill: C.muted, fontSize: 11 }} axisLine={{ stroke: C.border }} tickLine={false} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="reward" stroke="none" fill="url(#rewardGrad)" />
                <Line type="monotone" dataKey="reward" stroke={C.teal} strokeWidth={2} dot={false} activeDot={{ r: 4, fill: C.teal }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="rl-empty">No reward data yet</div>
          )}
        </div>

        {/* Epsilon Decay */}
        <div className="rl-chart-card">
          <div className="rl-chart-title">
            <span className="dot" style={{ background: C.accent }} />
            Epsilon Decay
          </div>
          {epsilonData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={epsilonData}>
                <defs>
                  <linearGradient id="epsGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={C.accent} stopOpacity={0.45} />
                    <stop offset="100%" stopColor={C.accent} stopOpacity={0.03} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                <XAxis dataKey="step" tick={{ fill: C.muted, fontSize: 11 }} axisLine={{ stroke: C.border }} tickLine={false} />
                <YAxis domain={[0, 1]} tick={{ fill: C.muted, fontSize: 11 }} axisLine={{ stroke: C.border }} tickLine={false} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="epsilon" stroke={C.accent} strokeWidth={2} fill="url(#epsGrad)" activeDot={{ r: 4, fill: C.accent }} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="rl-empty">No epsilon data yet</div>
          )}
        </div>
      </div>

      {/* ═══════════ SECTION 3: ADVANCED METRICS ═══════════ */}
      {qValueStatsData.length > 0 || bufferGrowthData.length > 0 ? (
        <>
          <div className="rl-section-title">📊 Advanced Training Metrics</div>
          <div className="rl-charts-grid">
            {/* Q-Value Mean ± Std */}
            {qValueStatsData.length > 0 && (
              <div className="rl-chart-card">
                <div className="rl-chart-title">
                  <span className="dot" style={{ background: C.purple }} />
                  Q-Value Confidence (mean ± std)
                </div>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={qValueStatsData}>
                    <defs>
                      <linearGradient id="qBandGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={C.purple} stopOpacity={0.2} />
                        <stop offset="100%" stopColor={C.purple} stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                    <XAxis dataKey="step" tick={{ fill: C.muted, fontSize: 11 }} axisLine={{ stroke: C.border }} tickLine={false} />
                    <YAxis tick={{ fill: C.muted, fontSize: 11 }} axisLine={{ stroke: C.border }} tickLine={false} />
                    <Tooltip content={<ChartTooltip formatter={(v) => v.toFixed(4)} />} />
                    <Area type="monotone" dataKey="max" stroke="none" fill="url(#qBandGrad)" />
                    <Area type="monotone" dataKey="min" stroke="none" fill="url(#qBandGrad)" />
                    <Line type="monotone" dataKey="mean" stroke={C.purple} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                    <Line type="monotone" dataKey="std" stroke={C.purple} strokeWidth={1} strokeDasharray="4 4" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Buffer Size Growth */}
            {bufferGrowthData.length > 0 && (
              <div className="rl-chart-card">
                <div className="rl-chart-title">
                  <span className="dot" style={{ background: C.blue }} />
                  Replay Buffer Growth
                </div>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={bufferGrowthData}>
                    <defs>
                      <linearGradient id="bufGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={C.blue} stopOpacity={0.3} />
                        <stop offset="100%" stopColor={C.blue} stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                    <XAxis dataKey="step" tick={{ fill: C.muted, fontSize: 11 }} axisLine={{ stroke: C.border }} tickLine={false} />
                    <YAxis tick={{ fill: C.muted, fontSize: 11 }} axisLine={{ stroke: C.border }} tickLine={false} />
                    <Tooltip content={<ChartTooltip />} />
                    <Area type="monotone" dataKey="size" stroke={C.blue} strokeWidth={2} fill="url(#bufGrad)" dot={false} activeDot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Throughput Card */}
            <div className="rl-chart-card">
              <div className="rl-chart-title">
                <span className="dot" style={{ background: C.accent }} />
                Training Throughput
              </div>
              <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", height: 220, gap: 8 }}>
                <div style={{ fontSize: "2.2rem", fontWeight: 700, color: C.accent }}>
                  {trainingThroughput ? `${trainingThroughput} step/s` : "—"}
                </div>
                <div style={{ fontSize: ".78rem", color: C.muted }}>
                  Total records: <strong style={{ color: C.text }}>{history.length.toLocaleString()}</strong>
                </div>
                <div style={{ fontSize: ".78rem", color: C.muted }}>
                  Buffer capacity: <strong style={{ color: C.text }}>{(stats?.buffer_capacity ?? 8000).toLocaleString()}</strong>
                </div>
                <div style={{ fontSize: ".78rem", color: C.muted }}>
                  Buffer fill: <strong style={{ color: C.blue }}>{((stats?.buffer_size ?? 0) / (stats?.buffer_capacity ?? 8000) * 100).toFixed(1)}%</strong>
                </div>
                {qValueStatsData.length > 0 && (
                  <div style={{ fontSize: ".78rem", color: C.muted }}>
                    Q-value range: <strong style={{ color: C.purple }}>
                      {qValueStatsData[qValueStatsData.length - 1]?.min.toFixed(2)} – {qValueStatsData[qValueStatsData.length - 1]?.max.toFixed(2)}
                    </strong>
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      ) : null}

      {/* ═══════════ SECTION 4: TRAINING ACTIVITY FEED ═══════════ */}
      {trainingActivity.length > 0 && (
        <>
          <div className="rl-section-title">⚡ Live Training Activity</div>
          <div className="rl-activity-wrap">
            <div className="rl-activity-header">
              <span>Step</span>
              <span>Loss ↓</span>
              <span>Q-Mean</span>
              <span>ε</span>
              <span>Avg Reward</span>
              <span>Time</span>
            </div>
            <div className="rl-activity-body">
              {trainingActivity.map((act, i) => {
                const lossColor = act.loss != null ? (act.loss > 1 ? C.red : act.loss > 0.3 ? C.amber : C.green) : C.muted;
                const rewardColor = act.avgReward != null ? (act.avgReward > 0 ? C.green : C.red) : C.muted;
                return (
                  <div key={i} className="rl-activity-row" style={{ animationDelay: `${i * 30}ms` }}>
                    <span className="rl-activity-step">#{act.step}</span>
                    <span className={act.loss != null ? "" : "rl-na"} style={{ color: lossColor }}>
                      {act.loss != null ? act.loss.toFixed(6) : "—"}
                    </span>
                    <span className={act.qMean != null ? "" : "rl-na"}>
                      {act.qMean != null ? act.qMean.toFixed(4) : "—"}
                    </span>
                    <span style={{ color: act.epsilon != null ? (act.epsilon > 0.5 ? C.amber : C.accent) : C.muted }}>
                      {act.epsilon != null ? act.epsilon.toFixed(4) : "—"}
                    </span>
                    <span style={{ color: rewardColor }}>
                      {act.avgReward != null ? act.avgReward.toFixed(4) : "—"}
                    </span>
                    <span className="rl-na">
                      {act.timestamp ? new Date(act.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—"}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}

      {/* ═══════════ SECTION 5 + 6: DISTRIBUTION + Q-VALUES ═══════════ */}
      <div className="rl-insights-grid">
        {/* Action Distribution */}
        <div className="rl-dist-card">
          <div className="rl-section-title">🎯 Action Distribution</div>
          <div className="rl-dist-inner">
            {pieData.length > 0 ? (
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={90}
                    paddingAngle={3}
                    dataKey="value"
                    animationBegin={0}
                    animationDuration={800}
                  >
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={ACTION_COLORS[i % ACTION_COLORS.length]} stroke={C.panel} strokeWidth={2} />
                    ))}
                  </Pie>
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const d = payload[0];
                      return (
                        <div className="rl-tooltip">
                          <div className="label">{d.name}</div>
                          <div className="value">{d.value} ({pieTotal > 0 ? ((d.value / pieTotal) * 100).toFixed(1) : 0}%)</div>
                        </div>
                      );
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="rl-empty">No action data</div>
            )}
            <div>
              <table className="rl-exp-table">
                <thead>
                  <tr><th>Action</th><th>Count</th><th>%</th></tr>
                </thead>
                <tbody>
                  {pieData.map((d, i) => (
                    <tr key={i}>
                      <td style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{ width: 10, height: 10, borderRadius: "50%", background: ACTION_COLORS[i % ACTION_COLORS.length], flexShrink: 0 }} />
                        {d.name}
                      </td>
                      <td>{d.value}</td>
                      <td>{pieTotal > 0 ? ((d.value / pieTotal) * 100).toFixed(1) : 0}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {stats && (
                <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
                  <span className="chosen-badge chosen-exploitation">
                    🎯 Exploitation {exploitationPct}%
                  </span>
                  <span className="chosen-badge chosen-exploration">
                    🔍 Exploration {explorationPct}%
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Q-Value Insights */}
        <div className="rl-qval-card">
          <div className="rl-section-title">🧪 Q-Value Snapshot</div>
          {qBarDataWithMax.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={qBarDataWithMax} barCategoryGap="18%">
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis dataKey="action" tick={{ fill: C.muted, fontSize: 10 }} axisLine={{ stroke: C.border }} tickLine={false} angle={-15} textAnchor="end" height={50} />
                  <YAxis tick={{ fill: C.muted, fontSize: 11 }} axisLine={{ stroke: C.border }} tickLine={false} />
                  <Tooltip content={<ChartTooltip formatter={(v) => v.toFixed(4)} />} />
                  <Bar dataKey="value" radius={[6, 6, 0, 0]} animationDuration={700}>
                    {qBarDataWithMax.map((d, i) => (
                      <Cell
                        key={i}
                        fill={d.isMax ? C.accent : ACTION_COLORS[i % ACTION_COLORS.length]}
                        className={d.isMax ? "rl-qbar-max" : ""}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              {stateVector && (
                <div style={{ marginTop: 10, fontSize: ".75rem", color: C.muted }}>
                  <strong>State vector:</strong>{" "}
                  [{Array.isArray(stateVector) ? stateVector.map(v => typeof v === "number" ? v.toFixed(2) : v).join(", ") : JSON.stringify(stateVector)}]
                </div>
              )}
              <div style={{ marginTop: 6, fontSize: ".75rem", color: C.accent }}>
                ★ Highlighted bar = agent's preferred action (max Q-value)
              </div>
            </>
          ) : (
            <div className="rl-empty">No Q-value data — agent needs more training</div>
          )}
        </div>
      </div>

      {/* ═══════════ SECTION 7: RECENT EPISODES ═══════════ */}
      <div className="rl-section-title">📋 Recent Episodes</div>
      <div className="rl-episodes-wrap">
        {episodes.length > 0 ? (
          <table className="rl-ep-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Vehicle</th>
                <th>Action</th>
                <th>Reward</th>
                <th>Chosen By</th>
                <th>SLA Met</th>
              </tr>
            </thead>
            <tbody>
              {episodes.slice(0, 20).map((ep, i) => {
                const reward = ep.reward ?? 0;
                const rowClass = reward > 0 ? "row-positive" : reward < 0 ? "row-negative" : "row-neutral";
                const chosenBy = ep.chosen_by ?? ep.selection_method ?? "exploitation";
                const chosenClass = `chosen-${chosenBy.replace(/_/g, "-")}`;
                const timeStr = ep.timestamp ?? ep.time ?? ep.created_at ?? "";
                const fmtTime = timeStr ? new Date(timeStr.endsWith("Z") ? timeStr : timeStr + "Z").toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "--:--";
                return (
                  <tr key={i} className={rowClass}>
                    <td>{fmtTime}</td>
                    <td>{ep.vehicle_id ?? ep.vehicle ?? `V-${i}`}</td>
                    <td style={{ fontWeight: 500 }}>{ACTION_LABELS[ep.action] ?? ep.action?.replace(/_/g, " ") ?? "—"}</td>
                    <td style={{ color: reward > 0 ? C.green : reward < 0 ? C.red : C.muted, fontWeight: 700 }}>
                      {reward > 0 ? "+" : ""}{reward.toFixed(3)}
                    </td>
                    <td>
                      <span className={`chosen-badge ${chosenClass}`}>
                        {chosenBy === "exploitation" ? "🎯" : chosenBy === "exploration" ? "🔍" : "📏"}{" "}
                        {chosenBy.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className={ep.sla_met || ep.sla_met === undefined ? "sla-met" : "sla-missed"}>
                      {ep.sla_met === undefined ? "—" : ep.sla_met ? "✓ Yes" : "✗ No"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <div className="rl-empty">No episodes recorded yet — start the simulation to see RL decisions</div>
        )}
      </div>

      {/* ═══════════ SECTION 8: TRAINING CONTROLS ═══════════ */}
      <div className="rl-section-title">🎮 Training Controls</div>
      <div className="rl-controls">
        <button className="rl-btn rl-btn-primary" onClick={runBatchTraining} disabled={training}>
          {training && <span className="rl-spinner" />}
          {training ? "Training (100 epochs)…" : "Run Batch Training (100 epochs)"}
        </button>
        <button className="rl-btn rl-btn-danger" onClick={resetAgent} disabled={resetting || training}>
          {resetting && <span className="rl-spinner" />}
          {resetting ? "Resetting…" : "⚠ Reset Agent"}
        </button>
        {training && (
          <span style={{ color: C.muted, fontSize: ".82rem", marginLeft: 8 }}>
            Training in progress — dashboard will auto-refresh when complete
          </span>
        )}
      </div>
    </div>
  );
}
