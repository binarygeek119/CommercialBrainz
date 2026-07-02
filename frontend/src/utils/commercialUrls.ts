/** URLs for the unified commercial + video view. */

export function commercialUrl(commercialId: string, videoId?: string | null): string {
  const base = `/commercial/${encodeURIComponent(commercialId)}`;
  if (!videoId) return base;
  return `${base}?video=${encodeURIComponent(videoId)}`;
}
