const TABS = [
  { id: "route", label: "Route", icon: "🗺" },
  { id: "tasks", label: "Tasks", icon: "📋" },
  { id: "incidents", label: "Report", icon: "⚠" },
  { id: "ai", label: "AI", icon: "✨" },
];

export function BottomNav({ active, onTabChange }) {
  return (
    <nav className="bottom-nav">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={`bottom-nav-btn${active === tab.id ? " active" : ""}`}
          onClick={() => onTabChange(tab.id)}
        >
          <span className="nav-icon">{tab.icon}</span>
          <span>{tab.label}</span>
        </button>
      ))}
    </nav>
  );
}
