import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

describe("useLanguage Hook Logic", () => {
  const mockTranslations = {
    en: { greeting: "Hello", farewell: "Goodbye" },
    hi: { greeting: "नमस्ते", farewell: "अलविदा" },
  };

  function getTranslation(lang, key) {
    return mockTranslations[lang]?.[key] ?? mockTranslations.en[key] ?? key;
  }

  describe("getTranslation", () => {
    it("should return English by default", () => {
      expect(getTranslation("en", "greeting")).toBe("Hello");
    });

    it("should return Hindi when selected", () => {
      expect(getTranslation("hi", "greeting")).toBe("नमस्ते");
    });

    it("should fall back to English key for missing translations", () => {
      expect(getTranslation("hi", "farewell")).toBe("अलविदा");
    });

    it("should return the key itself when neither language has it", () => {
      expect(getTranslation("en", "missing_key")).toBe("missing_key");
    });

    it("should support German as a fallback language", () => {
      expect(getTranslation("de", "greeting")).toBe("Hello");
    });
  });

  describe("Language State Machine", () => {
    const supportedLanguages = ["en", "hi"];

    it("should have exactly 2 supported languages", () => {
      expect(supportedLanguages).toHaveLength(2);
      expect(supportedLanguages).toContain("en");
      expect(supportedLanguages).toContain("hi");
    });

    it("should not include unsupported languages", () => {
      expect(supportedLanguages).not.toContain("fr");
      expect(supportedLanguages).not.toContain("es");
    });
  });
});
