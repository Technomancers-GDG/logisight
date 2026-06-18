import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useInView } from "framer-motion";
import { useRef } from "react";
import { fadeInUp } from "./animations";

export function PartnerSection() {
  const navigate = useNavigate();
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-80px" });

  return (
    <section className="lp-section" style={{ background: "var(--surface, #111827)", padding: "80px 0" }}>
      <div className="lp-container">
        <motion.div
          ref={ref}
          style={{ textAlign: "center", maxWidth: 700, margin: "0 auto" }}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
          transition={{ duration: 0.6, ease: [0.25, 0.1, 0.25, 1] }}
        >
          <span className="lp-eyebrow" style={{ marginBottom: 20 }}>For Logistics Partners</span>
          <h2 className="lp-h2">Integrate Your Fleet</h2>
          <p className="lp-body-lg" style={{ color: "var(--muted)", marginBottom: 32 }}>
            Connect your logistics operations and get real-time visibility, AI-powered
            route optimization, and a dedicated operations dashboard.
          </p>
          <div style={{ display: "flex", gap: 16, justifyContent: "center", flexWrap: "wrap", marginBottom: 32 }}>
            {[
              { icon: "\ud83d\udccb", text: "Upload your facilities and fleet in minutes" },
              { icon: "\ud83c\udf0d", text: "Track your operations in real-time" },
              { icon: "\ud83d\udd0c", text: "Integrate via REST API + Webhooks" },
              { icon: "\ud83e\udde0", text: "AI-powered route optimization" },
            ].map((item, i) => (
              <div key={i} style={{ flex: "1 1 200px", maxWidth: 240, background: "#1a2332", borderRadius: 12, padding: 20, border: "1px solid #2a3342" }}>
                <div style={{ fontSize: 24, marginBottom: 8 }}>{item.icon}</div>
                <div style={{ fontSize: 14, color: "#e5e7eb" }}>{item.text}</div>
              </div>
            ))}
          </div>
          <button className="lp-btn lp-btn-primary lp-btn-lg" onClick={() => navigate("/client")}>
            Integrate Your Fleet
          </button>
          <p style={{ marginTop: 16, fontSize: 14, color: "#6b7280" }}>
            Already registered?{" "}
            <a href="/client" style={{ color: "#60a5fa", textDecoration: "none", fontWeight: 500, cursor: "pointer" }}
              onClick={(e) => { e.preventDefault(); navigate("/client"); }}>
              Sign in to your portal
            </a>
          </p>
        </motion.div>
      </div>
    </section>
  );
}
