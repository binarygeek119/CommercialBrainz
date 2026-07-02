import { Link } from "react-router-dom";
import type { Video } from "../api";
import { videoThumbnailUrl } from "../utils/videoThumbnail";
import { formatDurationMs } from "../utils/youtube";
import {
  VIDEO_DETAIL_FIELDS,
  getVideoFieldValue,
  videoDisplayTitle,
  videoHasFieldValue,
  videoMetadataExtras,
} from "../utils/videoMetadata";

function renderVideoField(video: Video, key: string) {
  const value = getVideoFieldValue(video, key);
  if (value == null || value === "") return null;

  if (key === "sbid") {
    return <span className="mono">{String(value)}</span>;
  }
  if (key === "youtube_url" && video.youtube_url) {
    return (
      <a href={video.youtube_url} target="_blank" rel="noreferrer noopener">
        {video.youtube_url}
      </a>
    );
  }
  if (key === "youtube_id" && video.youtube_url) {
    return (
      <a href={video.youtube_url} target="_blank" rel="noreferrer noopener">
        {String(value)}
      </a>
    );
  }
  if (key === "phash" || key === "file_sha256" || key === "audio_fingerprint") {
    return <span className="mono">{String(value)}</span>;
  }
  if (key === "transcript") {
    return <span style={{ whiteSpace: "pre-wrap" }}>{String(value)}</span>;
  }
  return String(value);
}

export default function CommercialVideoEntry({ video }: { video: Video }) {
  const thumb = videoThumbnailUrl(video);
  const title = videoDisplayTitle(video);
  const duration = formatDurationMs(video.duration_ms);
  const rows = VIDEO_DETAIL_FIELDS.filter(({ key }) => videoHasFieldValue(video, key));
  const extras = videoMetadataExtras(video);

  return (
    <article
      className="commercial-video-entry card"
      style={{
        border: video.is_main ? "2px solid var(--accent)" : undefined,
      }}
    >
      <Link to={`/video/${video.sbid}`} className="commercial-video-entry-thumb">
        {thumb ? (
          <img src={thumb} alt="" loading="lazy" />
        ) : (
          <div className="video-card-thumb-placeholder" aria-hidden />
        )}
        {duration && <span className="video-card-duration">{duration}</span>}
      </Link>

      <div className="commercial-video-entry-body">
        <h3 style={{ margin: "0 0 0.75rem" }}>
          <Link to={`/video/${video.sbid}`}>{title}</Link>
          {video.is_main && (
            <span className="badge badge-open" style={{ marginLeft: "0.5rem", textTransform: "none" }}>
              Main link
            </span>
          )}
        </h3>

        <dl className="metadata-list">
          {rows.map(({ key, label }) => {
            const rendered = renderVideoField(video, key);
            if (!rendered) return null;
            return (
              <div key={key} className="metadata-row">
                <dt className="muted">{label}</dt>
                <dd>{rendered}</dd>
              </div>
            );
          })}
          {extras.map(({ label, value }) => (
            <div key={`${label}-${value}`} className="metadata-row">
              <dt className="muted">{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </div>
    </article>
  );
}
