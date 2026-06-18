import { useState, useEffect, useCallback, useMemo, useRef, startTransition, useDeferredValue, lazy, Suspense } from "react";

import { AIRerouteToast } from "./common/AIDecisionWidgets";
import { ErrorBoundary } from "./common/ErrorBoundary";
import { AIChatPanel } from "./common/AIChatPanel";  // Phase 5.1 — SSE chat enabled
import { 
  LayoutDashboard, Map, Activity, 
  TrendingUp, Box, Clapperboard, 
  BrainCircuit, Search, LineChart, 
  Network, Target, Radio, 
  Globe2, Settings, Plug 
} from "lucide-react";

const DashboardView = lazy(() => import("./views/DashboardView").then(m => ({ default: m.DashboardView })));
const MapView = lazy(() => import("./views/MapView").then(m => ({ default: m.MapView })));
const LiveOpsView = lazy(() => import("./views/LiveOpsView").then(m => ({ default: m.LiveOpsView })));
import { ForecastView } from "./views/ForecastView";
import { InventoryView } from "./views/InventoryView";
import { ScenariosView } from "./views/ScenariosView";
const CloudView = lazy(() => import("./views/CloudView").then(m => ({ default: m.CloudView })));
const NetworkView = lazy(() => import("./views/NetworkView").then(m => ({ default: m.NetworkView })));
const ObjectivesView = lazy(() => import("./views/ObjectivesView").then(m => ({ default: m.ObjectivesView })));
const EventsView = lazy(() => import("./views/EventsView").then(m => ({ default: m.EventsView })));
const ImpactView = lazy(() => import("./views/ImpactView").then(m => ({ default: m.ImpactView })));
const SettingsView = lazy(() => import("./views/SettingsView").then(m => ({ default: m.SettingsView })));
const RLTrainingView = lazy(() => import("./views/RLTrainingView").then(m => ({ default: m.RLTrainingView })));
const AIExplainerView = lazy(() => import("./views/AIExplainerView").then(m => ({ default: m.AIExplainerView })));
const ComparisonView = lazy(() => import("./views/ComparisonView").then(m => ({ default: m.ComparisonView })));
const IntegrationView = lazy(() => import("./views/IntegrationView").then(m => ({ default: m.IntegrationView })));

