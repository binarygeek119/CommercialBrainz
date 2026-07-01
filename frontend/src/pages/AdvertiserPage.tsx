import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

export default function AdvertiserPage() {
  const { sbid } = useParams<{ sbid: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["advertiser", sbid],
    queryFn: () => fetch(`/api/v1/advertisers/${sbid}`, {
      headers: { "User-Agent": "CommercialBrainz-Web/0.1.0" },
    }).then((r) => r.json()),
    enabled: !!sbid,
  });

  if (isLoading) return <p className="muted">Loading...</p>;
  if (error) return <p className="error">{(error as Error).message}</p>;

  const commercials = (data?.commercials as { sbid: string; title: string }[]) || [];

  return (
    <div>
      <h1 className="page-title">{data?.name}</h1>
      {data?.description && <p className="muted">{data.description}</p>}

      <h2 style={{ marginTop: "1.5rem" }}>Commercials</h2>
      <div className="stack">
        {commercials.map((c) => (
          <a key={c.sbid} href={`/commercial/${c.sbid}`} className="card" style={{ textDecoration: "none", color: "inherit" }}>
            {c.title}
          </a>
        ))}
      </div>
    </div>
  );
}
