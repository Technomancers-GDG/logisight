import { describe, it, expect } from "vitest";
import {
  formatINRCompact,
  formatDurationFromMinutes,
  decisionVerb,
  actionDetail,
  recommendationTime,
  buildDecisionFromRecommendation,
  buildActivityFeed,
} from "../src/components/DashboardShell";

describe("formatINRCompact", () => {
  it("formats lakhs", () => {
    expect(formatINRCompact(250000)).toBe("₹2.5L");
  });

  it("formats thousands", () => {
    expect(formatINRCompact(50000)).toBe("₹50K");
  });

  it("formats small amounts as INR currency", () => {
    const result = formatINRCompact(500);
    expect(result).toContain("₹");
    expect(result).toContain("500");
  });

  it("handles zero", () => {
    const result = formatINRCompact(0);
    expect(result).toContain("₹");
  });
});

describe("formatDurationFromMinutes", () => {
  it("converts minutes to hours", () => {
    expect(formatDurationFromMinutes(120)).toBe("2.0h");
  });

  it("uses fallback for invalid input", () => {
    expect(formatDurationFromMinutes(null)).toBe("36h");
    expect(formatDurationFromMinutes(undefined)).toBe("36h");
    expect(formatDurationFromMinutes("abc")).toBe("36h");
  });

  it("shows decimal for under 10 hours", () => {
    expect(formatDurationFromMinutes(90)).toBe("1.5h");
  });

  it("rounds to integer for 10+ hours", () => {
    expect(formatDurationFromMinutes(600)).toBe("10h");
  });

  it("uses custom fallback", () => {
    expect(formatDurationFromMinutes(null, 12)).toBe("12h");
  });
});

describe("decisionVerb", () => {
  it("returns Rerouted for reroute actions", () => {
    expect(decisionVerb("reroute_warehouse")).toBe("Rerouted");
    expect(decisionVerb("reroute_port")).toBe("Rerouted");
  });

  it("returns Held for wait actions", () => {
    expect(decisionVerb("wait")).toBe("Held");
    expect(decisionVerb("wait_at_dock")).toBe("Held");
  });

  it("returns Deferred for defer actions", () => {
    expect(decisionVerb("defer")).toBe("Deferred");
  });

  it("returns Optimized for all other actions", () => {
    expect(decisionVerb("continue")).toBe("Optimized");
    expect(decisionVerb("dispatch")).toBe("Optimized");
    expect(decisionVerb("")).toBe("Optimized");
  });
});

describe("actionDetail", () => {
  it("detects port delays", () => {
    expect(actionDetail("reroute", "avoided port congestion")).toBe("avoided port delay");
  });

  it("detects route risk", () => {
    expect(actionDetail("reroute", "high risk zone")).toBe("reduced route risk");
  });

  it("detects rail switch", () => {
    expect(actionDetail("reroute_rail", "")).toBe("switched to rail route for cost efficiency");
  });

  it("detects reroute fallback", () => {
    expect(actionDetail("reroute_warehouse", "")).toBe("selected a safer fallback route");
  });

  it("defaults to updated route recommendation", () => {
    expect(actionDetail("continue", "")).toBe("updated route recommendation");
  });
});

describe("recommendationTime", () => {
  it("formats a valid ISO timestamp", () => {
    const result = recommendationTime({ created_at: "2026-06-11T12:30:00" });
    expect(result).toContain(":");
  });

  it("falls back to simulation_time", () => {
    const result = recommendationTime({ simulation_time: "2026-06-11T14:00:00" });
    expect(result).toContain(":");
  });

  it("falls back to current time for missing data", () => {
    expect(recommendationTime({})).toBeTruthy();
    expect(recommendationTime(null)).toBeTruthy();
  });

  it("returns fallback for invalid date strings", () => {
    expect(recommendationTime({ created_at: "not-a-date" })).toBe("--:--");
  });
});

describe("buildDecisionFromRecommendation", () => {
  const baseRec = {
    id: 1,
    action: "reroute_warehouse",
    explanation: "avoided port congestion",
    financial_impact_usd: 35000,
    baseline_cost: 120000,
    recommended_cost: 85000,
    confidence: 0.92,
  };

  it("builds a decision object from a recommendation", () => {
    const decision = buildDecisionFromRecommendation(baseRec, {});
    expect(decision.title).toContain("Rerouted");
    expect(decision.title).toContain("SHP-001");
    expect(decision.reason).toBe("avoided port congestion");
    expect(decision.confidence).toBe(92);
    expect(decision.impact[0]).toContain("₹");
    expect(decision.comparison.before.label).toBe("Route A");
    expect(decision.comparison.after.label).toBe("Route B");
  });

  it("generates a mock decision when no recommendation", () => {
    const decision = buildDecisionFromRecommendation(null, {});
    expect(decision.id).toBe("mock-decision");
    expect(decision.title).toContain("Rerouted");
    expect(decision.confidence).toBe(92);
  });

  it("handles missing confidence", () => {
    const rec = { ...baseRec, confidence: undefined };
    const decision = buildDecisionFromRecommendation(rec, {});
    expect(decision.confidence).toBe(90);
  });

  it("handles missing financial impact", () => {
    const rec = { ...baseRec, financial_impact_usd: undefined, baseline_cost: undefined, recommended_cost: undefined };
    const decision = buildDecisionFromRecommendation(rec, {});
    expect(decision.impact[0]).toContain("₹");
  });

  it("detects reroute in action for decision text", () => {
    const decision = buildDecisionFromRecommendation(baseRec, {});
    expect(decision.comparison.decision).toContain("minimize cost");
  });
});

describe("buildActivityFeed", () => {
  it("builds feed items from recommendations", () => {
    const recs = [
      { id: 1, action: "reroute", created_at: "2026-06-11T12:00:00", explanation: "delay" },
      { id: 2, action: "continue", created_at: "2026-06-11T12:05:00", explanation: "" },
    ];
    const feed = buildActivityFeed(recs, null);
    expect(feed.length).toBe(2);
    expect(feed[0].id).toBe("rec-1");
    expect(feed[0].title).toContain("Rerouted");
    expect(feed[1].title).toContain("Optimized");
  });

  it("limits to 15 items", () => {
    const recs = Array.from({ length: 20 }, (_, i) => ({
      id: i, action: "continue", created_at: "2026-06-11T12:00:00",
    }));
    const feed = buildActivityFeed(recs, null);
    expect(feed.length).toBe(15);
  });

  it("returns empty array for null input", () => {
    expect(buildActivityFeed(null, null)).toEqual([]);
    expect(buildActivityFeed(undefined, null)).toEqual([]);
  });
});
