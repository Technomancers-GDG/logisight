import { motion } from "framer-motion";
import { useInView } from "framer-motion";
import { useRef } from "react";
import { fadeInUp, staggerContainer, cardHover } from "./animations";

function TrustCard({ icon, title, children }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });

  return (
    <motion.div
      ref={ref}
      className="lp-trust-card"
      variants={cardHover}
      initial="rest"
      whileHover="hover"
      animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
      transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
    >
      <span className="lp-trust-icon">{icon}</span>
      <h3 className="lp-h3">{title}</h3>
      <p className="lp-body">{children}</p>
    </motion.div>
  );
}

export function TrustSection() {
  const headerRef = useRef(null);
  const gridRef = useRef(null);
  const headerInView = useInView(headerRef, { once: true, margin: "-80px" });
  const gridInView = useInView(gridRef, { once: true, margin: "-60px" });

  return (
    <section className="lp-section" id="trust">
      <div className="lp-container">
        <motion.div
          className="lp-section-header"
          ref={headerRef}
          animate={headerInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
          transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
        >
          <h2 className="lp-h2">Built for real-world logistics operations</h2>
          <p className="lp-body-lg">
            Logisight was designed with input from supply chain operators, AI
            researchers, and disaster response coordinators.
          </p>
        </motion.div>

        <motion.div
          className="lp-trust-grid"
          ref={gridRef}
          variants={staggerContainer}
          initial="hidden"
          animate={gridInView ? "visible" : "hidden"}
        >
          <TrustCard
            icon={
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <ellipse cx="12" cy="12" rx="4" ry="10" />
                <line x1="2" y1="12" x2="22" y2="12" />
                <line x1="12" y1="2" x2="12" y2="22" />
              </svg>
            }
            title="Regionally Agnostic"
          >
            Designed to work with any geography, any infrastructure context.
            Weather data, news feeds, and route networks adapt to wherever
            your supply chain operates.
          </TrustCard>

          <TrustCard
            icon={
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="4" y="8" width="16" height="12" rx="2" />
                <circle cx="9" cy="13" r="1.5" />
                <circle cx="15" cy="13" r="1.5" />
                <path d="M9 17a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2" />
                <path d="M12 2v4" />
                <path d="M8 4l-3 3" />
                <path d="M16 4l3 3" />
              </svg>
            }
            title="AI with Transparency"
          >
            Every AI decision includes a plain-English explanation. You always
            know why a route was recommended, what alternatives exist, and how
            confident the system is.
          </TrustCard>

          <TrustCard
            icon={
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                <circle cx="12" cy="16" r="1" />
                <line x1="12" y1="16" x2="12" y2="16.5" />
                <path d="M9 11v-2a3 3 0 0 1 6 0v2" />
              </svg>
            }
            title="Explainable by Design"
          >
            Full traceability on every recommendation. Logged decisions, audit
            trails, and confidence scoring mean you never have to trust a black
            box with your supply chain.
          </TrustCard>
        </motion.div>
      </div>
    </section>
  );
}
