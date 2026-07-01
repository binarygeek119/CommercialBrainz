import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";

export default function CommercialPage() {
  const { sbid } = useParams<{ sbid: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["commercial", sbid],
    queryFn: () => api.getCommercial(sbid!),
    enabled: !!sbid,
  });

  if (isLoading) return <p className="muted">Loading...</p>;
  if (error) return <p className="error">{(error as Error).message}</p>;
  if (!data) return null;

  const videos = (data.videos as { sbid: string; youtube_id: string | null; slogan: string | null }[]) || [];

  const title = data.title as string;
  const description = data.description as string | undefined;
  const year = data.year as number | undefined;

  return (
    <div>
      <h1 className="page-title">{title}</h1>
      {description && <p className="muted">{description}</p>}
      {year && <p>Year: {year}</p>}

      <h2 style={{ marginTop: "1.5rem" }}>Videos</h2>
      <div className="stack">
        {videos.map((v) => (
          <Link key={v.sbid} to={`/video/${v.sbid}`} className="card" style={{ textDecoration: "none", color: "inherit" }}>
            {v.slogan || v.youtube_id || v.sbid}
          </Link>
        ))}
        {videos.length === 0 && <p className="muted">No public videos linked.</p>}
      </div>
    </div>
  );
}
