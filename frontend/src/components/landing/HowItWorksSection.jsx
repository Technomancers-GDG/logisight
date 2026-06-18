import { motion } from "framer-motion";
import { useInView } from "framer-motion";
import { useRef } from "react";
import { fadeInUp, staggerContainer, cardHover } from "./animations";

function Step({ number, icon, title, children }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });

  return (
    <motion.div
      ref={ref}
      className="lp-step"
      variants={cardHover}
      initial="rest"
      whileHover="hover"
      animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
      transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
    >
      <div className="lp-step-number">{number}</div>
      <span className="lp-step-icon">{icon}</span>
      <h3 className="lp-h3">{title}</h3>
      <p className="lp-body">{children}</p>
    </motion.div>
  );
}

export function HowItWorksSection() {
  const headerRef = useRef(null);
  const gridRef = useRef(null);
  const headerInView = useInView(headerRef, { once: true, margin: "-80px" });
  const gridInView = useInView(gridRef, { once: true, margin: "-60px" });

  return (
    <section className="lp-section" id="how-it-works" style={{ background: "var(--lp-surface)" }}>
      <div className="lp-container">
        <motion.div
          className="lp-section-header"
          ref={headerRef}
          animate={headerInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
          transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
        >
          <span className="lp-eyebrow" style={{ marginBottom: 20 }}>How It Works</span>
          <h2 className="lp-h2">From disruption to resolution in three steps</h2>
          <p className="lp-body-lg">
            Logisight connects data, prediction, and action into a single
            intelligent workflow.
          </p>
        </motion.div>

        <motion.div
          className="lp-steps"
          ref={gridRef}
          variants={staggerContainer}
          initial="hidden"
          animate={gridInView ? "visible" : "hidden"}
        >
          <Step
            number={1}
            icon={
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="2" />
                <path d="M12 4a8 8 0 0 1 8 8" />
                <path d="M12 8a4 4 0 0 1 4 4" />
                <path d="M4.93 4.93A10 10 0 0 1 12 2" />
                <path d="M2 12a10 10 0 0 1 10-10" />
                <path d="M2 12h2" />
                <path d="M20 12h2" />
              </svg>
            }
            title="Monitor"
          >
            Ingest real-time data from weather APIs, news feeds, sensor networks,
            and traffic reports. Logisight continuously scans for conditions that
            could affect your supply chain.
          </Step>

          <Step
            number={2}
            icon={
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2a3 3 0 0 0-3 3v1" />
                <path d="M12 2a3 3 0 0 1 3 3v1" />
                <path d="M7 6h10a2 2 0 0 1 2 2v1a4 4 0 0 1-4 4H9a4 4 0 0 1-4-4V8a2 2 0 0 1 2-2z" />
                <path d="M9 14v3a3 3 0 0 0 6 0v-3" />
                <circle cx="12" cy="18" r="4" />
                <path d="M8 21.5A6 6 0 0 1 12 20a6 6 0 0 1 4 1.5" />
              </svg>
            }
            title="Predict"
          >
            AI models assess route risk up to 12 hours ahead, evaluating
            weather patterns, infrastructure status, traffic conditions, and
            historical disruption data.
          </Step>

          <Step
            number={3}
            icon={
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
              </svg>
            }
            title="Optimize"
          >
            Receive actionable reroute recommendations with confidence scores,
            cost comparisons, and real-time impact estimates. Deploy changes
            instantly or review before executing.
          </Step>
        </motion.div>
      </div>
    </section>
  );
}
