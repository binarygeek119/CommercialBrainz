import { useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth, canSubmit } from "../auth";
import BrandLogoUpload from "../components/BrandLogoUpload";
import BrandLogoGallery from "../components/BrandLogoGallery";
import BrandMetadataDisplay from "../components/BrandMetadataDisplay";
import BrandMetadataForm from "../components/BrandMetadataForm";

export default function AdvertiserPage() {
  const { sbid } = useParams<{ sbid: string }>();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["advertiser", sbid],
    queryFn: () => api.getAdvertiser(sbid!),
    enabled: !!sbid,
  });

  if (isLoading) return <p className="muted">Loading...</p>;
  if (error) return <p className="error">{(error as Error).message}</p>;
  if (!data) return null;

  const commercials = (data.commercials as { sbid: string; title: string }[]) || [];

  return (
    <div>
      <div style={{ display: "flex", gap: "1.25rem", alignItems: "flex-start", flexWrap: "wrap" }}>
        {data.logo_url && (
          <div
            style={{
              background:
                "repeating-conic-gradient(#ccc 0% 25%, #fff 0% 50%) 50% / 16px 16px",
              padding: "0.75rem",
              borderRadius: 4,
            }}
          >
            <img
              src={data.logo_url}
              alt={`${data.name} logo`}
              style={{ maxWidth: 160, maxHeight: 160, display: "block" }}
            />
          </div>
        )}
        <div style={{ flex: 1, minWidth: 200 }}>
          <h1 className="page-title" style={{ marginTop: 0 }}>
            {data.name}
          </h1>
          {data.metadata?.tagline && (
            <p style={{ fontStyle: "italic", marginTop: "-0.25rem" }}>{data.metadata.tagline}</p>
          )}
        </div>
      </div>

      <BrandMetadataDisplay brand={data} />

      <BrandLogoGallery advertiserSbid={sbid!} brandName={data.name} />

      {user && canSubmit(user) && sbid && (
        <>
          <BrandMetadataForm advertiser={data} />
          <BrandLogoUpload
            advertiserSbid={sbid}
            brandName={data.name}
            onSubmitted={() => {
              queryClient.invalidateQueries({ queryKey: ["advertiser-logos", sbid] });
            }}
          />
        </>
      )}

      <h2 style={{ marginTop: "1.5rem" }}>Commercials</h2>
      <div className="stack">
        {commercials.map((c) => (
          <Link
            key={c.sbid}
            to={`/commercial/${c.sbid}`}
            className="card"
            style={{ textDecoration: "none", color: "inherit" }}
          >
            {c.title}
          </Link>
        ))}
      </div>
    </div>
  );
}