const TRANSLATIONS = {
  en: {
    operations: "Operations",
    intelligence: "Intelligence",
    aiIntelligence: "AI Intelligence",
    network: "Network",
    analytics: "Analytics",
    settings: "Settings",
    dashboard: "Dashboard",
    liveMap: "Live Map",
    liveOps: "Live Ops",
    forecast: "Risk Forecast",
    inventory: "Inventory AI",
    scenarios: "Scenarios",
    blockchain: "Blockchain",
    networkView: "Network",
    objectives: "Objectives",
    events: "Events",
    impact: "Impact & SDG",
    cloud: "Cloud",
    rlTraining: "RL Training",
    aiExplainer: "AI Decisions",
    aiComparison: "AI vs Baseline",
    developer: "Developer",
    developerApiKey: "API Key",
    developerWebhooks: "Webhooks",
    developerLogs: "Delivery Log",
    logisightApi: "Logisight Integration API",
    apiKeyDescription: "Use this API key to authenticate requests to the Logisight Integration API.",
    regenerateKey: "Regenerate Key",
    keyRegenerated: "New API key generated. Save it now — it will not be shown again.",
    copyKey: "Copy",
    keyCopied: "Copied!",
    noWebhooks: "No webhooks configured.",
    createWebhook: "Create Webhook",
    webhookUrl: "Payload URL",
    webhookEvents: "Events",
    webhookActive: "Active",
    deleteWebhook: "Delete",
    commandCenter: "Command Center",
    prototypeBadge: "Supply Chain Digital Twin",
    simTime: "Sim Time",
    speed: "Speed",
    localTime: "Local Time",
    active: "Active",
    onTime: "On-Time",
    co2Saved: "CO₂ Saved",
    start: "Start",
    pause: "Pause",
    resume: "Resume",
    reset: "Reset",
    language: "Language",
    english: "English",
    hindi: "Hindi",
    version: "Logisight V2",
    welcome: "Welcome to Logisight",
    loginTagline: "Intelligent Essential Goods Logistics",
    signInWithGoogle: "Sign in with Google",
    logout: "Logout",
  },
  hi: {
    operations: "संचालन",
    intelligence: "खुफिया",
    aiIntelligence: "AI खुफिया",
    network: "नेटवर्क",
    analytics: "विश्लेषण",
    settings: "सेटिंग्स",
    dashboard: "डैशबोर्ड",
    liveMap: "लाइव मानचित्र",
    liveOps: "लाइव संचालन",
    forecast: "जोखिम पूर्वानुमान",
    inventory: "इन्वेंटरी AI",
    scenarios: "परिदृश्य",
    blockchain: "ब्लॉकचेन",
    networkView: "नेटवर्क",
    objectives: "उद्देश्य",
    events: "घटनाएँ",
    impact: "प्रभाव और SDG",
    cloud: "क्लाउड",
    rlTraining: "RL प्रशिक्षण",
    aiExplainer: "AI निर्णय",
    aiComparison: "AI बनाम आधारभूत",
    developer: "डेवलपर",
    developerApiKey: "API कुंजी",
    developerWebhooks: "वेबहुक",
    developerLogs: "डिलीवरी लॉग",
    logisightApi: "Logisight इंटीग्रेशन API",
    apiKeyDescription: "Logisight इंटीग्रेशन API को प्रमाणित करने के लिए इस API कुंजी का उपयोग करें।",
    regenerateKey: "कुंजी पुनर्जीवित करें",
    keyRegenerated: "नई API कुंजी बनाई गई। अब इसे सहेजें — यह दोबारा नहीं दिखाई जाएगी।",
    copyKey: "कॉपी करें",
    keyCopied: "कॉपी हुआ!",
    noWebhooks: "कोई वेबहुक कॉन्फ़िगर नहीं।",
    createWebhook: "वेबहुक बनाएं",
    webhookUrl: "पेलोड URL",
    webhookEvents: "ईवेंट",
    webhookActive: "सक्रिय",
    deleteWebhook: "हटाएं",
    commandCenter: "कमांड केंद्र",
    prototypeBadge: "आपूर्ति श्रृंखला डिजिटल ट्विन",
    simTime: "सिम समय",
    speed: "गति",
    localTime: "स्थानीय समय",
    active: "सक्रिय",
    onTime: "समय पर",
    co2Saved: "CO₂ बचत",
    start: "प्रारंभ",
    pause: "रोकें",
    resume: "फिर से शुरू",
    reset: "रीसेट",
    language: "भाषा",
    english: "अंग्रेज़ी",
    hindi: "हिंदी",
    version: "Logisight V2",
    welcome: "Logisight में आपका स्वागत है",
    loginTagline: "बुद्धिमान आवश्यक वस्तु लॉजिस्टिक्स",
    signInWithGoogle: "Google से साइन इन करें",
    logout: "लॉग आउट",
  },
};

function useLanguage() {
  const [lang, setLang] = useState(() => localStorage.getItem("logisight-lang") || "en");
  const t = TRANSLATIONS[lang] || TRANSLATIONS.en;
  const switchLang = (next) => {
    setLang(next);
    localStorage.setItem("logisight-lang", next);
  };
  return { lang, t, switchLang };
}

function getNavSections(t, clientContext) {
  const sections = [
    {
      label: t.operations,
      items: [
        { key: "dashboard", label: t.dashboard, icon: <LayoutDashboard size={20} /> },
        { key: "map", label: t.liveMap, icon: <Map size={20} /> },
        { key: "liveOps", label: t.liveOps, icon: <Activity size={20} /> },
      ],
    },
    {
      label: t.intelligence,
      items: [
        { key: "forecast", label: t.forecast, icon: <TrendingUp size={20} /> },
        { key: "inventory", label: t.inventory, icon: <Box size={20} /> },
        { key: "scenarios", label: t.scenarios, icon: <Clapperboard size={20} /> },  {/* disabled Phase 5.1 */}
      ],
    },
    {
      label: t.aiIntelligence,
      items: [
        { key: "rlTraining", label: t.rlTraining, icon: <BrainCircuit size={20} /> },
        { key: "aiExplainer", label: t.aiExplainer, icon: <Search size={20} /> },
        { key: "aiComparison", label: t.aiComparison, icon: <LineChart size={20} /> },
      ],
    },
    {
      label: t.network,
      items: [
        { key: "network", label: t.networkView, icon: <Network size={20} /> },
        { key: "objectives", label: t.objectives, icon: <Target size={20} /> },
        { key: "events", label: t.events, icon: <Radio size={20} /> },
      ],
    },
    {
      label: t.analytics,
      items: [
        { key: "impact", label: t.impact, icon: <Globe2 size={20} /> },
      ],
    },
    {
      label: t.settings,
      items: [
        { key: "settings", label: t.settings, icon: <Settings size={20} /> },
        { key: "developer", label: t.developer, icon: <Plug size={20} /> },
      ],
    },
  ];

  // Phase 5.1: hide items with placeholder/coming-soon views
  const hiddenKeys = ["cloud", "aiComparison"];
  
  if (clientContext) {
    return sections
      .filter(s => s.label !== t.intelligence && s.label !== t.aiIntelligence)
      .map(s =>
        s.label === t.settings
          ? { ...s, items: s.items.filter(i => i.key !== "developer") }
          : s
      );
  }
  return sections.map(s => ({ ...s, items: s.items.filter(i => !hiddenKeys.includes(i.key)) }));
}

