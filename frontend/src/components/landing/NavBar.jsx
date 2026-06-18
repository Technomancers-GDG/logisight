import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { onAuthChange, signInWithGoogle, logout } from "../../firebase";

export function NavBar() {
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [user, setUser] = useState(null);

  useEffect(() => {
    return onAuthChange((u) => setUser(u));
  }, []);

  const scrollTo = (id) => {
    setMobileOpen(false);
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth" });
  };

  const handleSignIn = async () => {
    try {
      await signInWithGoogle();
    } catch (err) {
      console.error("Sign in failed:", err);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate("/");
  };

  return (
    <nav className="lp-nav">
      <div className="lp-container">
        <a href="/" className="lp-nav-logo">
          <div className="lp-nav-logo-mark">L</div>
          <span className="lp-nav-logo-text">Logisight</span>
          <span className="lp-nav-logo-tagline">Supply Chain Intelligence</span>
        </a>

        <div className={`lp-nav-links ${mobileOpen ? "open" : ""}`}>
          <button className="lp-nav-link" onClick={() => scrollTo("problem")}>Problem</button>
          <button className="lp-nav-link" onClick={() => scrollTo("how-it-works")}>How It Works</button>
          <button className="lp-nav-link" onClick={() => scrollTo("features")}>Features</button>
          <button className="lp-nav-link" onClick={() => scrollTo("trust")}>Why Logisight</button>
          <div className="lp-nav-actions-mobile">
            {user ? (
              <>
                <span style={{ color: "#94a3b8", fontSize: 14, padding: "4px 8px" }}>{user.displayName || user.email}</span>
                <button className="lp-nav-link-secondary" onClick={() => { setMobileOpen(false); navigate("/client"); }}>Dashboard</button>
                <button className="lp-nav-link-secondary" onClick={() => { setMobileOpen(false); handleLogout(); }}>Sign Out</button>
              </>
            ) : (
              <>
                <button className="lp-btn lp-btn-primary" onClick={() => { setMobileOpen(false); handleSignIn(); }}>Sign In</button>
                <button className="lp-nav-link-secondary" onClick={() => { setMobileOpen(false); navigate("/client"); }}>View Demo</button>
              </>
            )}
          </div>
        </div>

        <div className="lp-nav-actions">
          {user ? (
            <>
              <span style={{ color: "#94a3b8", fontSize: 13, marginRight: 8 }}>{user.displayName || user.email?.split("@")[0]}</span>
              <button className="lp-nav-link-secondary" onClick={() => navigate("/client")}>Dashboard</button>
              <button className="lp-nav-link-secondary" onClick={handleLogout}>Sign Out</button>
            </>
          ) : (
            <>
              <button className="lp-btn lp-btn-primary" onClick={handleSignIn}>Sign In</button>
              <button className="lp-nav-link-secondary" onClick={() => navigate("/client")}>View Demo</button>
            </>
          )}
        </div>

        <button
          className={`lp-nav-hamburger ${mobileOpen ? "open" : ""}`}
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle navigation menu"
        >
          <span /><span /><span />
        </button>
      </div>
    </nav>
  );
}
