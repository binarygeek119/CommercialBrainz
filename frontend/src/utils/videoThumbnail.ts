/** Resolve a display thumbnail for a video record. */

type ThumbnailSource = {
  thumbnail_url?: string | null;
  youtube_id?: string | null;
  metadata?: Record<string, unknown> | null;
};

const YT_CDN_QUALITIES = ["maxresdefault", "sddefault", "hqdefault", "mqdefault", "default"] as const;

export function videoThumbnailUrl(video: ThumbnailSource): string | null {
  if (video.thumbnail_url) return video.thumbnail_url;
  const fromMeta = video.metadata?.youtube_thumbnail;
  if (typeof fromMeta === "string" && fromMeta) return fromMeta;
  if (video.youtube_id) {
    return `https://i.ytimg.com/vi/${video.youtube_id}/hqdefault.jpg`;
  }
  return null;
}

/** Append a cache-bust query for hosted thumbs after a force re-grab. */
export function bustHostedThumbnailUrl(
  url: string | null,
  version: string | null | undefined,
): string | null {
  if (!url) return null;
  if (!version || !url.startsWith("/api/")) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}t=${encodeURIComponent(version)}`;
}

export function thumbnailFetchRequestedAt(
  metadata: Record<string, unknown> | null | undefined,
): string | null {
  const raw = metadata?.thumbnail_fetch;
  if (!raw || typeof raw !== "object") return null;
  const requested = (raw as { requested_at?: unknown }).requested_at;
  return typeof requested === "string" ? requested : null;
}

export function youtubeIdThumbnail(youtubeId: string, quality = "hqdefault"): string {
  return `https://i.ytimg.com/vi/${youtubeId}/${quality}.jpg`;
}

/** Next YouTube CDN quality URL after a load failure, or null when exhausted. */
export function nextYoutubeThumbnailFallback(
  failedUrl: string,
  youtubeId: string | null | undefined,
): string | null {
  if (!youtubeId) return null;
  const current = YT_CDN_QUALITIES.findIndex((q) => failedUrl.includes(`/${q}.jpg`));
  const start = current >= 0 ? current + 1 : 0;
  for (let i = start; i < YT_CDN_QUALITIES.length; i++) {
    const next = youtubeIdThumbnail(youtubeId, YT_CDN_QUALITIES[i]);
    if (next !== failedUrl) return next;
  }
  return null;
}
