import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type AdminUser, type AdminFingerprint, type ArchiveExportStatus, type RegistrationInvite, type YtdlpCookiesStatus } from "../api";
import FingerprintQueuePanel from "../components/FingerprintQueuePanel";

type Tab = "overview" | "users" | "fingerprints" | "fp-queue" | "registration" | "exports" | "ytdlp";

export default function AdminPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("overview");
  const [userQuery, setUserQuery] = useState("");
  const [userSearch, setUserSearch] = useState("");
  const [fpStatus, setFpStatus] = useState<string>("");
  const [exportError, setExportError] = useState("");
  const [exportLoading, setExportLoading] = useState(false);
  const [inviteLabel, setInviteLabel] = useState("");
  const [inviteError, setInviteError] = useState("");
  const [inviteLoading, setInviteLoading] = useState(false);
  const [copiedInviteId, setCopiedInviteId] = useState<string | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [cookiesText, setCookiesText] = useState("");
  const [cookiesError, setCookiesError] = useState("");
  const [cookiesLoading, setCookiesLoading] = useState(false);

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

  const { data: registrationSettings, refetch: refetchRegistrationSettings } = useQuery({
    queryKey: ["admin-registration-settings"],
    queryFn: () => api.adminRegistrationSettings(),
    enabled: tab === "registration",
  });

  const { data: invites, isLoading: invitesLoading, refetch: refetchInvites } = useQuery({
    queryKey: ["admin-invites"],
    queryFn: () => api.adminInvites(),
    enabled: tab === "registration",
  });

  const { data: ytdlpCookies, refetch: refetchYtdlpCookies } = useQuery({
    queryKey: ["admin-ytdlp-cookies"],
    queryFn: () => api.adminYtdlpCookiesStatus(),
    enabled: tab === "ytdlp",
  });

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
    queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    queryClient.invalidateQueries({ queryKey: ["admin-fingerprints"] });
    queryClient.invalidateQueries({ queryKey: ["fingerprint-queue"] });
    queryClient.invalidateQueries({ queryKey: ["admin-registration-settings"] });
    queryClient.invalidateQueries({ queryKey: ["admin-invites"] });
    queryClient.invalidateQueries({ queryKey: ["registration-settings"] });
    queryClient.invalidateQueries({ queryKey: ["admin-ytdlp-cookies"] });
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

  const handleBulkSubmit = async (userId: string, enabled: boolean) => {
    let revokeReason: string | undefined;
    if (!enabled) {
      revokeReason = prompt("Optional revoke reason:") || undefined;
    }
    try {
      await api.adminSetUserBulkSubmit(userId, enabled, revokeReason);
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to update bulk submit");
    }
  };

  const handleRetryFingerprint = async (id: string) => {
    await api.adminRetryFingerprint(id);
    queryClient.invalidateQueries({ queryKey: ["admin-fingerprints"] });
    queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
  };

  const handleToggleInviteOnly = async (inviteOnly: boolean) => {
    setSettingsLoading(true);
    setInviteError("");
    try {
      await api.adminSetRegistrationSettings(inviteOnly);
      await refetchRegistrationSettings();
      queryClient.invalidateQueries({ queryKey: ["registration-settings"] });
    } catch (err) {
      setInviteError((err as Error).message);
    } finally {
      setSettingsLoading(false);
    }
  };

  const handleCreateInvite = async () => {
    setInviteLoading(true);
    setInviteError("");
    try {
      await api.adminCreateInvite({ label: inviteLabel.trim() || undefined });
      setInviteLabel("");
      await refetchInvites();
    } catch (err) {
      setInviteError((err as Error).message);
    } finally {
      setInviteLoading(false);
    }
  };

  const handleRevokeInvite = async (inviteId: string) => {
    if (!confirm("Revoke this invite code?")) return;
    setInviteError("");
    try {
      await api.adminRevokeInvite(inviteId);
      await refetchInvites();
    } catch (err) {
      setInviteError((err as Error).message);
    }
  };

  const handleCopyInviteCode = async (inviteId: string, code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopiedInviteId(inviteId);
      window.setTimeout(() => setCopiedInviteId((current) => (current === inviteId ? null : current)), 2000);
    } catch (err) {
      setInviteError((err as Error).message || "Could not copy invite code");
    }
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

  const handleSaveYtdlpCookies = async () => {
    setCookiesError("");
    setCookiesLoading(true);
    try {
      await api.adminSetYtdlpCookies(cookiesText);
      setCookiesText("");
      await refetchYtdlpCookies();
    } catch (err) {
      setCookiesError((err as Error).message);
    } finally {
      setCookiesLoading(false);
    }
  };

  const handleClearYtdlpCookies = async () => {
    if (
      !confirm(
        "Remove the managed YouTube cookies file? yt-dlp may hit bot checks until replaced."
      )
    ) {
      return;
    }
    setCookiesError("");
    setCookiesLoading(true);
    try {
      await api.adminClearYtdlpCookies();
      await refetchYtdlpCookies();
    } catch (err) {
      setCookiesError((err as Error).message);
    } finally {
      setCookiesLoading(false);
    }
  };

  const handleCookiesFile = async (file: File | null) => {
    if (!file) return;
    setCookiesError("");
    try {
      setCookiesText(await file.text());
    } catch (err) {
      setCookiesError((err as Error).message || "Could not read file");
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
            ["fp-queue", "Fingerprint queue"],
            ["registration", "Registration"],
            ["ytdlp", "YouTube cookies"],
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
                  Edits accepted: {u.accepted_edits_count} · Submit: {u.can_submit ? "yes" : "no"} ·
                  Reputation: {u.reputation_points.toFixed(2)}
                  {u.bulk_submit_enabled ? " · Power user" : ""}
                  {u.power_user_terms_accepted_at ? " · terms accepted" : ""}
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
                  {!u.bulk_submit_enabled ? (
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => void handleBulkSubmit(u.id, true)}
                      title="Requires 500+ reputation or mod/admin"
                    >
                      Enable bulk submit
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-danger"
                      onClick={() => void handleBulkSubmit(u.id, false)}
                    >
                      Remove power user
                    </button>
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

      {tab === "fp-queue" && (
        <FingerprintQueuePanel
          queryKey="admin"
          fetchQueue={() => api.adminFingerprintQueue()}
          onRetry={async (id) => {
            await api.adminRetryFingerprint(id);
            queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
          }}
        />
      )}

      {tab === "registration" && (
        <div className="stack">
          <div className="card">
            <h2 style={{ marginTop: 0 }}>Invite-only registration</h2>
            <p className="muted">
              When enabled, new accounts need a valid invite code. Anyone can still browse videos,
              brands, and search without logging in.
            </p>
            <label style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "1rem" }}>
              <input
                type="checkbox"
                checked={registrationSettings?.invite_only ?? false}
                disabled={settingsLoading}
                onChange={(e) => handleToggleInviteOnly(e.target.checked)}
              />
              <span>Require invite code to register</span>
            </label>
            {inviteError && <p className="error">{inviteError}</p>}
          </div>

          <div className="card">
            <h2 style={{ marginTop: 0 }}>Invite codes</h2>
            <div className="form-group">
              <label>Label (optional)</label>
              <input
                value={inviteLabel}
                onChange={(e) => setInviteLabel(e.target.value)}
                placeholder="e.g. Beta tester batch 1"
              />
            </div>
            <button
              type="button"
              className="btn btn-primary"
              disabled={inviteLoading}
              onClick={handleCreateInvite}
            >
              {inviteLoading ? "Creating…" : "Generate invite code"}
            </button>
            <p className="muted" style={{ marginTop: "0.75rem", fontSize: "0.85rem" }}>
              Share a code or link like <code>/register?invite=CODE</code>. Codes expire in 30 days by default.
            </p>
          </div>

          {invitesLoading && <p className="muted">Loading invites…</p>}
          <div className="stack">
            {(invites?.items as RegistrationInvite[])?.map((invite) => (
              <div key={invite.id} className="card">
                <div className="flex-between">
                  <code style={{ fontSize: "1.05rem" }}>{invite.code}</code>
                  <span className={`badge badge-${invite.is_active ? "applied" : "rejected"}`}>
                    {invite.is_active ? "active" : invite.revoked_at ? "revoked" : "expired"}
                  </span>
                </div>
                {invite.label && <p className="muted" style={{ marginTop: "0.35rem" }}>{invite.label}</p>}
                <p className="muted" style={{ fontSize: "0.85rem", marginTop: "0.35rem" }}>
                  Uses: {invite.use_count}/{invite.max_uses}
                  {invite.expires_at && <> · expires {new Date(invite.expires_at).toLocaleDateString()}</>}
                </p>
                <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => handleCopyInviteCode(invite.id, invite.code)}
                  >
                    {copiedInviteId === invite.id ? "Copied!" : "Copy code"}
                  </button>
                  <Link to={`/register?invite=${encodeURIComponent(invite.code)}`} className="btn btn-secondary">
                    Open register link
                  </Link>
                  {invite.is_active && (
                    <button
                      type="button"
                      className="btn btn-danger"
                      onClick={() => handleRevokeInvite(invite.id)}
                    >
                      Revoke
                    </button>
                  )}
                </div>
              </div>
            ))}
            {invites?.items.length === 0 && !invitesLoading && (
              <p className="muted">No invite codes yet.</p>
            )}
          </div>
        </div>
      )}

      {tab === "ytdlp" && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>YouTube cookies (yt-dlp)</h2>
          <p className="muted">
            YouTube may block anonymous yt-dlp with a bot check. Paste a Netscape{" "}
            <code>cookies.txt</code> exported from a logged-in browser. Contents are stored on
            the server and never shown again after save.{" "}
            <a
              href="https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies"
              target="_blank"
              rel="noreferrer"
            >
              Export guide
            </a>
          </p>

          <YtdlpCookiesPanel
            status={ytdlpCookies}
            cookiesText={cookiesText}
            loading={cookiesLoading}
            error={cookiesError}
            onCookiesTextChange={setCookiesText}
            onFile={handleCookiesFile}
            onSave={handleSaveYtdlpCookies}
            onClear={handleClearYtdlpCookies}
          />
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

function YtdlpCookiesPanel({
  status,
  cookiesText,
  loading,
  error,
  onCookiesTextChange,
  onFile,
  onSave,
  onClear,
}: {
  status?: YtdlpCookiesStatus;
  cookiesText: string;
  loading: boolean;
  error: string;
  onCookiesTextChange: (value: string) => void;
  onFile: (file: File | null) => void;
  onSave: () => void;
  onClear: () => void;
}) {
  return (
    <div>
      <p>
        Managed file:{" "}
        <span className={`badge badge-${status?.present ? "applied" : "open"}`}>
          {status?.present ? "present" : "missing"}
        </span>
        {status?.active && (
          <span className="muted" style={{ marginLeft: "0.5rem" }}>
            active for yt-dlp
          </span>
        )}
      </p>
      {status?.path && (
        <p className="muted" style={{ fontSize: "0.9rem" }}>
          Path: <code>{status.path}</code>
        </p>
      )}
      {status?.present && (
        <p className="muted" style={{ fontSize: "0.9rem" }}>
          {status.size_bytes} bytes
          {status.updated_at && <> · updated {new Date(status.updated_at).toLocaleString()}</>}
        </p>
      )}
      {status?.env_override && (
        <p className="muted" style={{ fontSize: "0.9rem" }}>
          Note: <code>YTDLP_COOKIES_FILE</code> is set and takes priority when that file exists.
        </p>
      )}
      {status?.browser_fallback && !status.active && (
        <p className="muted" style={{ fontSize: "0.9rem" }}>
          Browser cookie extraction is configured as a fallback (
          <code>YTDLP_COOKIES_FROM_BROWSER</code>).
        </p>
      )}

      <div className="form-group" style={{ marginTop: "1rem" }}>
        <label htmlFor="ytdlp-cookies-file">Load from file</label>
        <input
          id="ytdlp-cookies-file"
          type="file"
          accept=".txt,text/plain"
          onChange={(e) => onFile(e.target.files?.[0] ?? null)}
          disabled={loading}
        />
      </div>

      <div className="form-group">
        <label htmlFor="ytdlp-cookies-text">cookies.txt contents</label>
        <textarea
          id="ytdlp-cookies-text"
          value={cookiesText}
          onChange={(e) => onCookiesTextChange(e.target.value)}
          rows={10}
          placeholder="# Netscape HTTP Cookie File&#10;…"
          disabled={loading}
          spellCheck={false}
          style={{ fontFamily: "var(--mono)", fontSize: "0.85rem" }}
        />
      </div>

      {error && <p className="error">{error}</p>}

      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
        <button
          type="button"
          className="btn btn-primary"
          disabled={loading || !cookiesText.trim()}
          onClick={onSave}
        >
          {loading ? "Saving…" : "Save cookies"}
        </button>
        <button
          type="button"
          className="btn btn-danger"
          disabled={loading || !status?.present}
          onClick={onClear}
        >
          Clear cookies
        </button>
      </div>
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
