import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { HeroNetworkBackground } from "./HeroNetworkBackground";
import { AnimatedCounter } from "./AnimatedCounter";

const textVariant = (delay = 0) => ({
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.25, 0.1, 0.25, 1], delay } },
});

export function HeroSection() {
  const navigate = useNavigate();

  return (
    <section className="lp-hero" id="hero">
      <HeroNetworkBackground />
      <div className="lp-hero-gradient" />

      <div className="lp-container" style={{ position: "relative", zIndex: 2 }}>
        <div className="lp-hero-content">
          <motion.div
            className="lp-hero-text"
            initial="hidden"
            animate="visible"
            variants={{
              visible: { transition: { staggerChildren: 0.12 } },
            }}
          >
            <motion.span className="lp-eyebrow" variants={textVariant(0)}>
              Supply Chain Intelligence Platform
            </motion.span>
            <motion.h1 className="lp-h1" variants={textVariant(0.12)}>
              See disruptions before they happen. Protect what matters.
            </motion.h1>
            <motion.p className="lp-body-lg" variants={textVariant(0.24)}>
              Logisight is an AI-powered operations platform that predicts supply chain
              disruptions — from weather events to infrastructure failures — and
              instantly recommends optimal reroutes so critical goods keep moving.
            </motion.p>
            <motion.div className="lp-hero-actions" variants={textVariant(0.36)}>
              <button className="lp-btn lp-btn-primary lp-btn-lg" onClick={() => navigate("/client")}>
                Start the Demo
              </button>
              <button className="lp-btn lp-btn-secondary lp-btn-lg" onClick={() => {
                document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth" });
              }}>
                See How It Works
              </button>
            </motion.div>
          </motion.div>

          <motion.div
            className="lp-hero-visual"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, ease: [0.25, 0.1, 0.25, 1], delay: 0.3 }}
          >
            <img src="/assets/hero-concept-1.png" alt="" aria-hidden="true" />
          </motion.div>
        </div>

        <motion.div
          className="lp-hero-stats"
          initial="hidden"
          animate="visible"
          variants={{
            visible: { transition: { staggerChildren: 0.15, delayChildren: 0.5 } },
          }}
        >
          <motion.div
            className="lp-hero-stat"
            variants={{
              hidden: { opacity: 0, y: 16 },
              visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.25, 0.1, 0.25, 1] } },
            }}
          >
            <h3><AnimatedCounter value={12} suffix="h" /></h3>
            <p>Advanced disruption forecasting</p>
          </motion.div>
          <motion.div
            className="lp-hero-stat"
            variants={{
              hidden: { opacity: 0, y: 16 },
              visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.25, 0.1, 0.25, 1] } },
            }}
          >
            <h3><AnimatedCounter value={99} suffix="%" /></h3>
            <p>Route optimization coverage</p>
          </motion.div>
          <motion.div
            className="lp-hero-stat"
            variants={{
              hidden: { opacity: 0, y: 16 },
              visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.25, 0.1, 0.25, 1] } },
            }}
          >
            <h3><AnimatedCounter value={100} suffix="+" /></h3>
            <p>Multi-source data integration</p>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
