import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type AdminUser, type AdminFingerprint, type ArchiveExportStatus } from "../api";

type Tab = "overview" | "users" | "fingerprints" | "exports";

export default function AdminPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("overview");
  const [userQuery, setUserQuery] = useState("");
  const [userSearch, setUserSearch] = useState("");
  const [fpStatus, setFpStatus] = useState<string>("");
  const [exportError, setExportError] = useState("");
  const [exportLoading, setExportLoading] = useState(false);

  const { data: stats } = useQuery({
    queryKey: ["admin-stats"],
    queryFn: () => api.adminStats(),
  });

  const { data: users, isLoading: usersLoading } = useQuery({
    queryKey: ["admin-users", userSearch],
    queryFn: () => api.adminUsers(userSearch || undefined),
    enabled: tab === "users",
  });

  const { data: fingerprints, isLoading: fpLoading } = useQuery({
    queryKey: ["admin-fingerprints", fpStatus],
    queryFn: () => api.adminFingerprints(fpStatus || undefined),
    enabled: tab === "fingerprints",
  });

  const { data: archiveExport, refetch: refetchArchiveExport } = useQuery({
    queryKey: ["admin-archive-export"],
    queryFn: () => api.adminArchiveExportStatus(),
    enabled: tab === "exports",
    refetchInterval: (query) =>
      query.state.data?.status === "running" ? 5000 : false,
  });

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
    queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    queryClient.invalidateQueries({ queryKey: ["admin-fingerprints"] });
  };

  const handleRole = async (userId: string, role: string) => {
    if (!confirm(`Set role to ${role}?`)) return;
    await api.adminSetUserRole(userId, role);
    queryClient.invalidateQueries({ queryKey: ["admin-users"] });
  };

  const handleAccess = async (userId: string, access: string) => {
    await api.adminSetUserAccess(userId, access);
    queryClient.invalidateQueries({ queryKey: ["admin-users"] });
  };

  const handleActive = async (userId: string, isActive: boolean) => {
    await api.adminSetUserActive(userId, isActive);
    queryClient.invalidateQueries({ queryKey: ["admin-users"] });
  };

  const handleRetryFingerprint = async (id: string) => {
    await api.adminRetryFingerprint(id);
    queryClient.invalidateQueries({ queryKey: ["admin-fingerprints"] });
    queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
  };

  const handleTriggerArchiveExport = async () => {
    if (!confirm("Start Archive.org dataset export? This may take several minutes.")) return;
    setExportLoading(true);
    setExportError("");
    try {
      await api.adminTriggerArchiveExport();
      await refetchArchiveExport();
    } catch (err) {
      setExportError((err as Error).message);
    } finally {
      setExportLoading(false);
    }
  };

  return (
    <div>
      <div className="flex-between" style={{ marginBottom: "1.5rem" }}>
        <h1 className="page-title" style={{ marginBottom: 0 }}>
          Admin
        </h1>
        <button type="button" className="btn btn-secondary" onClick={refreshAll}>
          Refresh
        </button>
      </div>

      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem", flexWrap: "wrap" }}>
        {(
          [
            ["overview", "Overview"],
            ["users", "Users"],
            ["fingerprints", "Fingerprints"],
            ["exports", "Archive.org export"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`btn ${tab === id ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
        <Link to="/mod" className="btn btn-secondary">
          Mod queue
        </Link>
        <Link to="/edits" className="btn btn-secondary">
          Open edits
        </Link>
      </div>

      {tab === "overview" && stats && (
        <div className="grid grid-2">
          <div className="card admin-stat">
            <span className="admin-stat-value">{stats.users}</span>
            <span className="muted">Users</span>
          </div>
          <div className="card admin-stat">
            <span className="admin-stat-value">{stats.videos}</span>
            <span className="muted">Videos</span>
          </div>
          <div className="card admin-stat">
            <span className="admin-stat-value">{stats.open_edits}</span>
            <span className="muted">Open edits</span>
          </div>
          <div className="card admin-stat">
            <span className="admin-stat-value">{stats.open_dmca}</span>
            <span className="muted">Open DMCA</span>
          </div>
          <div className="card admin-stat">
            <span className="admin-stat-value">{stats.pending_fingerprints}</span>
            <span className="muted">Pending fingerprints</span>
          </div>
          <div className="card admin-stat">
            <span className="admin-stat-value">{stats.failed_fingerprints}</span>
            <span className="muted">Failed fingerprints</span>
          </div>
        </div>
      )}

      {tab === "users" && (
        <div>
          <form
            className="flex-between"
            style={{ marginBottom: "1rem", gap: "0.5rem" }}
            onSubmit={(e) => {
              e.preventDefault();
              setUserSearch(userQuery);
            }}
          >
            <input
              placeholder="Search username or email…"
              value={userQuery}
              onChange={(e) => setUserQuery(e.target.value)}
              style={{ flex: 1 }}
            />
            <button type="submit" className="btn btn-primary">
              Search
            </button>
          </form>

          {usersLoading && <p className="muted">Loading users…</p>}
          <div className="stack">
            {(users?.items as AdminUser[])?.map((u) => (
              <div key={u.id} className="card">
                <div className="flex-between">
                  <div>
                    <strong>{u.username}</strong>
                    {!u.is_active && <span className="badge badge-rejected"> inactive</span>}
                    <p className="muted">{u.email}</p>
                  </div>
                  <span className="mono muted">{u.role} · {u.access_level}</span>
                </div>
                <p className="muted" style={{ marginTop: "0.5rem" }}>
                  Edits accepted: {u.accepted_edits_count} · Submit: {u.can_submit ? "yes" : "no"}
                </p>
                <div className="vote-buttons" style={{ marginTop: "0.75rem" }}>
                  <button type="button" className="btn btn-secondary" onClick={() => handleRole(u.id, "user")}>
                    User
                  </button>
                  <button type="button" className="btn btn-secondary" onClick={() => handleRole(u.id, "mod")}>
                    Mod
                  </button>
                  <button type="button" className="btn btn-secondary" onClick={() => handleRole(u.id, "admin")}>
                    Admin
                  </button>
                  {u.role === "user" && (
                    <>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => handleAccess(u.id, "vote_only")}
                      >
                        Vote only
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => handleAccess(u.id, "submit_and_vote")}
                      >
                        Submit access
                      </button>
                    </>
                  )}
                  <button
                    type="button"
                    className={`btn ${u.is_active ? "btn-danger" : "btn-success"}`}
                    onClick={() => handleActive(u.id, !u.is_active)}
                  >
                    {u.is_active ? "Deactivate" : "Activate"}
                  </button>
                </div>
              </div>
            ))}
            {users?.items.length === 0 && <p className="muted">No users found.</p>}
          </div>
        </div>
      )}

      {tab === "fingerprints" && (
        <div>
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem", flexWrap: "wrap" }}>
            {["", "pending", "processing", "completed", "failed"].map((s) => (
              <button
                key={s || "all"}
                type="button"
                className={`btn ${fpStatus === s ? "btn-primary" : "btn-secondary"}`}
                onClick={() => setFpStatus(s)}
              >
                {s || "all"}
              </button>
            ))}
          </div>

          {fpLoading && <p className="muted">Loading fingerprint jobs…</p>}
          <div className="stack">
            {(fingerprints?.items as AdminFingerprint[])?.map((fp) => (
              <div key={fp.id} className="card">
                <div className="flex-between">
                  <span className={`badge badge-${fp.status === "completed" ? "applied" : fp.status === "failed" ? "rejected" : "open"}`}>
                    {fp.status}
                  </span>
                  <span className="mono muted">{fp.phase}</span>
                </div>
                <p style={{ marginTop: "0.5rem" }}>
                  YouTube: <a href={`https://youtube.com/watch?v=${fp.youtube_id}`} target="_blank" rel="noreferrer">{fp.youtube_id}</a>
                </p>
                {fp.phash && <p className="mono muted">pHash: {fp.phash}</p>}
                {fp.file_sha256 && <p className="mono muted">SHA256: {fp.file_sha256.slice(0, 16)}…</p>}
                {fp.error_message && <p className="error">{fp.error_message}</p>}
                <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem" }}>
                  {fp.edit_id && (
                    <Link to={`/edits/${fp.edit_id}`} className="btn btn-secondary">
                      View edit
                    </Link>
                  )}
                  {fp.video_id && (
                    <Link to={`/video/${fp.video_id}`} className="btn btn-secondary">
                      View video
                    </Link>
                  )}
                  {fp.status === "failed" && (
                    <button type="button" className="btn btn-primary" onClick={() => handleRetryFingerprint(fp.id)}>
                      Retry
                    </button>
                  )}
                </div>
              </div>
            ))}
            {fingerprints?.items.length === 0 && <p className="muted">No fingerprint jobs.</p>}
          </div>
        </div>
      )}

      {tab === "exports" && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>Internet Archive export</h2>
          <p className="muted">
            Builds a CC0 dataset with full video and brand metadata, site links, custom
            thumbnails, brand logos, and YouTube preview images, then uploads to archive.org.
          </p>

          <ArchiveExportPanel
            status={archiveExport}
            loading={exportLoading}
            error={exportError}
            onTrigger={handleTriggerArchiveExport}
          />
        </div>
      )}
    </div>
  );
}

