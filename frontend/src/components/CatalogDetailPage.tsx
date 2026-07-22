import { useParams, Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useAuth, canSubmit } from "../auth";
import BrandLogoImage from "./BrandLogoImage";
import CatalogLogoGallery from "./CatalogLogoGallery";
import CatalogLogoUpload from "./CatalogLogoUpload";
import CatalogMetadataDisplay from "./CatalogMetadataDisplay";
import CatalogMetadataForm from "./CatalogMetadataForm";
import type { CatalogKindConfig } from "../catalog/kinds";

export default function CatalogDetailPage({ kind }: { kind: CatalogKindConfig }) {
  const { sbid } = useParams<{ sbid: string }>();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: [kind.key, sbid],
    queryFn: () => api.getCatalog(kind.key, sbid!),
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
          <BrandLogoImage src={data.logo_url} alt={`${data.name} logo`} size="md" />
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

      <CatalogMetadataDisplay kind={kind} entity={data} />

      <CatalogLogoGallery kind={kind} entitySbid={sbid!} entityName={data.name} />

      {user && canSubmit(user) && sbid && (
        <>
          <CatalogMetadataForm kind={kind} entity={data} />
          <CatalogLogoUpload
            kind={kind}
            entitySbid={sbid}
            entityName={data.name}
            onSubmitted={() => {
              queryClient.invalidateQueries({ queryKey: [`${kind.key}-logos`, sbid] });
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
        {!commercials.length && (
          <p className="muted">No linked commercials yet.</p>
        )}
      </div>
    </div>
  );
}
