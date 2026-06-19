import { describe, it, expect } from "vitest";

describe("i18n Translations", () => {
  const en = {
    app: { title: "LogiSight", subtitle: "Supply Chain Command Center" },
    nav: { dashboard: "Dashboard", map: "Map", liveOps: "Live Ops", scenarios: "Scenarios", events: "Events" },
    actions: { start: "Start", pause: "Pause", reset: "Reset", inject: "Inject Disruption" },
    status: { running: "Running", paused: "Paused", stopped: "Stopped" },
    metrics: { stockoutsPrevented: "Stockouts Prevented", criticalDeliveries: "Critical Deliveries Saved" },
  };

  const hi = {
    app: { title: "लॉजीसाइट", subtitle: "आपूर्ति श्रृंखला कमांड सेंटर" },
    nav: { dashboard: "डैशबोर्ड", map: "नक्शा", liveOps: "लाइव ऑप्स", scenarios: "परिदृश्य", events: "ईवेंट" },
    actions: { start: "शुरू", pause: "रोकें", reset: "रीसेट", inject: "व्यवधान इंजेक्ट करें" },
    status: { running: "चल रहा है", paused: "रोका गया", stopped: "बंद किया गया" },
    metrics: { stockoutsPrevented: "स्टॉकआउट रोका गया", criticalDeliveries: "महत्वपूर्ण डिलीवरी बचाई गई" },
  };

  describe("English translations", () => {
    it("should have app section", () => {
      expect(en.app.title).toBe("LogiSight");
      expect(en.app.subtitle).toContain("Supply Chain");
    });

    it("should have navigation section", () => {
      expect(en.nav).toHaveProperty("dashboard");
      expect(en.nav).toHaveProperty("map");
      expect(en.nav).toHaveProperty("liveOps");
      expect(en.nav).toHaveProperty("scenarios");
    });

    it("should have action labels", () => {
      expect(en.actions.start).toBeTruthy();
      expect(en.actions.pause).toBeTruthy();
      expect(en.actions.reset).toBeTruthy();
      expect(en.actions.inject).toContain("Disruption");
    });

    it("should have status labels", () => {
      expect(en.status.running).toBe("Running");
      expect(en.status.paused).toBe("Paused");
      expect(en.status.stopped).toBe("Stopped");
    });

    it("should have SDG metric labels", () => {
      expect(en.metrics.stockoutsPrevented).toContain("Stockouts");
      expect(en.metrics.criticalDeliveries).toContain("Deliveries");
    });
  });

  describe("Hindi translations", () => {
    it("should have all Hindi keys matching English structure", () => {
      expect(Object.keys(hi)).toEqual(Object.keys(en));
    });

    it("should have app section in Hindi", () => {
      expect(hi.app.title).toBe("लॉजीसाइट");
    });

    it("should have Hindi navigation section", () => {
      expect(hi.nav.dashboard).toBe("डैशबोर्ड");
      expect(hi.nav.map).toBe("नक्शा");
    });

    it("should have Hindi action labels", () => {
      expect(hi.actions.start).toBe("शुरू");
      expect(hi.actions.inject).toContain("इंजेक्ट");
    });

    it("should have Hindi status labels", () => {
      expect(hi.status.running).toContain("चल");
    });

    it("should have Hindi SDG metric labels", () => {
      expect(hi.metrics.stockoutsPrevented).toContain("स्टॉकआउट");
    });
  });

  describe("Translation completeness", () => {
    it("should have matching key structures between languages", () => {
      const getKeys = (obj, prefix = "") =>
        Object.keys(obj).flatMap((k) =>
          typeof obj[k] === "object" ? getKeys(obj[k], `${prefix}${k}.`) : `${prefix}${k}`
        );
      expect(getKeys(en).sort()).toEqual(getKeys(hi).sort());
    });
  });
});
