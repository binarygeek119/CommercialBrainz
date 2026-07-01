import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";

export default function BrowsePage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["browse"],
    queryFn: () => api.browseVideos(),
  });

  if (isLoading) return <p className="muted">Loading...</p>;
  if (error) return <p className="error">{(error as Error).message}</p>;

  return (
    <div>
      <h1 className="page-title">Browse Videos</h1>
      <div className="grid grid-2">
        {data?.items.map((video) => (
          <Link key={video.sbid} to={`/video/${video.sbid}`} className="card" style={{ textDecoration: "none", color: "inherit" }}>
            <h3>{video.slogan || video.youtube_id || "Untitled"}</h3>
            <p className="muted">
              {video.language && `${video.language} · `}
              {video.region && `${video.region} · `}
              {video.duration_ms && `${Math.round(video.duration_ms / 1000)}s`}
            </p>
            {video.youtube_id && (
              <p className="mono muted">{video.youtube_id}</p>
            )}
          </Link>
        ))}
      </div>
      {data?.items.length === 0 && (
        <p className="muted">No videos yet. Be the first to submit one!</p>
      )}
    </div>
  );
}
