/** Client-side YouTube URL helpers (mirrors backend extract_youtube_id). */

const ID_RE = /^[\w-]{11}$/;

export function extractYouTubeId(urlOrId: string): string | null {
  const value = urlOrId.trim();
  if (!value) return null;
  if (ID_RE.test(value)) return value;

  try {
    const parsed = new URL(value);
    const host = parsed.hostname.replace(/^www\./, "");
    if (host === "youtu.be") {
      const id = parsed.pathname.slice(1).split("/")[0];
      return ID_RE.test(id) ? id : null;
    }
    if (host === "youtube.com" || host === "m.youtube.com") {
      if (parsed.pathname === "/watch") {
        const id = parsed.searchParams.get("v");
        return id && ID_RE.test(id) ? id : null;
      }
      const match = parsed.pathname.match(/^\/(embed|v|shorts)\/([\w-]{11})/);
      if (match) return match[2];
    }
  } catch {
    return null;
  }
  return null;
}

export function formatDurationMs(ms: number | null | undefined): string {
  if (!ms || ms <= 0) return "";
  const totalSec = Math.round(ms / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${m}:${String(s).padStart(2, "0")}`;
}
