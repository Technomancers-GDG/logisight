import { motion } from "framer-motion";
import { useInView } from "framer-motion";
import { useRef } from "react";
import { fadeInUp } from "./animations";

export function ProductPreviewSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });

  return (
    <section className="lp-section lp-preview-section" id="dashboard-preview">
      <div className="lp-container">
        <motion.div
          className="lp-section-header"
          ref={ref}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
          transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
        >
          <h2 className="lp-h2">See it in action</h2>
          <p className="lp-body-lg">
            A live operations dashboard showing real-time risk assessments,
            route status, and AI-powered recommendations.
          </p>
        </motion.div>

        <motion.div
          className="lp-preview-image-wrap"
          initial={{ opacity: 0, y: 40, scale: 0.98 }}
          animate={isInView ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: 40, scale: 0.98 }}
          transition={{ duration: 0.7, ease: [0.25, 0.1, 0.25, 1], delay: 0.1 }}
        >
          <img
            src="/images/dashboard-preview.png"
            alt="Logisight dashboard showing real-time risk assessments, route status, and AI recommendations"
            className="lp-preview-image"
            loading="lazy"
            width="1200"
            height="675"
          />
        </motion.div>
      </div>
    </section>
  );
}
