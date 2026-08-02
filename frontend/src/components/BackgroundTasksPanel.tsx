import { Link } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { type BackgroundTasksStatus } from "../api";

function formatWhen(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function formatBytes(n: number | null | undefined) {
  if (n == null) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function StatusBadge({ status }: { status: string }) {
  const tone =
    status === "running" || status === "pending" || status === "retry"
      ? "open"
      : status === "failed" || status === "error"
        ? "rejected"
        : "submitted";
  return <span className={`badge badge-${tone}`}>{status}</span>;
}

export default function BackgroundTasksPanel({
  queryKey,
  fetchTasks,
}: {
  queryKey: string;
  fetchTasks: () => Promise<BackgroundTasksStatus>;
}) {
  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["background-tasks", queryKey],
    queryFn: fetchTasks,
    refetchInterval: 8000,
  });

  if (isLoading && !data) {
    return <p className="muted">Loading background tasks…</p>;
  }
  if (!data) {
    return <p className="error">Could not load background tasks.</p>;
  }

  const bulkEntries = Object.entries(data.bulk_submit.items_by_status).filter(
    ([, count]) => count > 0
  );

  return (
    <div className="stack">
      <div className="flex-between">
        <div>
          <h2 style={{ margin: 0 }}>Background tasks</h2>
          <p className="muted" style={{ margin: "0.35rem 0 0", fontSize: "0.9rem" }}>
            Everything except fingerprinting. Shared ARQ queue depth:{" "}
            <strong>{data.redis_queue_depth}</strong> (worker max_jobs={data.worker_max_jobs}).
          </p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={() => void refetch()}>
          {isFetching ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {data.note && (
        <p className="muted" style={{ margin: 0, fontSize: "0.9rem" }}>
          {data.note}
        </p>
      )}

      <div className="grid grid-2">
        <section className="card" style={{ margin: 0 }}>
          <div className="flex-between">
            <h3 style={{ margin: 0 }}>Thumbnails</h3>
            <StatusBadge
              status={data.thumbnails.active_count > 0 ? "pending" : "idle"}
            />
          </div>
          <p className="muted" style={{ fontSize: "0.9rem" }}>
            CDN verify after submit; force re-grab streams a padded frame (CDN fallback).
          </p>
          <p style={{ margin: "0.5rem 0 0" }}>
            Active: <strong>{data.thumbnails.active_count}</strong> (pending{" "}
            {data.thumbnails.pending_count}, retry {data.thumbnails.retry_count}) · failed{" "}
            {data.thumbnails.failed_count}
          </p>
          {data.thumbnails.sample.length > 0 && (
            <ul style={{ margin: "0.75rem 0 0", paddingLeft: "1.1rem" }}>
              {data.thumbnails.sample.map((item) => (
                <li key={item.video_id} style={{ marginBottom: "0.35rem", fontSize: "0.9rem" }}>
                  <Link to={`/video/${item.video_id}`}>{item.youtube_id || item.video_id}</Link>{" "}
                  <StatusBadge status={item.status} /> · attempts {item.attempts}
                  {item.last_error ? (
                    <span className="error" style={{ display: "block" }}>
                      {item.last_error}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card" style={{ margin: 0 }}>
          <div className="flex-between">
            <h3 style={{ margin: 0 }}>Bulk submit</h3>
            <StatusBadge
              status={
                data.bulk_submit.importing_batches > 0 || data.bulk_submit.active_items > 0
                  ? "pending"
                  : "idle"
              }
            />
          </div>
          <p className="muted" style={{ fontSize: "0.9rem" }}>
            Playlist import, metadata enrich, and hashing for bulk review slots.
          </p>
          <p style={{ margin: "0.5rem 0 0" }}>
            Importing batches: <strong>{data.bulk_submit.importing_batches}</strong> · active items:{" "}
            <strong>{data.bulk_submit.active_items}</strong>
          </p>
          {bulkEntries.length > 0 ? (
            <ul style={{ margin: "0.75rem 0 0", paddingLeft: "1.1rem", fontSize: "0.9rem" }}>
              {bulkEntries.map(([status, count]) => (
                <li key={status}>
                  {status}: {count}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted" style={{ marginBottom: 0, fontSize: "0.9rem" }}>
              No bulk items in the database.
            </p>
          )}
        </section>

        <section className="card" style={{ margin: 0 }}>
          <div className="flex-between">
            <h3 style={{ margin: 0 }}>Archive.org export</h3>
            <StatusBadge status={data.archive_export.status || "idle"} />
          </div>
          <p className="muted" style={{ fontSize: "0.9rem" }}>
            {data.archive_export.configured
              ? "IA credentials configured."
              : "Not configured (admin Archive.org export tab)."}
          </p>
          {data.archive_export.stage && (
            <p style={{ margin: "0.5rem 0 0" }}>Stage: {data.archive_export.stage}</p>
          )}
          <p className="muted" style={{ fontSize: "0.85rem", marginBottom: 0 }}>
            Started: {formatWhen(data.archive_export.started_at)} · Finished:{" "}
            {formatWhen(data.archive_export.finished_at)}
          </p>
          {data.archive_export.item_url && (
            <p style={{ marginBottom: 0 }}>
              <a href={data.archive_export.item_url} target="_blank" rel="noreferrer noopener">
                {data.archive_export.identifier || "View item"}
              </a>
            </p>
          )}
          {data.archive_export.error && <p className="error">{data.archive_export.error}</p>}
        </section>

        <section className="card" style={{ margin: 0 }}>
          <div className="flex-between">
            <h3 style={{ margin: 0 }}>Dead link check</h3>
            <StatusBadge status={data.link_check.flagged_count > 0 ? "pending" : "idle"} />
          </div>
          <p className="muted" style={{ fontSize: "0.9rem" }}>
            {data.link_check.cron}
          </p>
          <p style={{ margin: "0.5rem 0 0" }}>
            Flagged links: <strong>{data.link_check.flagged_count}</strong>
          </p>
          <p className="muted" style={{ fontSize: "0.85rem", marginBottom: 0 }}>
            Last video checked: {formatWhen(data.link_check.last_checked_at)}
          </p>
          <p style={{ marginBottom: 0, marginTop: "0.5rem" }}>
            <Link to="/mod" className="btn btn-secondary">
              Open mod Dead links
            </Link>
          </p>
        </section>

        <section className="card" style={{ margin: 0 }}>
          <div className="flex-between">
            <h3 style={{ margin: 0 }}>JSON dump</h3>
            <StatusBadge status={data.dumps.available ? "ok" : "idle"} />
          </div>
          <p className="muted" style={{ fontSize: "0.9rem" }}>
            {data.dumps.cron}
          </p>
          {data.dumps.available ? (
            <p style={{ marginBottom: 0 }}>
              Latest: <span className="mono">{data.dumps.filename}</span> (
              {formatBytes(data.dumps.size_bytes)})
            </p>
          ) : (
            <p className="muted" style={{ marginBottom: 0 }}>
              No dump file on this host yet.
            </p>
          )}
        </section>

        <section className="card" style={{ margin: 0 }}>
          <div className="flex-between">
            <h3 style={{ margin: 0 }}>Expire edits</h3>
            <StatusBadge status="idle" />
          </div>
          <p className="muted" style={{ fontSize: "0.9rem", marginBottom: 0 }}>
            {data.expire_edits.cron}. Closes timed-out edits and may enqueue follow-up hash /
            thumbnail jobs.
          </p>
        </section>
      </div>
    </div>
  );
}
