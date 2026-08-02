import { useEffect, useState } from "react";
import { Link } from "react-router";
import { type Video } from "../api";
import { formatRegionDisplay } from "../data/regions";
import { commercialUrl } from "../utils/commercialUrls";
import { formatDurationMs } from "../utils/youtube";
import { videoDisplayTitle } from "../utils/videoMetadata";
import {
  bustHostedThumbnailUrl,
  nextYoutubeThumbnailFallback,
  thumbnailFetchRequestedAt,
  videoThumbnailUrl,
} from "../utils/videoThumbnail";

export default function VideoCard({ video }: { video: Video }) {
  const requestedAt = thumbnailFetchRequestedAt(video.metadata ?? null);
  const resolved = bustHostedThumbnailUrl(videoThumbnailUrl(video), requestedAt);
  const [thumb, setThumb] = useState<string | null>(resolved);
  const title = videoDisplayTitle(video);
  const duration = formatDurationMs(video.duration_ms);
  const region = formatRegionDisplay(video.region, video.sub_region);
  const typeMeta =
    video.commercial_type === "bumper" && video.bumper_channel
      ? video.bumper_channel
      : null;
  const meta = [typeMeta, video.channel_name, video.language, region].filter(Boolean);

  useEffect(() => {
    setThumb(bustHostedThumbnailUrl(videoThumbnailUrl(video), requestedAt));
  }, [video.thumbnail_url, video.youtube_id, video.metadata, requestedAt]);

  return (
    <Link to={commercialUrl(video.commercial_id, video.sbid)} className="video-card">
      <div className="video-card-thumb">
        {thumb ? (
          <img
            src={thumb}
            alt=""
            loading="lazy"
            onError={() => {
              // Hosted path 404 → try YouTube CDN qualities; then clear.
              if (thumb.startsWith("/api/")) {
                const yt = video.youtube_id
                  ? `https://i.ytimg.com/vi/${video.youtube_id}/maxresdefault.jpg`
                  : null;
                setThumb(yt);
                return;
              }
              const next = nextYoutubeThumbnailFallback(thumb, video.youtube_id);
              setThumb(next);
            }}
          />
        ) : (
          <div className="video-card-thumb-placeholder" aria-hidden />
        )}
        {duration && <span className="video-card-duration">{duration}</span>}
      </div>
      <div className="video-card-info">
        <h3 className="video-card-title">{title}</h3>
        {meta.length > 0 && <p className="video-card-meta">{meta.join(" · ")}</p>}
      </div>
    </Link>
  );
}
