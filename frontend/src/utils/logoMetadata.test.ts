import { describe, expect, it } from "vitest";
import { formatLogoFieldValue, logoFieldLabel } from "./logoMetadata";

describe("logoFieldLabel", () => {
  it("returns known labels and falls back for unknown keys", () => {
    expect(logoFieldLabel("year")).toBe("Year");
    expect(logoFieldLabel("custom_key")).toBe("custom key");
  });
});

describe("formatLogoFieldValue", () => {
  it("formats months and empty values", () => {
    expect(formatLogoFieldValue("month", 3)).toBe("March");
    expect(formatLogoFieldValue("notes", "")).toBe("—");
    expect(formatLogoFieldValue("label", "Primary")).toBe("Primary");
  });
});
