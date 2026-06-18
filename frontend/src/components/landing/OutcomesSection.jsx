import { motion } from "framer-motion";
import { useInView } from "framer-motion";
import { useRef } from "react";
import { fadeInUp, staggerContainer, cardHover } from "./animations";

function OutcomeCard({ icon, title, children }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });

  return (
    <motion.div
      ref={ref}
      className="lp-outcome-card"
      variants={cardHover}
      initial="rest"
      whileHover="hover"
      animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
      transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
    >
      <div className="lp-outcome-icon">{icon}</div>
      <div className="lp-outcome-body">
        <h3 className="lp-h3">{title}</h3>
        <p className="lp-body">{children}</p>
      </div>
    </motion.div>
  );
}

export function OutcomesSection() {
  const headerRef = useRef(null);
  const gridRef = useRef(null);
  const headerInView = useInView(headerRef, { once: true, margin: "-80px" });
  const gridInView = useInView(gridRef, { once: true, margin: "-60px" });

  return (
    <section className="lp-section" id="features">
      <div className="lp-container">
        <motion.div
          className="lp-section-header"
          ref={headerRef}
          animate={headerInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
          transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
        >
          <h2 className="lp-h2">What Logisight delivers</h2>
          <p className="lp-body-lg">
            Every capability is designed around a single goal: keeping essential
            supply chains moving when disruptions hit.
          </p>
        </motion.div>

        <motion.div
          className="lp-outcomes-grid"
          ref={gridRef}
          variants={staggerContainer}
          initial="hidden"
          animate={gridInView ? "visible" : "hidden"}
        >
          <OutcomeCard
            icon={
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 8v4l2 2" />
                <path d="M12 2v2" />
                <path d="M12 20v2" />
                <path d="M4.93 4.93l1.41 1.41" />
                <path d="M17.66 17.66l1.41 1.41" />
                <path d="M2 12h2" />
                <path d="M20 12h2" />
              </svg>
            }
            title="12-Hour Disruption Forecast"
          >
            See risks to your routes and facilities up to half a day in advance.
            AI aggregates weather, news, and infrastructure data into a clear,
            actionable forecast.
          </OutcomeCard>

          <OutcomeCard
            icon={
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="5" cy="6" r="3" />
                <circle cx="19" cy="18" r="3" />
                <path d="M5 9v6" />
                <path d="M8 12h8" />
                <path d="M19 15V9" />
                <path d="M16 12l3-3 3 3" />
              </svg>
            }
            title="Real-Time Route Optimization"
          >
            When a disruption occurs, Logisight instantly evaluates alternative
            routes based on cost, time, risk, and capacity — and recommends the
            best option.
          </OutcomeCard>

          <OutcomeCard
            icon={
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
              </svg>
            }
            title="Multi-Source Data Integration"
          >
            Connect weather services, news APIs, traffic data, and your existing
            logistics systems. Logisight becomes the single pane of glass for
            your operations.
          </OutcomeCard>

          <OutcomeCard
            icon={
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="4" y="2" width="16" height="20" rx="2" />
                <line x1="8" y1="7" x2="16" y2="7" />
                <line x1="8" y1="11" x2="16" y2="11" />
                <line x1="8" y1="15" x2="12" y2="15" />
                <polyline points="16 18 18 20 22 16" />
              </svg>
            }
            title="Decision Traceability"
          >
            Every recommendation includes a clear explanation: why this route was
            chosen, what risks were avoided, and what the alternatives would have
            cost. Full audit trail included.
          </OutcomeCard>

          <OutcomeCard
            icon={
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="5 3 19 12 5 21 5 3" />
                <path d="M9 12H3" />
                <path d="M21 12h-3" />
              </svg>
            }
            title="Scenario Simulation"
          >
            Test "what if" scenarios before they happen. Simulate the impact of
            a port closure, a weather event, or a fleet change — and see the
            downstream effects across your entire network.
          </OutcomeCard>

          <OutcomeCard
            icon={
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="20" x2="18" y2="10" />
                <line x1="12" y1="20" x2="12" y2="4" />
                <line x1="6" y1="20" x2="6" y2="14" />
                <rect x="2" y="2" width="20" height="20" rx="2" />
              </svg>
            }
            title="Live Operations Dashboard"
          >
            Real-time visibility into fleet status, delivery performance, risk
            levels, and AI decision activity — all in a single, unified command
            center.
          </OutcomeCard>
        </motion.div>
      </div>
    </section>
  );
}
