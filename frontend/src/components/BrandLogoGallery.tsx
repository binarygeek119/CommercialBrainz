import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type AdvertiserLogo } from "../api";
import { useAuth, canSubmit } from "../auth";
import BrandLogoMetadataForm from "./BrandLogoMetadataForm";

interface Props {
  advertiserSbid: string;
  brandName: string;
}

function LogoCard({
  logo,
  advertiserSbid,
  canVote,
  canEditMetadata,
  onVoted,
}: {
  logo: AdvertiserLogo;
  advertiserSbid: string;
  canVote: boolean;
  canEditMetadata: boolean;
  onVoted: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showMetadataForm, setShowMetadataForm] = useState(false);

  const castVote = async (choice: "up" | "down" | null) => {
    setLoading(true);
    setError("");
    try {
      await api.voteAdvertiserLogoPopularity(advertiserSbid, logo.id, choice);
      onVoted();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="card"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "0.65rem",
        border: logo.is_main ? "2px solid var(--accent, #6cf)" : undefined,
      }}
    >
      <div
        style={{
          background:
            "repeating-conic-gradient(#ccc 0% 25%, #fff 0% 50%) 50% / 12px 12px",
          padding: "0.75rem",
          borderRadius: 4,
          display: "flex",
          justifyContent: "center",
          minHeight: 120,
        }}
      >
        <img
          src={logo.image_url}
          alt={logo.context_label}
          style={{ maxWidth: "100%", maxHeight: 140, objectFit: "contain" }}
        />
      </div>
      <div>
        <strong style={{ fontSize: "0.95rem" }}>{logo.context_label}</strong>
        {logo.is_main && (
          <span
            className="muted"
            style={{ marginLeft: "0.5rem", fontSize: "0.8rem", fontWeight: 600 }}
          >
            Main logo
          </span>
        )}
        {logo.notes && (
          <p className="muted" style={{ margin: "0.35rem 0 0", fontSize: "0.85rem" }}>
            {logo.notes}
          </p>
        )}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
        <span className="muted" style={{ fontSize: "0.85rem" }}>
          Popularity: {logo.popularity_score > 0 ? "+" : ""}
          {logo.popularity_score}
        </span>
        {canVote && (
          <>
            <button
              type="button"
              className={`btn btn-secondary${logo.viewer_vote === "up" ? " active" : ""}`}
              disabled={loading}
              onClick={() => castVote(logo.viewer_vote === "up" ? null : "up")}
              style={{ padding: "0.2rem 0.55rem", fontSize: "0.85rem" }}
            >
              ▲ Up
            </button>
            <button
              type="button"
              className={`btn btn-secondary${logo.viewer_vote === "down" ? " active" : ""}`}
              disabled={loading}
              onClick={() => castVote(logo.viewer_vote === "down" ? null : "down")}
              style={{ padding: "0.2rem 0.55rem", fontSize: "0.85rem" }}
            >
              ▼ Down
            </button>
          </>
        )}
      </div>
      {canEditMetadata && (
        <>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ padding: "0.25rem 0.65rem", fontSize: "0.85rem", alignSelf: "flex-start" }}
            onClick={() => setShowMetadataForm((open) => !open)}
          >
            {showMetadataForm ? "Hide metadata editor" : "Edit metadata"}
          </button>
          {showMetadataForm && (
            <BrandLogoMetadataForm
              advertiserSbid={advertiserSbid}
              logo={logo}
              onSubmitted={onVoted}
            />
          )}
        </>
      )}
      {error && <p className="error" style={{ fontSize: "0.85rem" }}>{error}</p>}
    </div>
  );
}

export default function BrandLogoGallery({ advertiserSbid, brandName }: Props) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const { data: logos = [], isLoading, error } = useQuery({
    queryKey: ["advertiser-logos", advertiserSbid],
    queryFn: () => api.getAdvertiserLogos(advertiserSbid),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["advertiser-logos", advertiserSbid] });
    queryClient.invalidateQueries({ queryKey: ["advertiser", advertiserSbid] });
  };

  if (isLoading) return <p className="muted">Loading logos…</p>;
  if (error) return <p className="error">{(error as Error).message}</p>;
  if (!logos.length) return null;

  return (
    <section style={{ marginTop: "1.5rem" }}>
      <h2>Logo versions</h2>
      <p className="muted" style={{ marginBottom: "1rem" }}>
        {brandName} can have many logos for different years, campaigns, and anniversaries. The{" "}
        <strong>main logo</strong> shown across the site is whichever version has the highest net
        popularity score from community votes.
      </p>
      <div className="grid grid-2">
        {logos.map((logo) => (
          <LogoCard
            key={logo.id}
            logo={logo}
            advertiserSbid={advertiserSbid}
            canVote={!!user}
            canEditMetadata={!!user && canSubmit(user)}
            onVoted={refresh}
          />
        ))}
      </div>
      {!user && (
        <p className="muted" style={{ marginTop: "0.75rem" }}>
          <a href="/login">Log in</a> to vote on which logo should be main.
        </p>
      )}
    </section>
  );
}
