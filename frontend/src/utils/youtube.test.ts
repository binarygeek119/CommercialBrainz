import { describe, expect, it } from "vitest";
import { extractYouTubeId, formatDurationMs } from "./youtube";

describe("extractYouTubeId", () => {
  it("accepts a bare 11-character id", () => {
    expect(extractYouTubeId("dQw4w9WgXcQ")).toBe("dQw4w9WgXcQ");
  });

  it("parses watch, youtu.be, and shorts URLs", () => {
    expect(extractYouTubeId("https://www.youtube.com/watch?v=dQw4w9WgXcQ")).toBe(
      "dQw4w9WgXcQ",
    );
    expect(extractYouTubeId("https://youtu.be/dQw4w9WgXcQ")).toBe("dQw4w9WgXcQ");
    expect(extractYouTubeId("https://www.youtube.com/shorts/dQw4w9WgXcQ")).toBe(
      "dQw4w9WgXcQ",
    );
  });

  it("returns null for invalid input", () => {
    expect(extractYouTubeId("")).toBeNull();
    expect(extractYouTubeId("not-a-url")).toBeNull();
    expect(extractYouTubeId("https://example.com/watch?v=dQw4w9WgXcQ")).toBeNull();
  });
});

describe("formatDurationMs", () => {
  it("formats seconds and hours", () => {
    expect(formatDurationMs(65_000)).toBe("1:05");
    expect(formatDurationMs(3_661_000)).toBe("1:01:01");
  });

  it("returns empty for missing or non-positive values", () => {
    expect(formatDurationMs(null)).toBe("");
    expect(formatDurationMs(0)).toBe("");
  });
});