function Sidebar({ active, onNavigate, collapsed, onMouseEnter, onMouseLeave, t, clientContext }) {
  const sections = getNavSections(t, clientContext);
  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : "open"}`} onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave}>
      <div className="sidebar-header">
        <div className="logo-mark">L</div>
        {!collapsed && <span className="logo-text">Logisight</span>}
      </div>
      <nav className="sidebar-nav">
        {sections.map((section) => (
          <div key={section.label} className="nav-section">
            {!collapsed && <div className="nav-section-label">{section.label}</div>}
            {section.items.map((item) => (
              <button
                key={item.key}
                className={`nav-item ${active === item.key ? "active" : ""}`}
                onClick={() => onNavigate(item.key)}
                title={collapsed ? item.label : undefined}
              >
                <span className="nav-icon">{item.icon}</span>
                {!collapsed && <span className="nav-label">{item.label}</span>}
              </button>
            ))}
          </div>
        ))}
      </nav>
      <div className="sidebar-footer">
        {!collapsed && <div className="version">{t.version}</div>}
      </div>
    </aside>
  );
}

function StatusBar({ dashboard, metrics, t, clientContext }) {
  const sim = dashboard?.simulation;
  const [localTime, setLocalTime] = useState(new Date());
  const [displayTime, setDisplayTime] = useState(sim?.simulation_time);
  const speedRef = useRef(sim?.speed_multiplier ?? 1);

  useEffect(() => {
    speedRef.current = sim?.speed_multiplier ?? 1;
  }, [sim?.speed_multiplier]);

  useEffect(() => {
    setDisplayTime(sim?.simulation_time);
  }, [sim?.simulation_time]);

  useEffect(() => {
    if (clientContext) {
      const interval = setInterval(() => setLocalTime(new Date()), 1000);
      return () => clearInterval(interval);
    }
  }, [clientContext]);

  useEffect(() => {
    if (clientContext) return;
    if (sim?.status !== "running" || !sim?.simulation_time || !sim?.speed_multiplier) return;

    let lastTick = Date.now();
    const interval = setInterval(() => {
      const now = Date.now();
      const dtSec = (now - lastTick) / 1000;
      lastTick = now;

      setDisplayTime(prev => {
        if (!prev) return prev;
        const d = new Date(prev.endsWith("Z") ? prev : prev + "Z");
        if (isNaN(d.getTime())) return prev;
        d.setMilliseconds(d.getMilliseconds() + dtSec * speedRef.current * 1000);
        return d.toISOString().replace("Z", "");
      });
    }, 100);

    return () => clearInterval(interval);
  }, [clientContext, sim?.status, sim?.simulation_time, sim?.speed_multiplier]);

  return (
    <div className="status-bar">
      {clientContext ? (
        <>
          <div className="status-pill-group">
            <span className="status-dot live" />
            <span className="status-text">Live</span>
          </div>
          <div className="status-pill-group">
            <span className="status-label">{t.localTime}</span>
            <span className="status-value">{localTime.toLocaleTimeString()}</span>
          </div>
        </>
      ) : (
        <>
          <div className="status-pill-group">
            <span className={`status-dot ${sim?.status === "running" ? "live" : ""}`} />
            <span className="status-text">{sim?.status ?? "idle"}</span>
          </div>
          <div className="status-pill-group">
            <span className="status-label">{t.simTime}</span>
            <span className="status-value">{displayTime?.slice(0, 19).replace("T", " ") ?? "--"}</span>
          </div>
          <div className="status-pill-group">
            <span className="status-label">{t.speed}</span>
            <span className="status-value">{sim?.speed_multiplier ?? 0}x{(sim?.speed_multiplier ?? 0) >= 5000 ? <span className="turbo-badge"> TURBO</span> : ""}</span>
          </div>
        </>
      )}
      <div className="status-pill-group">
        <span className="status-label">{t.active}</span>
        <span className="status-value">{metrics?.active_trucks ?? 0} trucks</span>
      </div>
      <div className="status-pill-group">
        <span className="status-label">{t.onTime}</span>
        <span className="status-value">{metrics?.on_time_delivery_pct ?? 0}%</span>
      </div>
      <div className="status-pill-group">
        <span className="status-label">{t.co2Saved}</span>
        <span className="status-value">{(metrics?.co2_saved_kg ?? 0).toFixed(1)} kg</span>
      </div>
    </div>
  );
}

function SimControls({ onAction, onSetSpeed, currentSpeed, t }) {
  const options = [120, 180, 500, 1000, 5000, 50000, 100000];
  return (
    <div className="sim-controls">
      <button className="sim-btn primary" onClick={() => onAction("/api/simulation/start", { speed_multiplier: 180 }, t.start)}>{t.start}</button>
      <button className="sim-btn" onClick={() => onAction("/api/simulation/pause", {}, t.pause)}>{t.pause}</button>
      <button className="sim-btn" onClick={() => onAction("/api/simulation/resume", {}, t.resume)}>{t.resume}</button>
      <button className="sim-btn danger" onClick={() => onAction("/api/simulation/reset", {}, t.reset)}>{t.reset}</button>
      <select className="speed-select" value={currentSpeed >= options[options.length-1] ? options[options.length-1] : currentSpeed} onChange={e => onSetSpeed(Number(e.target.value))}>
        {options.map(s => <option key={s} value={s}>{s}x</option>)}
      </select>
    </div>
  );
}

function useVoiceInput() {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const recognitionRef = useRef(null);

  const start = useCallback((lang = "en-IN") => {
    if (!("webkitSpeechRecognition" in window || "SpeechRecognition" in window)) return;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new SR();
    rec.lang = lang;
    rec.continuous = false;
    rec.interimResults = false;
    rec.onresult = (e) => {
      const text = e.results[0][0].transcript;
      setTranscript(text);
      setIsListening(false);
    };
    rec.onerror = () => setIsListening(false);
    rec.onend = () => setIsListening(false);
    recognitionRef.current = rec;
    try { rec.start(); } catch { setIsListening(false); return; }
    setIsListening(true);
  }, []);

  return { isListening, transcript, start, reset: () => setTranscript("") };
}

export function formatINRCompact(value) {
  const amount = Number(value || 0);
  if (Math.abs(amount) >= 100000) return `₹${(amount / 100000).toFixed(1)}L`;
  if (Math.abs(amount) >= 1000) return `₹${Math.round(amount / 1000)}K`;
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(amount);
}

export function formatDurationFromMinutes(minutes, fallbackHours = 36) {
  const value = Number(minutes);
  const hours = Number.isFinite(value) && value > 0 ? value / 60 : fallbackHours;
  return `${hours.toFixed(hours >= 10 ? 0 : 1)}h`;
}

export function decisionVerb(action = "") {
  const normalized = String(action || "continue").replaceAll("_", " ");
  if (normalized.includes("reroute")) return "Rerouted";
  if (normalized.includes("wait")) return "Held";
  if (normalized.includes("defer")) return "Deferred";
  return "Optimized";
}

export function actionDetail(action = "", explanation = "") {
  const text = String(explanation || "").toLowerCase();
  if (text.includes("port")) return "avoided port delay";
  if (text.includes("risk")) return "reduced route risk";
  if (String(action).includes("rail")) return "switched to rail route for cost efficiency";
  if (String(action).includes("reroute")) return "selected a safer fallback route";
  return "updated route recommendation";
}

export function recommendationTime(rec) {
  const raw = rec?.created_at || rec?.simulation_time;
  const date = raw ? new Date(String(raw).endsWith("Z") ? raw : `${raw}Z`) : new Date();
  if (Number.isNaN(date.getTime())) return "--:--";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function buildDecisionFromRecommendation(rec, metrics) {
  if (!rec) return {
    id: "mock-decision",
    title: "Rerouted Shipment SHP-001",
    reason: "avoided port congestion",
    impact: ["₹35K cost saved", "delay risk avoided"],
    confidence: 92,
    comparison: {
      before: { label: "Route A", cost: "₹1.2L", time: "36h" },
      after: { label: "Route B", cost: "₹85K", time: "30h" },
      decision: "Chosen to minimize cost and avoid delay risk"
    }
  };

  const shipmentRef = `SHP-${String(rec.id ?? 1).padStart(3, "0")}`;
  const costSaved = Number(rec.financial_impact_usd ?? 0) || Math.max(0, Number(rec.baseline_cost ?? 0) - Number(rec.recommended_cost ?? 0));
  const addedTravel = Number(rec.score_breakdown?.added_travel_minutes ?? 0);
  const baselineMinutes = Number(rec.score_breakdown?.baseline_duration_minutes ?? 0);
  const recommendedMinutes = baselineMinutes > 0 ? Math.max(1, baselineMinutes + addedTravel) : 0;
  const timeSaved = baselineMinutes > 0 ? Math.max(0, baselineMinutes - recommendedMinutes) : null;
  const confidence = rec.confidence != null ? Math.round(Number(rec.confidence) * 100) : 90;

  const hasComparison = Number(rec.baseline_cost ?? 0) > 0 || Number(rec.recommended_cost ?? 0) > 0;
  const hasTimeData = baselineMinutes > 0;

  return {
    id: rec.id,
    title: `${decisionVerb(rec.action)} Shipment ${shipmentRef}`,
    reason: rec.explanation || null,
    impact: [
      `${formatINRCompact(costSaved)} cost saved`,
      ...(timeSaved !== null && timeSaved > 0 ? [`${formatDurationFromMinutes(timeSaved, 6)} faster delivery`] : []),
      ...(timeSaved !== null && timeSaved === 0 ? ["delay risk avoided"] : []),
    ],
    confidence,
    comparison: hasComparison || hasTimeData ? {
      before: {
        label: "Route A",
        cost: hasComparison ? formatINRCompact(rec.baseline_cost ?? 0) : formatDurationFromMinutes(baselineMinutes, 36),
        time: hasTimeData ? formatDurationFromMinutes(baselineMinutes, 36) : null,
      },
      after: {
        label: "Route B",
        cost: hasComparison ? formatINRCompact(rec.recommended_cost ?? 0) : formatDurationFromMinutes(recommendedMinutes, 30),
        time: hasTimeData ? formatDurationFromMinutes(recommendedMinutes, 30) : null,
      },
      decision: rec.action?.includes("reroute")
        ? "Chosen to minimize cost and avoid delay risk"
        : "Chosen as the lowest-risk feasible option",
    } : null,
  };
}

export function buildActivityFeed(recommendations, _aiActivity) {
  const fromRecommendations = (recommendations || []).slice(0, 15).map((rec) => ({
    id: `rec-${rec.id}`,
    time: recommendationTime(rec),
    title: `${decisionVerb(rec.action)} SHP-${String(rec.id ?? 0).padStart(3, "0")}`,
    detail: actionDetail(rec.action, rec.explanation),
  }));

  return fromRecommendations;
}

export default function DashboardShell({ user, onLogout, clientContext }) {
  const { lang, t, switchLang } = useLanguage();
  const API_BASE = import.meta.env.VITE_API_BASE ?? import.meta.env.VITE_API_BASE_URL ?? "";

  const apiCache = useRef({});

  const apiFetch = useCallback(async (path, options = {}) => {
    const { headers: optHeaders, ...rest } = options;
    const isGet = !rest.method || rest.method === "GET";
    
    if (isGet) {
      const cached = apiCache.current[path];
      if (cached && (Date.now() - cached.timestamp < 15000)) {
        return cached.data;
      }
    }
    const authHeaders = {};
    if (clientContext?.apiKey) {
      authHeaders["X-API-Key"] = clientContext.apiKey;
    } else if (clientContext?.firebaseToken) {
      authHeaders["Authorization"] = `Bearer ${clientContext.firebaseToken}`;
    }
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...authHeaders, ...(optHeaders ?? {}) },
      ...rest,
    });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `Request failed: ${response.status}`);
    }
    if (response.status === 204) return null;
    const data = await response.json();
    if (isGet) {
      apiCache.current[path] = { timestamp: Date.now(), data };
    }
    return data;
  }, [API_BASE, clientContext]);

  const [activeView, setActiveView] = useState("dashboard");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const [dashboard, setDashboard] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [facilities, setFacilities] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [objectives, setObjectives] = useState([]);
  const [routes, setRoutes] = useState([]);
  const [scenarios, setScenarios] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [events, setEvents] = useState([]);
  const [riskForecast, setRiskForecast] = useState([]);
  const [inventoryForecast, setInventoryForecast] = useState([]);
  const [proactiveDispatches, setProactiveDispatches] = useState([]);
  const [cloudHealth, setCloudHealth] = useState(null);
  const [voiceConfig, setVoiceConfig] = useState(null);
  const [aiActivity, setAiActivity] = useState(null);
  const [latestDecision, setLatestDecision] = useState(null);
  const [previousRoute, setPreviousRoute] = useState(null);
  const [activityFeed, setActivityFeed] = useState([]);
  const [toasts, setToasts] = useState([]);
  const seenDecisionIds = useRef(new Set());
  const [scenarioKey, setScenarioKey] = useState("");
  const [scenarioComparison, setScenarioComparison] = useState(null);
  const [scalingFleet, setScalingFleet] = useState(false); // unused — scale-fleet removed per RULES.md Rule 4
  const [voiceIncidentType, setVoiceIncidentType] = useState("road_blockage");
  const [voiceNote, setVoiceNote] = useState("");

  const deferredVehicles = useDeferredValue(dashboard?.vehicles ?? []);
  const voice = useVoiceInput();

  const refreshAll = useCallback(async (showSpinner = false) => {
    if (showSpinner) setLoading(true);
    try {
      if (clientContext) {
        console.log("[RC5-DIAG] refreshAll: CLIENT MODE, clientId=", clientContext.clientId, "endpoints=/api/v1/client/*");
        const [d, f, v, o, r, rec, e] = await Promise.all([
          apiFetch("/api/v1/client/dashboard"),
          apiFetch("/api/v1/client/facilities"),
          apiFetch("/api/v1/client/vehicles"),
          apiFetch("/api/v1/client/objectives"),
          apiFetch("/api/v1/client/routes"),
          apiFetch("/api/v1/client/recommendations"),
          apiFetch("/api/v1/client/events?relevant_only=true"),
        ]);
        startTransition(() => {
          setDashboard(prev => ({ ...d, simulation: d.simulation || prev?.simulation }));
          setFacilities(f);
          setVehicles(v);
          setObjectives(o);
          setRoutes(r);
          setRecommendations(rec);
          setEvents(e);
          setMetrics(d.metrics);
          setError("");
        });
      } else {
        console.log("[RC5-DIAG] refreshAll: DEMO MODE, endpoints=/api/* (global)");
        const [
          d, f, v, dr, o, r, s, rec, m, e, rf, inv, pd, ai
        ] = await Promise.all([
          apiFetch("/api/dashboard"),
          apiFetch("/api/facilities"),
          apiFetch("/api/vehicles"),
          apiFetch("/api/drivers"),
          apiFetch("/api/objectives"),
          apiFetch("/api/routes"),
          apiFetch("/api/scenarios"),
          apiFetch("/api/recommendations"),
          apiFetch("/api/metrics/sdg"),
          apiFetch("/api/events/news?relevant_only=true"),
          apiFetch("/api/forecast/risk?hours=12").catch(() => []),
          apiFetch("/api/inventory/forecasts").catch(() => []),
          apiFetch("/api/inventory/proactive-dispatches").catch(() => []),
          apiFetch("/api/metrics/ai-activity").catch(() => null),
        ]);
        startTransition(() => {
          setDashboard(d);
          setFacilities(f);
          setVehicles(v);
          setDrivers(dr);
          setObjectives(o);
          setRoutes(r);
          setScenarios(s);
          setRecommendations(rec);
          setMetrics(m);
          setEvents(e);
          setRiskForecast(rf);
          setInventoryForecast(inv);
          setProactiveDispatches(pd);
          setAiActivity(ai);
          setError("");
        });
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [clientContext]);

  useEffect(() => {
    refreshAll(true);
    const id = setInterval(() => refreshAll(false), 30000);
    return () => clearInterval(id);
  }, [refreshAll]);

  useEffect(() => {
    if (voice.transcript) {
      const text = voice.transcript.toLowerCase();
      const matched = voiceConfig?.incident_types?.find((t) => text.includes(t.label.toLowerCase()) || text.includes(t.key.toLowerCase()));
      if (matched) setVoiceIncidentType(matched.key);
    }
  }, [voice.transcript, voiceConfig]);

  const [wsConnected, setWsConnected] = useState(false);

  useEffect(() => {
    let socket;
    let pingTimer;
    let reconnectTimer;

    function connectWs() {
      const wsBase = import.meta.env.VITE_WS_BASE_URL ||
        `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}`;

      const wsPath = clientContext
        ? `/ws/client?token=${encodeURIComponent(clientContext.firebaseToken || clientContext.apiKey)}`
        : "/ws/operations";

      console.log("[RC5-DIAG] WebSocket: clientContext=",
        clientContext ? `SET(clientId=${clientContext.clientId})` : "NULL",
        "→ wsPath=", wsPath);

      socket = new WebSocket(`${wsBase}${wsPath}`);

      socket.onopen = () => {
        setWsConnected(true);
        pingTimer = setInterval(() => { if (socket.readyState === WebSocket.OPEN) socket.send("ping"); }, 15000);
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === "simulation_snapshot") {
            startTransition(() => {
              setDashboard(prev => clientContext && prev ? { ...prev, simulation: payload.payload.simulation, metrics: payload.payload.metrics, vehicles: payload.payload.vehicles } : payload.payload);
              setMetrics(payload.payload.metrics);
              if (clientContext) {
                if (payload.payload.objectives) setObjectives(payload.payload.objectives);
                if (payload.payload.route_templates) setRoutes(payload.payload.route_templates);
              }
            });
          }
        } catch {}
      };

      socket.onclose = () => {
        setWsConnected(false);
        clearInterval(pingTimer);
        reconnectTimer = setTimeout(connectWs, 3000);
      };

      socket.onerror = () => {
        socket.close();
      };
    }

    connectWs();

    return () => {
      clearInterval(pingTimer);
      clearTimeout(reconnectTimer);
      if (socket) socket.close();
    };
  }, [clientContext]);

  const runAction = useCallback(async (path, body = null, msg = "") => {
    try {
      await apiFetch(path, { method: "POST", body: JSON.stringify(body ?? {}) });
      if (msg) {
        setMessage(msg);
        setError("");
        setTimeout(() => setMessage(""), 3000);
      }
      await refreshAll(false);
    } catch (err) { setError(err.message); }
  }, [refreshAll]);

  const handleSetSpeed = useCallback(async (speed) => {
    const clamped = Math.max(1, Math.min(100000, speed));
    try {
      const endpoint = clientContext ? "/api/v1/client/speed" : "/api/simulation/speed";
      await apiFetch(endpoint, { method: "PUT", body: JSON.stringify({ speed_multiplier: clamped }) });
    } catch (err) { setError(err.message); }
  }, [clientContext]);

  const currentSpeed = dashboard?.simulation?.speed_multiplier ?? 120;

  const facilityLookup = Object.fromEntries(facilities.map((f) => [f.id, f]));
  const objectiveLookup = Object.fromEntries(objectives.map((o) => [o.id, o]));
  const criticalFacilities = (dashboard?.facilities ?? []).filter((f) => f.utilization_pct >= 70).slice(0, 6);
  const derivedDecision = useMemo(
    () => buildDecisionFromRecommendation(recommendations?.[0], metrics),
    [recommendations, metrics]
  );
  const derivedActivityFeed = useMemo(
    () => buildActivityFeed(recommendations, aiActivity),
    [recommendations, aiActivity]
  );

  useEffect(() => {
    if (!derivedDecision) return;
    const id = String(derivedDecision.id ?? derivedDecision.title ?? "");
    if (id) seenDecisionIds.current.add(id);
    setLatestDecision(derivedDecision);
    setPreviousRoute(derivedDecision?.comparison?.before ?? null);
  }, [derivedDecision]);

  useEffect(() => {
    setActivityFeed(derivedActivityFeed.slice(0, 20));
  }, [derivedActivityFeed]);

  const dismissToast = useCallback((toastId) => {
    setToasts((prev) => prev.filter((t) => t.id !== toastId));
  }, []);

  const renderView = () => {
    switch (activeView) {
      case "dashboard":
        return <DashboardView metrics={metrics} criticalFacilities={criticalFacilities} proactiveDispatches={proactiveDispatches} riskForecast={riskForecast} facilityLookup={facilityLookup} aiActivity={aiActivity} latestDecision={latestDecision} previousRoute={previousRoute} activityFeed={activityFeed} />;
      case "map":
        return <MapView facilities={facilities} vehicles={dashboard?.vehicles ?? []} objectives={objectives} recommendations={recommendations} activeEvents={dashboard?.active_events ?? []} routeTemplates={routes} riskForecast={riskForecast} vehicleCount={dashboard?.vehicles?.length ?? vehicles.length} onScaleFleet={undefined} isScalingFleet={false} />;
      case "liveOps":
        return <LiveOpsView metrics={metrics} deferredVehicles={deferredVehicles} objectiveLookup={objectiveLookup} />;
      case "forecast":
        return <ForecastView riskForecast={riskForecast} />;
      case "inventory":
        return <InventoryView inventoryForecast={inventoryForecast} proactiveDispatches={proactiveDispatches} facilityLookup={facilityLookup} />;
      case "scenarios":
        return <ScenariosView scenarios={scenarios} scenarioKey={scenarioKey} setScenarioKey={setScenarioKey} scenarioComparison={scenarioComparison} setScenarioComparison={setScenarioComparison} runAction={runAction} apiFetch={apiFetch} />;
      case "network":
        return <NetworkView facilities={facilities} vehicles={vehicles} />;
      case "objectives":
        return <ObjectivesView objectives={objectives} facilityLookup={facilityLookup} />;
      case "events":
        return <EventsView events={events} />;
      case "impact":
        return <ImpactView metrics={metrics} />;
      case "cloud":
        return <CloudView cloudHealth={cloudHealth} />;
      case "developer":
        return <IntegrationView apiFetch={apiFetch} t={t} />;
      case "settings":
        return <SettingsView lang={lang} onSwitchLang={switchLang} t={t} onSetSpeed={handleSetSpeed} currentSpeed={currentSpeed} isClient={!!clientContext} />;
      case "rlTraining":
        return <RLTrainingView apiFetch={apiFetch} />;
      case "aiExplainer":
        return <AIExplainerView apiFetch={apiFetch} dashboard={dashboard} vehicles={dashboard?.vehicles ?? []} recommendations={recommendations} facilities={facilities} facilityLookup={facilityLookup} />;
      case "aiComparison":
        return <ComparisonView apiFetch={apiFetch} metrics={metrics} />;
      default:
        return <DashboardView metrics={metrics} criticalFacilities={criticalFacilities} proactiveDispatches={proactiveDispatches} riskForecast={riskForecast} facilityLookup={facilityLookup} aiActivity={aiActivity} latestDecision={latestDecision} previousRoute={previousRoute} activityFeed={activityFeed} />;
    }
  };

  return (
    <div className="app-shell">
      <AIRerouteToast toasts={toasts} onDismiss={dismissToast} />
      <Sidebar active={activeView} onNavigate={setActiveView} collapsed={sidebarCollapsed} onMouseEnter={() => setSidebarCollapsed(false)} onMouseLeave={() => setSidebarCollapsed(true)} t={t} clientContext={clientContext} />
      <div className={`main-content ${sidebarCollapsed ? "expanded" : ""}`}>
        <header className="top-bar" lang={lang}>
          <div className="top-bar-left">
            <button
              className="mobile-menu-btn"
              onClick={() => setSidebarCollapsed((c) => !c)}
              aria-label="Toggle sidebar"
            >
              ☰
            </button>
            <h1>{clientContext ? clientContext.companyName : t.commandCenter}</h1>
            {!clientContext && <span className="prototype-badge">{t.prototypeBadge}</span>}
            <div style={{ marginLeft: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{
                display: "inline-block", width: "10px", height: "10px", borderRadius: "50%",
                backgroundColor: wsConnected ? "#10b981" : "#ef4444",
                boxShadow: wsConnected ? "0 0 8px #10b981" : "0 0 8px #ef4444"
              }} title={wsConnected ? "Connected to Backend" : "Disconnected (Auto-reconnecting...)"} />
              <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>{wsConnected ? "Live" : "Reconnecting..."}</span>
            </div>
          </div>
          <div className="top-bar-right">
            <div className="user-chip">
              {user?.photoURL && (
                <img src={user.photoURL} alt="" className="user-avatar" referrerPolicy="no-referrer" />
              )}
              <span className="user-name">{user?.displayName || user?.email || "User"}</span>
              <button className="logout-btn" onClick={onLogout} title={t.logout}>
                {t.logout}
              </button>
            </div>
            {clientContext && (
              <button
                className="sim-btn danger"
                style={{ padding: "0.35rem 0.75rem", fontSize: "0.8rem" }}
                onClick={async () => {
                  if (!window.confirm("Reset your workspace? This will delete all your data permanently.")) return;
                  setLoading(true);
                  try {
                    await apiFetch("/api/v1/client/reset", {
                      method: "DELETE",
                      headers: { Authorization: `Bearer ${clientContext.firebaseToken}` },
                    });
                    window.location.href = "/client";
                  } catch (err) {
                    setError(err.message);
                  } finally {
                    setLoading(false);
                  }
                }}
                title="Reset Workspace"
              >
                Reset Workspace
              </button>
            )}
            {!clientContext && <SimControls onAction={runAction} onSetSpeed={handleSetSpeed} currentSpeed={currentSpeed} t={t} />}
          </div>
        </header>
        <StatusBar dashboard={dashboard} metrics={metrics} t={t} clientContext={clientContext} />
        {message && <div className="banner success">{message}</div>}
        {error && <div className="banner error">{error}</div>}
        {loading && !dashboard ? <div className="loading">Loading intelligence layer...</div> : (
          <main className="view-area">
            <ErrorBoundary key={activeView}>
              <Suspense fallback={<div className="loading">Loading...</div>}>
                {renderView()}
              </Suspense>
            </ErrorBoundary>
          </main>
        )}
      </div>
      <AIChatPanel apiFetch={apiFetch} />
    </div>
  );
}
