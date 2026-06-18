export function Footer() {
  return (
    <footer className="lp-footer">
      <div className="lp-container">
        <div className="lp-footer-grid">
          <div className="lp-footer-brand">
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div className="lp-nav-logo-mark">L</div>
              <span className="lp-nav-logo-text">Logisight</span>
            </div>
            <p className="lp-body">
              AI-powered supply chain intelligence. Predict disruptions, protect
              essential goods, and keep supply chains moving.
            </p>
          </div>

          <div>
            <h4>Product</h4>
            <ul className="lp-footer-links">
              <li><a href="#features">Features</a></li>
              <li><a href="#how-it-works">How It Works</a></li>
              <li><a href="#trust">Why Logisight</a></li>
            </ul>
          </div>

          <div>
            <h4>Company</h4>
            <ul className="lp-footer-links">
              <li><a href="#about">About</a></li>
              <li><a href="#contact">Contact</a></li>
              <li><a href="#privacy">Privacy</a></li>
            </ul>
          </div>

          <div>
            <h4>Resources</h4>
            <ul className="lp-footer-links">
              <li><a href="/client">Dashboard</a></li>
              <li><a href="#docs">Documentation</a></li>
              <li><a href="#status">System Status</a></li>
            </ul>
          </div>
        </div>

        <div className="lp-footer-bottom">
          <span>&copy; {new Date().getFullYear()} Logisight. All rights reserved.</span>
          <span>Built for Google Solution Challenge 2026</span>
        </div>
      </div>
    </footer>
  );
}
