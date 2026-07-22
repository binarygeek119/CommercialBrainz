import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type BulkSubmissionItem } from "../api";
import BulkReviewSubmitModal from "../components/BulkReviewSubmitModal";
import { youtubeIdThumbnail } from "../utils/videoThumbnail";

export default function BulkSubmitQueuePage() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<BulkSubmissionItem | null>(null);

  const { data: items, isLoading, isFetching } = useQuery({
    queryKey: ["bulk-submit-items"],
    queryFn: () => api.bulkSubmitItems(),
    refetchInterval: selected ? false : 5000,
  });

  const { data: batches } = useQuery({
    queryKey: ["bulk-submit-batches"],
    queryFn: () => api.bulkSubmitBatches(),
    refetchInterval: selected ? false : 10000,
  });

  const refreshQueue = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["bulk-submit-items"] }),
      queryClient.invalidateQueries({ queryKey: ["bulk-submit-batches"] }),
    ]);
  };

  const handleSkip = async (itemId: string) => {
    await api.bulkSubmitItemSkip(itemId);
    if (selected?.id === itemId) setSelected(null);
    await refreshQueue();
  };

  const handleRehash = async (itemId: string) => {
    await api.bulkSubmitItemRehash(itemId);
    await queryClient.invalidateQueries({ queryKey: ["bulk-submit-items"] });
  };

  const handleSubmitted = async () => {
    setSelected(null);
    await refreshQueue();
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
        Review opens a submit-style popup. After you submit, the popup closes, remaining videos move
        up, and the next playlist link is staged and hashed.
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
                  {batch.defaults?.commercial_type
                    ? ` · default type ${batch.defaults.commercial_type}`
                    : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {isLoading && <p className="muted">Loading queue…</p>}
      {isFetching && !isLoading && (
        <p className="muted" style={{ marginTop: "0.75rem" }}>
          Updating queue…
        </p>
      )}

      <div className="stack" style={{ marginTop: "1rem" }}>
        {items?.map((item, index) => {
          const meta = item.metadata || {};
          const thumb =
            (typeof meta.thumbnail_url === "string" && meta.thumbnail_url) ||
            youtubeIdThumbnail(item.youtube_id);
          return (
            <div key={item.id} className="card">
              <div style={{ display: "flex", gap: "0.85rem", alignItems: "stretch" }}>
                {thumb && (
                  <img
                    src={thumb}
                    alt=""
                    style={{
                      width: 140,
                      aspectRatio: "16 / 9",
                      objectFit: "cover",
                      borderRadius: 4,
                      flexShrink: 0,
                    }}
                  />
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="flex-between" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
                    <span className="badge badge-submitted">
                      #{index + 1} · {item.status}
                    </span>
                    <a
                      href={item.youtube_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mono muted"
                    >
                      {item.youtube_id}
                    </a>
                  </div>
                  <h3 style={{ marginTop: "0.5rem", marginBottom: 0 }}>
                    {item.title || "Untitled"}
                  </h3>
                  {item.error_message && <p className="muted">{item.error_message}</p>}
                  <div className="vote-buttons" style={{ marginTop: "0.75rem" }}>
                    {(item.status === "ready" ||
                      item.status === "failed" ||
                      item.status === "hashing") && (
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={() => setSelected(item)}
                      >
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
              </div>
            </div>
          );
        })}
        {items?.length === 0 && <p className="muted">Queue empty.</p>}
      </div>

      {selected && (
        <BulkReviewSubmitModal
          item={selected}
          onClose={() => setSelected(null)}
          onSubmitted={() => void handleSubmitted()}
        />
      )}
    </div>
  );
}
