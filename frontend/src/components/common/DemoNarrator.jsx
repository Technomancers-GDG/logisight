import { useState, useEffect } from "react";

export function DemoNarrator({ latestDecision, activityFeed }) {
  const [displayedText, setDisplayedText] = useState("");
  const [targetText, setTargetText] = useState("System initialized. AI Agent monitoring supply chain network for disruptions...");
  const [isTyping, setIsTyping] = useState(false);
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    setIsVisible(true);
    const hideTimeout = setTimeout(() => setIsVisible(false), 12000);
    return () => clearTimeout(hideTimeout);
  }, [targetText]);

  useEffect(() => {
    if (latestDecision) {
      let narratorText = `AI Decision Engine evaluated ${(latestDecision.action || "a new route").replace(/_/g, " ").toUpperCase()}. `;
      if (latestDecision.explanation) {
        narratorText += latestDecision.explanation;
      }
      if (targetText !== narratorText) {
        setTargetText(narratorText);
        setDisplayedText("");
      }
    } else if (activityFeed && activityFeed.length > 0) {
      const latest = activityFeed[0];
      const newText = `System update: ${latest.message}`;
      if (targetText !== newText) {
        setTargetText(newText);
        setDisplayedText("");
      }
    }
  }, [latestDecision, activityFeed, targetText]);

  useEffect(() => {
    if (displayedText !== targetText) {
      setIsTyping(true);
      const timeout = setTimeout(() => {
        setDisplayedText(targetText.substring(0, displayedText.length + 2)); // type 2 chars at a time
      }, 25);
      return () => clearTimeout(timeout);
    } else {
      setIsTyping(false);
    }
  }, [displayedText, targetText]);

  if (!isVisible) return null;

  return (
    <div style={{
      position: "fixed",
      bottom: "30px",
      left: "50%",
      transform: "translateX(-50%)",
      backgroundColor: "rgba(15, 23, 42, 0.9)",
      backdropFilter: "blur(12px)",
      border: "1px solid rgba(59, 130, 246, 0.5)",
      borderRadius: "30px",
      padding: "14px 28px",
      color: "#f8fafc",
      display: "flex",
      alignItems: "center",
      gap: "16px",
      boxShadow: "0 12px 40px rgba(0, 0, 0, 0.5)",
      zIndex: 999,
      maxWidth: "700px",
      width: "80%"
    }}>
      <div style={{
        minWidth: "14px",
        height: "14px",
        borderRadius: "50%",
        backgroundColor: isTyping ? "#3b82f6" : "#10b981",
        boxShadow: isTyping ? "0 0 12px #3b82f6" : "0 0 12px #10b981",
        animation: isTyping ? "narrator-pulse 0.8s infinite alternate" : "none"
      }} />
      <div style={{ fontSize: "1.05rem", lineHeight: 1.5, fontFamily: "'Inter', sans-serif" }}>
        <strong style={{ color: "#93c5fd" }}>NARRATOR: </strong>
        {displayedText}
        {isTyping && <span style={{ opacity: 0.5, marginLeft: "2px" }}>▋</span>}
      </div>
      <style>{`
        @keyframes narrator-pulse {
          from { opacity: 0.3; transform: scale(0.9); }
          to { opacity: 1; transform: scale(1.1); }
        }
      `}</style>
    </div>
  );
}
