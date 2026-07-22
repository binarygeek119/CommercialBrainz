import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type BulkPlaylistCheck } from "../api";
import { useAuth } from "../auth";

function duplicateReasonLabel(reason: string | null | undefined): string {
  switch (reason) {
    case "catalog":
      return "Already in catalog";
    case "queue":
      return "Already in your review queue";
    case "playlist_duplicate":
      return "Duplicate entry in this playlist";
    default:
      return "Duplicate link";
  }
}

export default function BulkSubmitPage() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [playlistUrl, setPlaylistUrl] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [check, setCheck] = useState<BulkPlaylistCheck | null>(null);

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

  const handleCheck = async () => {
    setBusy(true);
    setError(null);
    setCheck(null);
    try {
      const result = await api.bulkSubmitCheckPlaylist(playlistUrl.trim());
      setCheck(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Duplicate check failed");
    } finally {
      setBusy(false);
    }
  };

  const handleImport = async () => {
    if (!check || check.counts.ok < 1) return;
    setBusy(true);
    setError(null);
    try {
      await api.bulkSubmitPlaylist(check.playlist_url);
      setPlaylistUrl("");
      setCheck(null);
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

  const duplicates = check?.entries.filter((e) => e.status === "duplicate") ?? [];
  const importable = check?.counts.ok ?? 0;

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
        Paste a YouTube playlist URL, check for duplicate links, then import. Videos are hashed and
        metadata is fetched immediately; nothing goes live until you review and submit each item.
      </p>
      <div className="card" style={{ marginTop: "1rem" }}>
        <label htmlFor="playlist-url">Playlist URL</label>
        <input
          id="playlist-url"
          value={playlistUrl}
          onChange={(e) => {
            setPlaylistUrl(e.target.value);
            setCheck(null);
          }}
          placeholder="https://www.youtube.com/playlist?list=…"
          style={{ width: "100%" }}
        />
        {error && <p className="error">{error}</p>}
        <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem", flexWrap: "wrap" }}>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!playlistUrl.trim() || busy}
            onClick={() => void handleCheck()}
          >
            {busy && !check ? "Checking…" : "Check duplicates"}
          </button>
          {check && (
            <button
              type="button"
              className="btn btn-secondary"
              disabled={importable < 1 || busy}
              onClick={() => void handleImport()}
            >
              {busy && check ? "Starting…" : `Import ${importable} video${importable === 1 ? "" : "s"}`}
            </button>
          )}
        </div>
      </div>

      {check && (
        <div className="card" style={{ marginTop: "1rem" }}>
          <h2 style={{ marginTop: 0, fontSize: "1.1rem" }}>
            {check.playlist_title || "Playlist check"}
          </h2>
          <p className="muted" style={{ marginBottom: "0.75rem" }}>
            {check.counts.total} link{check.counts.total === 1 ? "" : "s"} found · {importable}{" "}
            importable
            {check.counts.catalog > 0 ? ` · ${check.counts.catalog} already in catalog` : ""}
            {check.counts.queue > 0 ? ` · ${check.counts.queue} already in queue` : ""}
            {check.counts.playlist_duplicate > 0
              ? ` · ${check.counts.playlist_duplicate} playlist duplicate${
                  check.counts.playlist_duplicate === 1 ? "" : "s"
                }`
              : ""}
          </p>
          {importable < 1 && (
            <p className="error">Nothing new to import — every link is a duplicate.</p>
          )}
          {duplicates.length > 0 && (
            <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
              {duplicates.map((entry) => (
                <li key={`${entry.youtube_id}-${entry.position}`}>
                  {entry.title || entry.youtube_id}
                  <span className="muted"> — {duplicateReasonLabel(entry.reason)}</span>
                </li>
              ))}
            </ul>
          )}
          {duplicates.length === 0 && importable > 0 && (
            <p className="muted">No duplicate links. Ready to import.</p>
          )}
        </div>
      )}
    </div>
  );
}
