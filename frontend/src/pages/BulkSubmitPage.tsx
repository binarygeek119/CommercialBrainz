import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useAuth } from "../auth";

export default function BulkSubmitPage() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [playlistUrl, setPlaylistUrl] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const needsTerms = Boolean(user?.bulk_submit_enabled) && !user?.can_bulk_submit;

  const { data: terms, isLoading: termsLoading } = useQuery({
    queryKey: ["bulk-submit-terms"],
    queryFn: () => api.bulkSubmitTerms(),
    enabled: needsTerms,
  });

  const handleAcceptTerms = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.bulkSubmitAcceptTerms(agreed);
      await refresh();
      queryClient.invalidateQueries({ queryKey: ["bulk-submit-terms"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to accept terms");
    } finally {
      setBusy(false);
    }
  };

  const handleImport = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.bulkSubmitPlaylist(playlistUrl.trim());
      setPlaylistUrl("");
      navigate("/submit/bulk/queue");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(false);
    }
  };

  if (needsTerms) {
    if (termsLoading) return <p className="muted">Loading…</p>;
    if (!terms) return <p className="muted">Unable to load terms.</p>;
    return (
      <div>
        <h1 className="page-title">{terms.title}</h1>
        <p>{terms.intro}</p>
        <div className="stack" style={{ marginTop: "1rem" }}>
          {terms.sections.map((section) => (
            <div key={section.heading} className="card">
              <h3>
                {section.number != null ? `${section.number}. ` : ""}
                {section.heading}
              </h3>
              {section.paragraphs?.map((p) => (
                <p key={p}>{p}</p>
              ))}
              {section.bullet_label && <p>{section.bullet_label}</p>}
              {section.bullets && section.bullets.length > 0 && (
                <ul>
                  {section.bullets.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
        <label style={{ display: "flex", gap: "0.5rem", marginTop: "1rem", alignItems: "flex-start" }}>
          <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
          <span>I agree to the Power User Terms and will personally QC each bulk item.</span>
        </label>
        {error && <p className="error">{error}</p>}
        <button
          type="button"
          className="btn btn-primary"
          style={{ marginTop: "1rem" }}
          disabled={!agreed || busy}
          onClick={() => void handleAcceptTerms()}
        >
          {busy ? "Saving…" : "Accept and continue"}
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="flex-between" style={{ marginBottom: "1rem" }}>
        <h1 className="page-title" style={{ margin: 0 }}>
          Playlist import
        </h1>
        <Link to="/submit/bulk/queue" className="btn btn-secondary">
          Review queue
        </Link>
      </div>
      <p className="muted">
        Paste a YouTube playlist URL. Videos are hashed and metadata is fetched immediately; nothing
        goes live until you review and submit each item.
      </p>
      <div className="card" style={{ marginTop: "1rem" }}>
        <label htmlFor="playlist-url">Playlist URL</label>
        <input
          id="playlist-url"
          value={playlistUrl}
          onChange={(e) => setPlaylistUrl(e.target.value)}
          placeholder="https://www.youtube.com/playlist?list=…"
          style={{ width: "100%" }}
        />
        {error && <p className="error">{error}</p>}
        <button
          type="button"
          className="btn btn-primary"
          style={{ marginTop: "0.75rem" }}
          disabled={!playlistUrl.trim() || busy}
          onClick={() => void handleImport()}
        >
          {busy ? "Starting…" : "Import playlist"}
        </button>
      </div>
    </div>
  );
}
