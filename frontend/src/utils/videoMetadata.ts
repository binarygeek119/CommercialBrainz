import { formatDurationMs } from "./youtube";
import { formatRegionDisplay } from "../data/regions";
import { formatSubmissionGenres, type SubmissionGenres } from "./submissionGenres";
import type { Video } from "../api";

export const VIDEO_DETAIL_FIELDS = [
  { key: "version_label", label: "Version label" },
  { key: "sbid", label: "Video ID" },
  { key: "youtube_id", label: "YouTube ID" },
  { key: "youtube_url", label: "YouTube URL" },
  { key: "channel_name", label: "Channel" },
  { key: "upload_date", label: "Upload date" },
  { key: "duration_ms", label: "Duration" },
  { key: "aspect_ratio", label: "Aspect ratio" },
  { key: "resolution", label: "Resolution" },
  { key: "language", label: "Language" },
  { key: "region", label: "Region" },
  { key: "market", label: "Market" },
  { key: "first_aired_date", label: "First aired" },
  { key: "last_aired_date", label: "Last aired" },
  { key: "network", label: "Network" },
  { key: "slogan", label: "Slogan" },
  { key: "cta_text", label: "Call to action" },
  { key: "transcript", label: "Transcript" },
  { key: "visibility", label: "Visibility" },
  { key: "hash_status", label: "Fingerprint status" },
  { key: "phash", label: "pHash" },
  { key: "file_sha256", label: "SHA256" },
  { key: "audio_fingerprint", label: "Chromaprint" },
  { key: "hashed_at", label: "Fingerprinted at" },
  { key: "created_at", label: "Added to archive" },
  { key: "updated_at", label: "Last updated" },
] as const;

function formatDate(value: string | null | undefined): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export function getVideoFieldValue(video: Video, key: string): unknown {
  if (key === "region") {
    return formatRegionDisplay(video.region, video.sub_region) || null;
  }
  if (key === "duration_ms") {
    return video.duration_ms ? formatDurationMs(video.duration_ms) : null;
  }
  if (key === "upload_date" || key === "first_aired_date" || key === "last_aired_date") {
    return formatDate(video[key as keyof Video] as string | null | undefined);
  }
  if (key === "hashed_at" || key === "created_at" || key === "updated_at") {
    return formatDate(video[key as keyof Video] as string | null | undefined);
  }
  if (key === "audio_fingerprint" && video.audio_fingerprint) {
    const value = video.audio_fingerprint;
    return value.length > 80 ? `${value.slice(0, 80)}…` : value;
  }
  return video[key as keyof Video];
}

export function videoHasFieldValue(video: Video, key: string): boolean {
  const value = getVideoFieldValue(video, key);
  return value != null && value !== "";
}

export function videoMetadataExtras(video: Video): { label: string; value: string }[] {
  const extras: { label: string; value: string }[] = [];
  const metadata = video.metadata ?? {};
  const genres = formatSubmissionGenres(metadata.genres as SubmissionGenres | undefined);
  for (const line of genres) {
    extras.push({ label: "Genre", value: line });
  }

  for (const [key, raw] of Object.entries(metadata)) {
    if (key === "genres" || key === "youtube_thumbnail" || key === "hash_error") continue;
    if (raw == null || raw === "") continue;
    extras.push({
      label: key.replace(/_/g, " "),
      value: typeof raw === "object" ? JSON.stringify(raw) : String(raw),
    });
  }

  return extras;
}

export function videoDisplayTitle(video: Video): string {
  return (
    video.link_label ||
    video.version_label ||
    video.slogan ||
    video.youtube_id ||
    "Untitled video"
  );
}
