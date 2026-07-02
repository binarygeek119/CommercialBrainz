import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { useAuth, canSubmit } from "../auth";
import CommercialMetadataForm from "../components/CommercialMetadataForm";
import CommercialMetadataDisplay from "../components/CommercialMetadataDisplay";
import CommercialVideoGallery from "../components/CommercialVideoGallery";

export default function CommercialPage() {
  const { sbid } = useParams<{ sbid: string }>();
  const { user } = useAuth();
  const [showMetadataForm, setShowMetadataForm] = useState(false);
  const { data, isLoading, error } = useQuery({
    queryKey: ["commercial", sbid],
    queryFn: () => api.getCommercial(sbid!),
    enabled: !!sbid,
  });

  if (isLoading) return <p className="muted">Loading...</p>;
  if (error) return <p className="error">{(error as Error).message}</p>;
  if (!data) return null;

  return (
    <div>
      <div className="flex-between" style={{ alignItems: "flex-start", gap: "1rem", flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <h1 className="page-title" style={{ marginTop: 0 }}>
            {data.title}
          </h1>
          {data.campaign_name && data.campaign_name !== data.title && (
            <p className="muted">{data.campaign_name}</p>
          )}
        </div>
        {user && canSubmit(user) && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setShowMetadataForm((open) => !open)}
          >
            {showMetadataForm ? "Hide metadata editor" : "Edit metadata"}
          </button>
        )}
      </div>

      <CommercialMetadataDisplay commercial={data} />

      {showMetadataForm && user && canSubmit(user) && (
        <CommercialMetadataForm commercial={data} />
      )}

      {!user && (
        <p className="muted" style={{ marginTop: "0.75rem" }}>
          <a href="/login">Log in</a> and unlock submit access to propose metadata edits.
        </p>
      )}

      <CommercialVideoGallery commercial={data} />
    </div>
  );
}
