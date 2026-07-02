import { Link } from "react-router-dom";
import { type Video } from "../api";
import { formatRegionDisplay } from "../data/regions";
import { formatDurationMs } from "../utils/youtube";
import { videoThumbnailUrl } from "../utils/videoThumbnail";

export default function VideoCard({ video }: { video: Video }) {
  const thumb = videoThumbnailUrl(video);
  const title = video.slogan || video.youtube_id || "Untitled";
  const duration = formatDurationMs(video.duration_ms);
  const region = formatRegionDisplay(video.region, video.sub_region);
  const meta = [video.channel_name, video.language, region].filter(Boolean);

  return (
    <Link to={`/video/${video.sbid}`} className="video-card">
      <div className="video-card-thumb">
        {thumb ? (
          <img src={thumb} alt="" loading="lazy" />
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
