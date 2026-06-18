import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useInView } from "framer-motion";
import { useRef } from "react";
import { fadeInUp } from "./animations";

export function CTASection() {
  const navigate = useNavigate();
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-80px" });

  return (
    <section className="lp-cta">
      <div className="lp-cta-bg" />
      <div className="lp-container">
        <motion.div
          className="lp-cta-content"
          ref={ref}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
          transition={{ duration: 0.6, ease: [0.25, 0.1, 0.25, 1] }}
        >
          <span className="lp-eyebrow" style={{ marginBottom: 20 }}>Get Started</span>
          <h2 className="lp-h2">Ready to protect your supply chain?</h2>
          <p className="lp-body-lg">
            Start the demo and see Logisight in action. No sign-up required.
            No onboarding calls. Just click and experience the platform.
          </p>
          <div className="lp-cta-actions">
            <button className="lp-btn lp-btn-primary lp-btn-lg" onClick={() => navigate("/client")}>
              Start the Demo
            </button>
            <button className="lp-btn lp-btn-secondary lp-btn-lg" onClick={() => navigate("/client")}>
              Sign In
            </button>
          </div>
          <p className="lp-cta-note">
            Free during pilot phase. Built for the Google Solution Challenge 2026.
          </p>
        </motion.div>
      </div>
    </section>
  );
}
