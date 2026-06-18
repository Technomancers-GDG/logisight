import { useState, useEffect, lazy, Suspense } from "react";
import { useNavigate } from "react-router-dom";

const DashboardShell = lazy(() => import("../components/DashboardShell"));
const OnboardingWizard = lazy(() => import("./OnboardingWizard"));
import { signInWithGoogle } from "../firebase";

const API_BASE = import.meta.env.VITE_API_BASE || "";

async function checkFleetStatus(apiKey, firebaseToken) {
  const headers = {};
  if (apiKey) headers["X-API-Key"] = apiKey;
  if (firebaseToken) headers["Authorization"] = `Bearer ${firebaseToken}`;
  const resp = await fetch(`${API_BASE}/api/v1/client/upload-status`, { headers });
  if (!resp.ok) throw new Error(`upload-status returned ${resp.status}`);
  return resp.json();
}

function Loading() {
  return (
    <div style={{ minHeight: "100vh", background: "radial-gradient(ellipse at top, #eef2f6, #f8fafc)", display: "flex", alignItems: "center", justifyContent: "center", color: "#475569", fontWeight: 500 }}>
      Loading...
    </div>
  );
}

export default function ClientPortal() {
  const navigate = useNavigate();
  const [selectedTenantId, setSelectedTenantId] = useState(null);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Load stored selection
  useEffect(() => {
    async function init() {
      const stored = localStorage.getItem("logisight_tenant");
      if (!stored) {
        setLoading(false);
        return;
      }
      const parsed = JSON.parse(stored);
      setSelectedTenantId(parsed.id);
      const baseStatus = { client_id: parsed.id, company_name: parsed.name, api_key: parsed.api_key, firebaseToken: parsed.firebaseToken };
      try {
        const s = await checkFleetStatus(parsed.api_key, parsed.firebaseToken);
        setStatus({ ...baseStatus, has_fleet: !!s.all_complete });
      } catch {
        setStatus(baseStatus);
      }
      setLoading(false);
    }
    init();
  }, []);

  const handleCreateWorkspace = async (e) => {
    e.preventDefault();
    if (!companyName || !email) {
      setError("Please fill in all fields.");
      return;
    }
    setError("");
    setIsSubmitting(true);

    try {
      const resp = await fetch(`${API_BASE}/api/auth/quick-register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company_name: companyName, email: email })
      });

      if (!resp.ok) {
        throw new Error("Registration failed");
      }

      const data = await resp.json();
      
      const stored = { 
        id: data.client_id, 
        name: data.company_name, 
        slug: data.slug, 
        api_key: data.api_key 
      };
      localStorage.setItem("logisight_tenant", JSON.stringify(stored));

      setSelectedTenantId(data.client_id);
      setStatus({ client_id: data.client_id, company_name: data.company_name, api_key: data.api_key });
    } catch (e) {
      setError("Failed to create workspace. Is the backend running?");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGoogleLogin = async () => {
    setError("");
    setIsSubmitting(true);
    try {
      const result = await signInWithGoogle();
      
      const resp = await fetch(`${API_BASE}/api/auth/login/firebase`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${result.idToken}` 
        }
      });
      
      if (!resp.ok) {
        throw new Error("Firebase Backend Auth Failed");
      }
      
      const data = await resp.json();
      
      const stored = {
        id: data.client_id,
        name: data.company_name,
        slug: data.slug,
        firebaseToken: result.idToken
      };
      localStorage.setItem("logisight_tenant", JSON.stringify(stored));
      setSelectedTenantId(data.client_id);
      setStatus({ client_id: data.client_id, company_name: data.company_name, firebaseToken: result.idToken });
    } catch (err) {
      console.error(err);
      setError("Google Login failed. " + err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("logisight_tenant");
    setSelectedTenantId(null);
    setStatus(null);
    navigate("/");
  };

  if (loading) return <Loading />;

  // No tenant selected — show creation form
  if (!selectedTenantId) {
    return (
      <div style={{ minHeight: "100vh", background: "radial-gradient(ellipse at top, #eef2f6, #f8fafc)", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "Inter, system-ui, sans-serif" }}>
        <div style={{ 
          textAlign: "center", 
          background: "rgba(255, 255, 255, 0.7)", 
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          padding: "48px 40px", 
          borderRadius: 28, 
          border: "1px solid rgba(0,0,0,0.04)", 
          boxShadow: "0 24px 64px rgba(0,0,0,0.08)",
          width: "100%",
          maxWidth: 420 
        }}>
          <div className="logo-mark large" style={{ margin: "0 auto 20px", background: "#111", color: "#eaf86b", width: 48, height: 48, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: "1.2rem", boxShadow: "0 8px 16px rgba(0,0,0,0.1)" }}>L</div>
          <h2 style={{ color: "#111", marginBottom: 8, fontSize: "1.75rem", fontWeight: 800, letterSpacing: "-0.03em" }}>Create Workspace</h2>
          <p style={{ color: "#475569", marginBottom: 24, fontSize: "0.95rem", lineHeight: 1.5 }}>
            Register a new client account to access the Logisight operations dashboard.
          </p>

          {error && <div style={{ color: "#ef4444", marginBottom: 16, fontSize: 14 }}>{error}</div>}

          <form onSubmit={handleCreateWorkspace} style={{ display: "flex", flexDirection: "column", gap: 12, textAlign: "left" }}>
            <div>
              <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#334155", marginBottom: 6 }}>Company Name</label>
              <input 
                type="text" 
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="e.g. Acme Logistics"
                style={{ width: "100%", padding: "12px 16px", borderRadius: 8, border: "1px solid #cbd5e1", outline: "none", fontSize: "0.95rem", boxSizing: "border-box" }}
                required
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#334155", marginBottom: 6 }}>Contact Email</label>
              <input 
                type="email" 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="hello@acme.com"
                style={{ width: "100%", padding: "12px 16px", borderRadius: 8, border: "1px solid #cbd5e1", outline: "none", fontSize: "0.95rem", boxSizing: "border-box" }}
                required
              />
            </div>
            <button
              type="submit"
              disabled={isSubmitting}
              style={{ 
                marginTop: 12,
                width: "100%",
                padding: "14px 20px", 
                background: "#111", 
                color: "#fff", 
                border: "none", 
                borderRadius: 10,
                fontSize: "0.95rem", 
                fontWeight: 600, 
                cursor: isSubmitting ? "not-allowed" : "pointer",
                opacity: isSubmitting ? 0.7 : 1
              }}
            >
              {isSubmitting ? "Creating..." : "Create Workspace"}
            </button>
          </form>

          <div style={{ margin: "24px 0", display: "flex", alignItems: "center" }}>
            <div style={{ flex: 1, height: 1, background: "#cbd5e1" }} />
            <div style={{ padding: "0 12px", color: "#64748b", fontSize: "0.85rem", fontWeight: 500 }}>OR</div>
            <div style={{ flex: 1, height: 1, background: "#cbd5e1" }} />
          </div>

          <button
            onClick={handleGoogleLogin}
            disabled={isSubmitting}
            style={{ 
              width: "100%",
              padding: "14px 20px", 
              background: "#fff", 
              color: "#334155", 
              border: "1px solid #cbd5e1", 
              borderRadius: 10,
              fontSize: "0.95rem", 
              fontWeight: 600, 
              cursor: isSubmitting ? "not-allowed" : "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              boxShadow: "0 1px 2px rgba(0,0,0,0.05)"
            }}
          >
            <svg viewBox="0 0 24 24" width="18" height="18" xmlns="http://www.w3.org/2000/svg">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            Sign in with Google
          </button>

          <p style={{ marginTop: 24, fontSize: "0.85rem", color: "#64748b", fontWeight: 500 }}>
            <a href="/" style={{ color: "#475569", textDecoration: "none" }}>Back to home</a>
            <span style={{ margin: "0 12px", color: "#cbd5e1" }}>•</span>
            <a href="/dashboard" style={{ color: "#475569", textDecoration: "none" }}>View Demo</a>
          </p>
        </div>
      </div>
    );
  }

  // Tenant selected — check fleet
  if (!status?.has_fleet) {
    return (
      <Suspense fallback={<Loading />}>
        <OnboardingWizard
          apiKey={status.api_key}
          firebaseToken={status.firebaseToken}
          onComplete={() => {
            setStatus({ ...status, has_fleet: true });
          }}
        />
      </Suspense>
    );
  }

  // Full dashboard
  return (
    <Suspense fallback={<Loading />}>
      <DashboardShell
        onLogout={handleLogout}
        clientContext={{
          clientId: status.client_id,
          companyName: status.company_name,
          apiKey: status.api_key,
          firebaseToken: status.firebaseToken,
        }}
      />
    </Suspense>
  );
}
