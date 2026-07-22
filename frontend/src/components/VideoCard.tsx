import { Link } from "react-router-dom";
import { type Video } from "../api";
import { formatRegionDisplay } from "../data/regions";
import { commercialUrl } from "../utils/commercialUrls";
import { formatDurationMs } from "../utils/youtube";
import { videoDisplayTitle } from "../utils/videoMetadata";
import { videoThumbnailUrl } from "../utils/videoThumbnail";

export default function VideoCard({ video }: { video: Video }) {
  const thumb = videoThumbnailUrl(video);
  const title = videoDisplayTitle(video);
  const duration = formatDurationMs(video.duration_ms);
  const region = formatRegionDisplay(video.region, video.sub_region);
  const typeMeta =
    video.commercial_type === "bumper" && video.bumper_channel
      ? video.bumper_channel
      : null;
  const meta = [typeMeta, video.channel_name, video.language, region].filter(Boolean);

  return (
    <Link to={commercialUrl(video.commercial_id, video.sbid)} className="video-card">
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