function ArchiveExportPanel({
  status,
  loading,
  error,
  onTrigger,
}: {
  status?: ArchiveExportStatus;
  loading: boolean;
  error: string;
  onTrigger: () => void;
}) {
  const running = status?.status === "running";

  return (
    <div>
      <p>
        IA credentials:{" "}
        <strong>{status?.configured ? "configured" : "not configured"}</strong>
      </p>
      <p>
        Status: <span className={`badge badge-${running ? "open" : status?.status === "completed" ? "applied" : status?.status === "failed" ? "rejected" : "open"}`}>
          {status?.status ?? "idle"}
        </span>
        {status?.stage && running && (
          <span className="muted" style={{ marginLeft: "0.5rem" }}>
            ({status.stage})
          </span>
        )}
      </p>

      {status?.started_at && (
        <p className="muted">Started: {new Date(status.started_at).toLocaleString()}</p>
      )}
      {status?.finished_at && (
        <p className="muted">Finished: {new Date(status.finished_at).toLocaleString()}</p>
      )}

      {(status?.video_count != null || status?.brand_count != null) && (
        <ul style={{ margin: "0.75rem 0" }}>
          {status.video_count != null && <li>{status.video_count} videos</li>}
          {status.brand_count != null && <li>{status.brand_count} brands</li>}
          {status.thumbnail_files != null && (
            <li>{status.thumbnail_files} hosted thumbnails copied</li>
          )}
          {status.youtube_thumbnails_fetched != null && (
            <li>{status.youtube_thumbnails_fetched} YouTube thumbnails fetched</li>
          )}
          {status.logo_files != null && <li>{status.logo_files} logo images copied</li>}
        </ul>
      )}

      {status?.item_url && (
        <p>
          Archive item:{" "}
          <a href={status.item_url} target="_blank" rel="noreferrer">
            {status.identifier ?? status.item_url}
          </a>
        </p>
      )}

      {status?.bundle_path && (
        <p className="muted" style={{ fontSize: "0.9rem" }}>
          Bundle path: {status.bundle_path}
        </p>
      )}

      {status?.error && <p className="error">{status.error}</p>}
      {error && <p className="error">{error}</p>}

      <button
        type="button"
        className="btn btn-primary"
        disabled={loading || running}
        onClick={onTrigger}
        style={{ marginTop: "0.75rem" }}
      >
        {loading ? "Queueing…" : running ? "Export running…" : "Export to Archive.org"}
      </button>
    </div>
  );
}
