import { motion } from "framer-motion";
import { useInView } from "framer-motion";
import { useRef } from "react";
import { fadeInUp, staggerContainer, cardHover } from "./animations";

function ProblemCard({ icon, title, children, stat, statLabel }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });

  return (
    <motion.div
      ref={ref}
      className="lp-problem-card"
      variants={cardHover}
      initial="rest"
      whileHover="hover"
      animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
      transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
    >
      <div className="lp-problem-icon">{icon}</div>
      <h3 className="lp-h3">{title}</h3>
      <p className="lp-body">{children}</p>
      <div className="lp-problem-stat">{stat}</div>
      <p className="lp-body" style={{ marginTop: 4, fontSize: "0.85rem" }}>
        {statLabel}
      </p>
    </motion.div>
  );
}

export function ProblemSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-80px" });

  return (
    <section className="lp-section" id="problem">
      <div className="lp-container">
        <motion.div
          className="lp-section-header"
          ref={ref}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
          transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
        >
          <h2 className="lp-h2">Supply chains are more fragile than ever</h2>
          <p className="lp-body-lg">
            Extreme weather, infrastructure failures, and cascading delays turn routine
            logistics into a daily crisis. When critical goods are at stake, every hour counts.
          </p>
        </motion.div>

        <motion.div
          className="lp-problem-grid"
          variants={staggerContainer}
          initial="hidden"
          animate={isInView ? "visible" : "hidden"}
        >
          <ProblemCard
            icon={
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M2 14s3-3 5-3 4 2 6 2 4-2 6-2 3 1 3 1" />
                <path d="M2 18s3-3 5-3 4 2 6 2 4-2 6-2 3 1 3 1" />
                <path d="M2 10s3-3 5-3 4 2 6 2 4-2 6-2 3 1 3 1" />
                <path d="M2 6s3-3 5-3 4 2 6 2 4-2 6-2 3 1 3 1" />
              </svg>
            }
            title="Disruption Blindness"
            stat="78%"
            statLabel="of disruptions detected after impact"
          >
            Most logistics teams learn about disruptions after they've already
            caused delays. Weather warnings, port closures, and road blockages
            arrive too late to act on.
          </ProblemCard>

          <ProblemCard
            icon={
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21.5 2v6h-6" />
                <path d="M2.5 22v-6h6" />
                <path d="M3 17a9 9 0 0 1 14.5-6.5" />
                <path d="M21 7a9 9 0 0 1-14.5 6.5" />
              </svg>
            }
            title="Coordination Chaos"
            stat="6h+"
            statLabel="average time to manually reroute a critical shipment"
          >
            Disconnected systems, spreadsheets, and manual handoffs mean rerouting
            a single shipment requires calls to multiple teams. By the time a decision
            is made, the window to act has passed.
          </ProblemCard>

          <ProblemCard
            icon={
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
                <polyline points="16 7 22 7 22 13" />
                <polyline points="2 7 8.5 13.5 13.5 8.5 22 17" opacity="0.4" />
              </svg>
            }
            title="Hidden Costs"
            stat="15-30%"
            statLabel="of logistics costs are driven by unplanned disruptions"
          >
            Spoilage, fuel waste from inefficient rerouting, and missed delivery
            windows add costs that never appear on a single invoice. The real price
            of disruption is invisible — until it's too late.
          </ProblemCard>
        </motion.div>
      </div>
    </section>
  );
}
