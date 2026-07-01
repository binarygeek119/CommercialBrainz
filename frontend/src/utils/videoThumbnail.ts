/** Resolve a display thumbnail for a video record. */

type ThumbnailSource = {
  thumbnail_url?: string | null;
  youtube_id?: string | null;
  metadata?: Record<string, unknown> | null;
};

export function videoThumbnailUrl(video: ThumbnailSource): string | null {
  if (video.thumbnail_url) return video.thumbnail_url;
  const fromMeta = video.metadata?.youtube_thumbnail;
  if (typeof fromMeta === "string" && fromMeta) return fromMeta;
  if (video.youtube_id) {
    return `https://i.ytimg.com/vi/${video.youtube_id}/hqdefault.jpg`;
  }
  return null;
}

export function youtubeIdThumbnail(youtubeId: string, quality = "hqdefault"): string {
  return `https://i.ytimg.com/vi/${youtubeId}/${quality}.jpg`;
}
