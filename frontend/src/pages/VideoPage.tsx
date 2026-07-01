import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";

export default function VideoPage() {
  const { sbid } = useParams<{ sbid: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["video", sbid],
    queryFn: () => api.getVideo(sbid!),
    enabled: !!sbid,
  });

  if (isLoading) return <p className="muted">Loading...</p>;
  if (error) return <p className="error">{(error as Error).message}</p>;
  if (!data) return null;

  return (
    <div>
      <h1 className="page-title">{data.commercial?.title || data.slogan || "Video"}</h1>

      {data.youtube_url && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <a href={data.youtube_url} target="_blank" rel="noreferrer">
            Watch on YouTube ({data.youtube_id})
          </a>
        </div>
      )}

      {data.visibility !== "public" && (
        <p className="error">This video link is not publicly available ({data.visibility}).</p>
      )}

      <div className="grid grid-2">
        <div className="card">
          <h3>Details</h3>
          {data.advertiser && (
            <p>
              Advertiser:{" "}
              <Link to={`/advertiser/${data.advertiser.sbid}`}>{data.advertiser.name}</Link>
            </p>
          )}
          {data.commercial && (
            <p>
              Commercial:{" "}
              <Link to={`/commercial/${data.commercial.sbid}`}>{data.commercial.title}</Link>
            </p>
          )}
          {data.language && <p>Language: {data.language}</p>}
          {data.region && <p>Region: {data.region}</p>}
          {data.duration_ms && <p>Duration: {Math.round(data.duration_ms / 1000)}s</p>}
          {data.slogan && <p>Slogan: {data.slogan}</p>}
        </div>

        <div className="card">
          <h3>Tags & Credits</h3>
          {data.tags && data.tags.length > 0 && (
            <p>{data.tags.map((t) => `#${t}`).join(" ")}</p>
          )}
          {data.credits && data.credits.map((c, i) => (
            <p key={i} className="muted">
              {c.role}: {c.name}
            </p>
          ))}
        </div>
      </div>

      {data.transcript && (
        <div className="card">
          <h3>Transcript</h3>
          <p>{data.transcript}</p>
        </div>
      )}

      <p style={{ marginTop: "1rem" }}>
        <Link to={`/dmca?video=${data.sbid}`}>Report DMCA takedown</Link>
      </p>
    </div>
  );
}
