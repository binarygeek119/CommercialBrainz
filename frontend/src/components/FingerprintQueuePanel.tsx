import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { type FingerprintQueueItem, type FingerprintQueueStatus } from "../api";

function formatWhen(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function QueueItemCard({
  item,
  label,
  onRetry,
}: {
  item: FingerprintQueueItem;
  label?: string;
  onRetry?: (id: string) => void;
}) {
  return (
    <div className="card">
      <div className="flex-between">
        <span className={`badge badge-${item.status === "processing" ? "open" : "submitted"}`}>
          {label ?? item.status}
        </span>
        <span className="mono muted">{item.phase}</span>
      </div>
      <p style={{ marginTop: "0.5rem" }}>
        YouTube:{" "}
        <a href={`https://youtube.com/watch?v=${item.youtube_id}`} target="_blank" rel="noreferrer">
          {item.youtube_id}
        </a>
      </p>
      <p className="muted" style={{ fontSize: "0.85rem" }}>
        Queued: {formatWhen(item.created_at)}
        {item.started_at && <> · Started: {formatWhen(item.started_at)}</>}
      </p>
      {item.error_message && <p className="error">{item.error_message}</p>}
      <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
        {item.edit_id && (
          <Link to={`/edits/${item.edit_id}`} className="btn btn-secondary">
            View edit
          </Link>
        )}
        {item.video_id && (
          <Link to={`/video/${item.video_id}`} className="btn btn-secondary">
            View video
          </Link>
        )}
        {onRetry && item.status === "failed" && (
          <button type="button" className="btn btn-primary" onClick={() => onRetry(item.id)}>
            Retry
          </button>
        )}
      </div>
    </div>
  );
}

export default function FingerprintQueuePanel({
  queryKey,
  fetchQueue,
  onRetry,
}: {
  queryKey: string;
  fetchQueue: () => Promise<FingerprintQueueStatus>;
  onRetry?: (id: string) => Promise<void>;
}) {
  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["fingerprint-queue", queryKey],
    queryFn: fetchQueue,
    refetchInterval: 5000,
  });

  const handleRetry = async (id: string) => {
    if (!onRetry) return;
    await onRetry(id);
    await refetch();
  };

  if (isLoading && !data) {
    return <p className="muted">Loading fingerprint queue…</p>;
  }

  if (!data) {
    return <p className="muted">Unable to load fingerprint queue.</p>;
  }

  return (
    <div>
      <div className="grid grid-2" style={{ marginBottom: "1rem" }}>
        <div className="card admin-stat">
          <span className="admin-stat-value">{data.pending_count}</span>
          <span className="muted">Pending in database</span>
        </div>
        <div className="card admin-stat">
          <span className="admin-stat-value">{data.processing_count}</span>
          <span className="muted">Processing now</span>
        </div>
        <div className="card admin-stat">
          <span className="admin-stat-value">{data.redis_queue_depth}</span>
          <span className="muted">Jobs in Redis worker queue</span>
        </div>
      </div>

      <p className="muted" style={{ marginBottom: "1rem", fontSize: "0.85rem" }}>
        Auto-refreshes every 5 seconds{isFetching ? " · updating…" : ""}. Worker runs one fingerprint
        job at a time; pending jobs are processed oldest-first.
      </p>

      {data.processing.length > 0 && (
        <section style={{ marginBottom: "1.5rem" }}>
          <h2 style={{ fontSize: "1.1rem", marginBottom: "0.75rem" }}>Processing now</h2>
          <div className="stack">
            {data.processing.map((item) => (
              <QueueItemCard key={item.id} item={item} label="processing" onRetry={handleRetry} />
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 style={{ fontSize: "1.1rem", marginBottom: "0.75rem" }}>
          Waiting queue
          {data.pending_count > data.pending.length && (
            <span className="muted" style={{ fontWeight: 400, fontSize: "0.9rem" }}>
              {" "}
              (showing {data.pending.length} of {data.pending_count})
            </span>
          )}
        </h2>
        <div className="stack">
          {data.pending.map((item) => (
            <QueueItemCard
              key={item.id}
              item={item}
              label={item.queue_position != null ? `#${item.queue_position}` : "pending"}
            />
          ))}
          {data.pending.length === 0 && data.processing.length === 0 && (
            <p className="muted">Queue empty — no fingerprint jobs waiting.</p>
          )}
          {data.pending.length === 0 && data.processing.length > 0 && (
            <p className="muted">No other jobs waiting.</p>
          )}
        </div>
      </section>
    </div>
  );
}
