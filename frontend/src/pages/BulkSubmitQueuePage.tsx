import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type BulkSubmissionItem } from "../api";

export default function BulkSubmitQueuePage() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<BulkSubmissionItem | null>(null);
  const [title, setTitle] = useState("");
  const [advertiserName, setAdvertiserName] = useState("");
  const [comment, setComment] = useState("");
  const [termsAgreed, setTermsAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: items, isLoading } = useQuery({
    queryKey: ["bulk-submit-items"],
    queryFn: () => api.bulkSubmitItems(),
    refetchInterval: 5000,
  });

  const { data: batches } = useQuery({
    queryKey: ["bulk-submit-batches"],
    queryFn: () => api.bulkSubmitBatches(),
    refetchInterval: 10000,
  });

  const openItem = (item: BulkSubmissionItem) => {
    setSelected(item);
    const meta = item.metadata || {};
    setTitle((meta.title as string) || item.title || "");
    setAdvertiserName("");
    setComment("");
    setTermsAgreed(false);
    setError(null);
  };

  const handleSkip = async (itemId: string) => {
    await api.bulkSubmitItemSkip(itemId);
    queryClient.invalidateQueries({ queryKey: ["bulk-submit-items"] });
    queryClient.invalidateQueries({ queryKey: ["bulk-submit-batches"] });
    if (selected?.id === itemId) setSelected(null);
  };

  const handleRehash = async (itemId: string) => {
    await api.bulkSubmitItemRehash(itemId);
    queryClient.invalidateQueries({ queryKey: ["bulk-submit-items"] });
  };

  const handleSubmit = async () => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await api.bulkSubmitItemSubmit(selected.id, {
        commercial: {
          title: title.trim(),
          advertiser_name: advertiserName.trim() || null,
        },
        comment: comment || null,
        terms_agreed: termsAgreed,
        tags: [],
      });
      setSelected(null);
      queryClient.invalidateQueries({ queryKey: ["bulk-submit-items"] });
      queryClient.invalidateQueries({ queryKey: ["bulk-submit-batches"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="flex-between" style={{ marginBottom: "1rem" }}>
        <h1 className="page-title" style={{ margin: 0 }}>
          Bulk review queue
        </h1>
        <Link to="/submit/bulk" className="btn btn-secondary">
          Import playlist
        </Link>
      </div>
      <p className="muted">
        Up to 10 videos are staged for review at a time. Hashing starts when a link enters this
        window. Submit one to public voting and the next playlist link is pulled in automatically.
      </p>

      {batches && batches.length > 0 && (
        <div className="card" style={{ marginTop: "1rem" }}>
          <h2 style={{ marginTop: 0, fontSize: "1.05rem" }}>Saved playlists</h2>
          <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
            {batches.map((batch) => (
              <li key={batch.id} style={{ marginBottom: "0.35rem" }}>
                <strong>{batch.playlist_title || "Playlist"}</strong>
                <span className="muted">
                  {" "}
                  · {batch.staging_count ?? 0} in review · {batch.queued_count ?? 0} waiting ·{" "}
                  {batch.item_count} total
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {isLoading && <p className="muted">Loading queue…</p>}
      <div className="stack" style={{ marginTop: "1rem" }}>
        {items?.map((item) => (
          <div key={item.id} className="card">
            <div className="flex-between">
              <span className="badge badge-submitted">{item.status}</span>
              <a href={item.youtube_url} target="_blank" rel="noreferrer" className="mono muted">
                {item.youtube_id}
              </a>
            </div>
            <h3 style={{ marginTop: "0.5rem" }}>{item.title || "Untitled"}</h3>
            {item.error_message && <p className="muted">{item.error_message}</p>}
            <div className="vote-buttons" style={{ marginTop: "0.75rem" }}>
              {(item.status === "ready" || item.status === "failed" || item.status === "hashing") && (
                <button type="button" className="btn btn-primary" onClick={() => openItem(item)}>
                  Review
                </button>
              )}
              {item.status === "failed" && (
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => void handleRehash(item.id)}
                >
                  Rehash
                </button>
              )}
              {item.status !== "submitted" && item.status !== "skipped" && (
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => void handleSkip(item.id)}
                >
                  Skip
                </button>
              )}
              {item.edit_id && (
                <Link to={`/edits/${item.edit_id}`} className="btn btn-secondary">
                  View edit
                </Link>
              )}
            </div>
          </div>
        ))}
        {items?.length === 0 && <p className="muted">Queue empty.</p>}
      </div>

      {selected && (
        <div className="card" style={{ marginTop: "1.5rem" }}>
          <h2>Submit {selected.youtube_id}</h2>
          <p className="muted">Creates a normal catalog edit using prefetched metadata and hashes.</p>
          <label htmlFor="bulk-title">Commercial title</label>
          <input
            id="bulk-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            style={{ width: "100%" }}
          />
          <label htmlFor="bulk-brand" style={{ marginTop: "0.75rem", display: "block" }}>
            Brand / advertiser name
          </label>
          <input
            id="bulk-brand"
            value={advertiserName}
            onChange={(e) => setAdvertiserName(e.target.value)}
            style={{ width: "100%" }}
          />
          <label htmlFor="bulk-comment" style={{ marginTop: "0.75rem", display: "block" }}>
            Comment
          </label>
          <textarea
            id="bulk-comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={3}
            style={{ width: "100%" }}
          />
          <label style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem" }}>
            <input
              type="checkbox"
              checked={termsAgreed}
              onChange={(e) => setTermsAgreed(e.target.checked)}
            />
            <span>I agree to the Terms of Submission for this video</span>
          </label>
          {error && <p className="error">{error}</p>}
          <div className="vote-buttons" style={{ marginTop: "0.75rem" }}>
            <button
              type="button"
              className="btn btn-primary"
              disabled={!title.trim() || !termsAgreed || busy}
              onClick={() => void handleSubmit()}
            >
              {busy ? "Submitting…" : "Submit"}
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => setSelected(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
