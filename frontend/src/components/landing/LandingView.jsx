import { useEffect, useRef } from "react";
import { NavBar } from "./NavBar";
import { HeroSection } from "./HeroSection";
import { ProblemSection } from "./ProblemSection";
import { WhyExistingFailsSection } from "./WhyExistingFailsSection";
import { HowItWorksSection } from "./HowItWorksSection";
import { OutcomesSection } from "./OutcomesSection";
import { ProductPreviewSection } from "./ProductPreviewSection";
import { TrustSection } from "./TrustSection";
import { CTASection } from "./CTASection";
import { PartnerSection } from "./PartnerSection";
import { Footer } from "./Footer";
import "./landing.css";

function useScrollReveal() {
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
          }
        });
      },
      { threshold: 0.08, rootMargin: "0px 0px -40px 0px" }
    );

    const elements = document.querySelectorAll(".lp-animate");
    elements.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);
}

export function LandingView() {
  useScrollReveal();

  return (
    <div className="landing-page">
      <NavBar />
      <HeroSection />
      <ProblemSection />
      <WhyExistingFailsSection />
      <HowItWorksSection />
      <OutcomesSection />
      <ProductPreviewSection />
      <TrustSection />
      <PartnerSection />
      <CTASection />
      <Footer />
    </div>
  );
}
