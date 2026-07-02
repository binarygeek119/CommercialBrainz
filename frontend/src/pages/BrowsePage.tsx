import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { formatRegionDisplay } from "../data/regions";
import { commercialUrl } from "../utils/commercialUrls";
import { videoThumbnailUrl } from "../utils/videoThumbnail";

export default function BrowsePage() {  const { data, isLoading, error } = useQuery({
    queryKey: ["browse"],
    queryFn: () => api.browseVideos(),
  });

  if (isLoading) return <p className="muted">Loading...</p>;
  if (error) return <p className="error">{(error as Error).message}</p>;

  return (
    <div>
      <h1 className="page-title">Browse Videos</h1>
      <div className="grid grid-2">
        {data?.items.map((video) => {
          const thumb = videoThumbnailUrl(video);
          return (
          <Link key={video.sbid} to={commercialUrl(video.commercial_id, video.sbid)} className="card" style={{ textDecoration: "none", color: "inherit" }}>
            {thumb && (
              <img
                src={thumb}
                alt=""
                style={{
                  width: "100%",
                  aspectRatio: "16 / 9",
                  objectFit: "cover",
                  borderRadius: 4,
                  marginBottom: "0.75rem",
                }}
              />
            )}
            <h3>{video.slogan || video.youtube_id || "Untitled"}</h3>            <p className="muted">
              {video.language && `${video.language} · `}
              {formatRegionDisplay(video.region, video.sub_region) &&
                `${formatRegionDisplay(video.region, video.sub_region)} · `}
              {video.duration_ms && `${Math.round(video.duration_ms / 1000)}s`}
            </p>
            {video.youtube_id && (
              <p className="mono muted">{video.youtube_id}</p>
            )}
          </Link>
          );
        })}      </div>
      {data?.items.length === 0 && (
        <p className="muted">No videos yet. Be the first to submit one!</p>
      )}
    </div>
  );
}
