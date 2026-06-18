import { motion } from "framer-motion";
import { useInView } from "framer-motion";
import { useRef } from "react";
import { fadeInUp, staggerContainer, cardHover } from "./animations";

function FailsCard({ title, children }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });

  return (
    <motion.div
      ref={ref}
      className="lp-fails-card"
      variants={cardHover}
      initial="rest"
      whileHover="hover"
      animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
      transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
    >
      <div className="lp-fails-card-header">
        <div className="lp-fails-x">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </div>
        <span className="lp-fails-title">{title}</span>
      </div>
      <p className="lp-body">{children}</p>
    </motion.div>
  );
}

export function WhyExistingFailsSection() {
  const headerRef = useRef(null);
  const gridRef = useRef(null);
  const headerInView = useInView(headerRef, { once: true, margin: "-80px" });
  const gridInView = useInView(gridRef, { once: true, margin: "-60px" });

  return (
    <section className="lp-section" style={{ paddingTop: 0 }}>
      <div className="lp-container">
        <motion.div
          className="lp-section-header"
          ref={headerRef}
          animate={headerInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
          transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
        >
          <h2 className="lp-h2">Why traditional approaches fall short</h2>
          <p className="lp-body-lg">
            Spreadsheets, legacy ERP modules, and manual coordination weren't built
            for the speed and complexity of modern supply chains.
          </p>
        </motion.div>

        <motion.div
          className="lp-fails-grid"
          ref={gridRef}
          variants={staggerContainer}
          initial="hidden"
          animate={gridInView ? "visible" : "hidden"}
        >
          <FailsCard title="Reactive by Design">
            Most tools alert you after a disruption has already occurred. By the
            time you're notified, the shipment is already delayed, and the only
            option is damage control.
          </FailsCard>
          <FailsCard title="Siloed Data">
            Weather data lives in one system, fleet tracking in another, and
            inventory in a third. No single view connects the dots, so critical
            patterns go unnoticed.
          </FailsCard>
          <FailsCard title="Slow Rerouting">
            Manual rerouting requires phone calls, email chains, and approvals
            across teams. What should take minutes takes hours — and every minute
            of delay compounds the cost.
          </FailsCard>
        </motion.div>
      </div>
    </section>
  );
}
