import { useEffect, useState } from "react";
import { Link } from "react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type AdminUser, type AdminFingerprint, type ArchiveExportStatus, type CookieDonationPublic, type RegistrationInvite, type YtdlpCookiesStatus } from "../api";
import BackgroundTasksPanel from "../components/BackgroundTasksPanel";
import FingerprintQueuePanel from "../components/FingerprintQueuePanel";

type Tab =
  | "overview"
  | "users"
  | "fingerprints"
  | "fp-queue"
  | "tasks"
  | "registration"
  | "exports"
  | "ytdlp"
  | "funds"
  | "maintenance";

function toDatetimeLocalValue(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromDatetimeLocalValue(local: string): string {
  const d = new Date(local);
  return d.toISOString();
}

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
  const [annTitle, setAnnTitle] = useState("Announcement");
  const [annBody, setAnnBody] = useState("");
  const [annEnabled, setAnnEnabled] = useState(false);
  const [manualEnabled, setManualEnabled] = useState(false);
  const [manualMessage, setManualMessage] = useState("");
  const [windowStart, setWindowStart] = useState("");
  const [windowEnd, setWindowEnd] = useState("");
  const [windowMessage, setWindowMessage] = useState("");
  const [maintError, setMaintError] = useState("");
  const [maintLoading, setMaintLoading] = useState(false);
  const [domainGoal, setDomainGoal] = useState("");
  const [vmGoal, setVmGoal] = useState("");
  const [costFund, setCostFund] = useState<"domain" | "cloud_vm">("cloud_vm");
  const [costAmount, setCostAmount] = useState("");
  const [costNote, setCostNote] = useState("");
  const [fundsError, setFundsError] = useState("");
  const [fundsLoading, setFundsLoading] = useState(false);

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

  const { data: cookieDonations, refetch: refetchCookieDonations } = useQuery({
    queryKey: ["admin-cookie-donations"],
    queryFn: () => api.adminCookieDonations({ limit: 30 }),
    enabled: tab === "ytdlp",
  });

  const { data: maintenance, refetch: refetchMaintenance } = useQuery({
    queryKey: ["admin-maintenance"],
    queryFn: async () => {
      const data = await api.adminMaintenance();
      setAnnTitle(data.announcement.title || "Announcement");
      setAnnBody(data.announcement.body || "");
      setAnnEnabled(Boolean(data.announcement.enabled));
      setManualEnabled(Boolean(data.manual.enabled));
      setManualMessage(data.manual.message || "");
      return data;
    },
    enabled: tab === "maintenance",
  });

  const { data: donateFunds, refetch: refetchDonateFunds } = useQuery({
    queryKey: ["admin-donate-funds"],
    queryFn: () => api.adminDonateFunds(),
    enabled: tab === "funds",
  });

  useEffect(() => {
    if (!donateFunds) return;
    setDomainGoal(String(donateFunds.domain.goal));
    setVmGoal(String(donateFunds.cloud_vm.goal));
  }, [donateFunds]);

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
    queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    queryClient.invalidateQueries({ queryKey: ["admin-fingerprints"] });
    queryClient.invalidateQueries({ queryKey: ["fingerprint-queue"] });
    queryClient.invalidateQueries({ queryKey: ["background-tasks"] });
    queryClient.invalidateQueries({ queryKey: ["admin-registration-settings"] });
    queryClient.invalidateQueries({ queryKey: ["admin-invites"] });
    queryClient.invalidateQueries({ queryKey: ["registration-settings"] });
    queryClient.invalidateQueries({ queryKey: ["admin-ytdlp-cookies"] });
    queryClient.invalidateQueries({ queryKey: ["admin-donate-funds"] });
    queryClient.invalidateQueries({ queryKey: ["admin-maintenance"] });
    queryClient.invalidateQueries({ queryKey: ["site-status"] });
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

  const handleValidateYtdlpCookies = async () => {
    setCookiesError("");
    setCookiesLoading(true);
    try {
      const status = await api.adminValidateYtdlpCookies();
      queryClient.setQueryData(["admin-ytdlp-cookies"], status);
      if (status.last_validation_ok === false) {
        setCookiesError(status.last_validation_error || "Cookie validation failed");
      }
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

  const handleActivateNextDonation = async () => {
    setCookiesError("");
    setCookiesLoading(true);
    try {
      await api.adminActivateNextCookieDonation();
      await Promise.all([refetchYtdlpCookies(), refetchCookieDonations()]);
    } catch (err) {
      setCookiesError((err as Error).message);
    } finally {
      setCookiesLoading(false);
    }
  };

  const handleRotateDonation = async () => {
    if (!confirm("Exhaust the active donated cookies and activate the next pending donation?")) {
      return;
    }
    setCookiesError("");
    setCookiesLoading(true);
    try {
      await api.adminRotateCookieDonation();
      await Promise.all([refetchYtdlpCookies(), refetchCookieDonations()]);
    } catch (err) {
      setCookiesError((err as Error).message);
    } finally {
      setCookiesLoading(false);
    }
  };

  const handleRejectDonation = async (row: CookieDonationPublic) => {
    if (!confirm(`Reject cookie donation ${row.id}?`)) return;
    setCookiesError("");
    setCookiesLoading(true);
    try {
      await api.adminRejectCookieDonation(row.id);
      await refetchCookieDonations();
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

  const handleSaveAnnouncement = async () => {
    setMaintError("");
    setMaintLoading(true);
    try {
      await api.adminSetAnnouncement({
        enabled: annEnabled,
        title: annTitle,
        body: annBody,
      });
      await refetchMaintenance();
    } catch (err) {
      setMaintError((err as Error).message);
    } finally {
      setMaintLoading(false);
    }
  };

  const handleSaveManual = async () => {
    setMaintError("");
    setMaintLoading(true);
    try {
      await api.adminSetManualMaintenance({
        enabled: manualEnabled,
        message: manualMessage || null,
      });
      await refetchMaintenance();
    } catch (err) {
      setMaintError((err as Error).message);
    } finally {
      setMaintLoading(false);
    }
  };

  const handleAddWindow = async () => {
    setMaintError("");
    if (!windowStart || !windowEnd) {
      setMaintError("Start and end times are required");
      return;
    }
    setMaintLoading(true);
    try {
      await api.adminAddMaintenanceWindow({
        starts_at: fromDatetimeLocalValue(windowStart),
        ends_at: fromDatetimeLocalValue(windowEnd),
        message: windowMessage,
      });
      setWindowStart("");
      setWindowEnd("");
      setWindowMessage("");
      await refetchMaintenance();
    } catch (err) {
      setMaintError((err as Error).message);
    } finally {
      setMaintLoading(false);
    }
  };

  const handleRemoveWindow = async (windowId: string) => {
    if (!confirm("Remove this maintenance window?")) return;
    setMaintError("");
    setMaintLoading(true);
    try {
      await api.adminRemoveMaintenanceWindow(windowId);
      await refetchMaintenance();
    } catch (err) {
      setMaintError((err as Error).message);
    } finally {
      setMaintLoading(false);
    }
  };

  const handleSaveFundGoals = async () => {
    setFundsError("");
    const domain = Number(domainGoal);
    const vm = Number(vmGoal);
    if (!Number.isFinite(domain) || !Number.isFinite(vm) || domain < 0 || vm < 0) {
      setFundsError("Goals must be non-negative numbers");
      return;
    }
    setFundsLoading(true);
    try {
      await api.adminSetDonateFundGoals({ domain_goal: domain, cloud_vm_goal: vm });
      await refetchDonateFunds();
    } catch (err) {
      setFundsError((err as Error).message);
    } finally {
      setFundsLoading(false);
    }
  };

  const handleAddFundCost = async () => {
    setFundsError("");
    const amount = Number(costAmount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setFundsError("Cost amount must be greater than zero");
      return;
    }
    setFundsLoading(true);
    try {
      await api.adminAddDonateFundCost({
        fund: costFund,
        amount,
        note: costNote.trim() || undefined,
      });
      setCostAmount("");
      setCostNote("");
      await refetchDonateFunds();
    } catch (err) {
      setFundsError((err as Error).message);
    } finally {
      setFundsLoading(false);
    }
  };

  const handleDeleteFundCost = async (id: string) => {
    if (!confirm("Remove this cost entry?")) return;
    setFundsError("");
    setFundsLoading(true);
    try {
      await api.adminDeleteDonateFundCost(id);
      await refetchDonateFunds();
    } catch (err) {
      setFundsError((err as Error).message);
    } finally {
      setFundsLoading(false);
    }
  };

  const handleSyncDonateFunds = async () => {
    setFundsError("");
    setFundsLoading(true);
    try {
      await api.adminSyncDonateFunds();
      await refetchDonateFunds();
    } catch (err) {
      setFundsError((err as Error).message);
    } finally {
      setFundsLoading(false);
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
            ["tasks", "Tasks"],
            ["registration", "Registration"],
            ["ytdlp", "YouTube cookies"],
            ["funds", "Funds"],
            ["maintenance", "Maintenance"],
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

      {tab === "tasks" && (
        <BackgroundTasksPanel
          queryKey="admin"
          fetchTasks={() => api.adminBackgroundTasks()}
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
            the server and never shown again after save. Automatic Google login is not supported —
            use Check validity when downloads start failing, then re-export and save.{" "}
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
            onValidate={handleValidateYtdlpCookies}
            onClear={handleClearYtdlpCookies}
          />

          <div style={{ marginTop: "1.5rem", paddingTop: "1.25rem", borderTop: "1px solid var(--border)" }}>
            <h3 style={{ marginTop: 0 }}>Community cookie backlog</h3>
            <p className="muted" style={{ fontSize: "0.9rem" }}>
              Donations from <Link to="/donate">/donate</Link>. When the active jar fails, hashing
              will try rotating to the next pending donation automatically.
            </p>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={cookiesLoading}
                onClick={() => void handleActivateNextDonation()}
              >
                Activate next pending
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={cookiesLoading}
                onClick={() => void handleRotateDonation()}
              >
                Rotate active → next
              </button>
            </div>
            {cookieDonations && cookieDonations.items.length === 0 && (
              <p className="muted">No donations yet.</p>
            )}
            {cookieDonations && cookieDonations.items.length > 0 && (
              <ul style={{ margin: 0, paddingLeft: "1.2rem", fontSize: "0.9rem" }}>
                {cookieDonations.items.map((row) => (
                  <li key={row.id} style={{ marginBottom: "0.4rem" }}>
                    <span className={`badge badge-${row.status === "active" ? "applied" : row.status === "rejected" ? "rejected" : "open"}`}>
                      {row.status}
                    </span>{" "}
                    {row.size_bytes} bytes · {new Date(row.created_at).toLocaleString()}
                    {row.donor_note ? ` · ${row.donor_note}` : ""}
                    {row.status === "pending" && (
                      <>
                        {" "}
                        <button
                          type="button"
                          className="btn btn-secondary"
                          style={{ padding: "0.15rem 0.45rem", fontSize: "0.8rem" }}
                          disabled={cookiesLoading}
                          onClick={() => void handleRejectDonation(row)}
                        >
                          Reject
                        </button>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {tab === "funds" && (
        <div className="grid grid-2">
          <div className="card">
            <h2 style={{ marginTop: 0 }}>Fund goals</h2>
            <p className="muted">
              Goals are the expected Domain / Cloud VM costs the progress bars fill toward.
              Balance = donations matched by Buy Me a Coffee notes − costs you record when paid.
            </p>
            <div className="grid grid-2" style={{ marginBottom: "0.75rem" }}>
              <div>
                <div className="muted">Cloud VM</div>
                <div>
                  Raised {donateFunds?.cloud_vm.raised ?? 0} · Spent{" "}
                  {donateFunds?.cloud_vm.spent ?? 0} · Balance{" "}
                  {donateFunds?.cloud_vm.balance ?? 0}
                </div>
              </div>
              <div>
                <div className="muted">Domain</div>
                <div>
                  Raised {donateFunds?.domain.raised ?? 0} · Spent {donateFunds?.domain.spent ?? 0}{" "}
                  · Balance {donateFunds?.domain.balance ?? 0}
                </div>
              </div>
            </div>
            <label htmlFor="vm-goal">Cloud VM goal (USD)</label>
            <input
              id="vm-goal"
              type="number"
              min={0}
              step="0.01"
              value={vmGoal}
              onChange={(e) => setVmGoal(e.target.value)}
            />
            <label htmlFor="domain-goal">Domain goal (USD)</label>
            <input
              id="domain-goal"
              type="number"
              min={0}
              step="0.01"
              value={domainGoal}
              onChange={(e) => setDomainGoal(e.target.value)}
            />
            <button
              type="button"
              className="btn btn-primary"
              disabled={fundsLoading}
              onClick={() => void handleSaveFundGoals()}
            >
              Save goals
            </button>
          </div>

          <div className="card">
            <h2 style={{ marginTop: 0 }}>Record a cost</h2>
            <p className="muted">
              When you pay the VM or domain bill, record the amount so the public bars show what
              remains in the fund.
            </p>
            <label htmlFor="cost-fund">Fund</label>
            <select
              id="cost-fund"
              value={costFund}
              onChange={(e) => setCostFund(e.target.value as "domain" | "cloud_vm")}
            >
              <option value="cloud_vm">Cloud VM</option>
              <option value="domain">Domain</option>
            </select>
            <label htmlFor="cost-amount">Amount (USD)</label>
            <input
              id="cost-amount"
              type="number"
              min={0.01}
              step="0.01"
              value={costAmount}
              onChange={(e) => setCostAmount(e.target.value)}
            />
            <label htmlFor="cost-note">Note (optional)</label>
            <input
              id="cost-note"
              value={costNote}
              onChange={(e) => setCostNote(e.target.value)}
              placeholder="e.g. July VM invoice"
            />
            <button
              type="button"
              className="btn btn-primary"
              disabled={fundsLoading}
              onClick={() => void handleAddFundCost()}
            >
              Add cost
            </button>
          </div>

          <div className="card" style={{ gridColumn: "1 / -1" }}>
            <h2 style={{ marginTop: 0 }}>Buy Me a Coffee sync</h2>
            <p className="muted">
              Matches supporter notes containing the Domain / Cloud VM donation messages. Only
              donations after tracking started are counted.
              {donateFunds?.tracking_started_at
                ? ` Tracking since ${donateFunds.tracking_started_at}.`
                : ""}
            </p>
            <p className="muted" style={{ fontSize: "0.9rem" }}>
              Sync configured: {donateFunds?.sync_configured ? "yes" : "no (set BUYMEACOFFEE_ACCESS_TOKEN)"}
              {donateFunds?.last_sync_at ? ` · Last sync ${donateFunds.last_sync_at}` : ""}
            </p>
            {donateFunds?.last_sync_error ? (
              <p className="error">Last sync error: {donateFunds.last_sync_error}</p>
            ) : null}
            <button
              type="button"
              className="btn btn-secondary"
              disabled={fundsLoading}
              onClick={() => void handleSyncDonateFunds()}
            >
              Sync now
            </button>
            {fundsError ? <p className="error">{fundsError}</p> : null}
          </div>

          <div className="card">
            <h2 style={{ marginTop: 0 }}>Recent costs</h2>
            <ul style={{ paddingLeft: "1.2rem" }}>
              {(donateFunds?.costs ?? []).map((c) => (
                <li key={c.id} style={{ marginBottom: "0.75rem" }}>
                  <strong>{c.fund === "cloud_vm" ? "Cloud VM" : "Domain"}</strong> — ${c.amount}
                  {c.note ? ` · ${c.note}` : ""}
                  <div className="muted" style={{ fontSize: "0.85rem" }}>
                    {c.paid_at ? new Date(c.paid_at).toLocaleString() : ""}
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ marginTop: "0.35rem" }}
                    disabled={fundsLoading}
                    onClick={() => void handleDeleteFundCost(c.id)}
                  >
                    Remove
                  </button>
                </li>
              ))}
              {(donateFunds?.costs ?? []).length === 0 && (
                <li className="muted">No costs recorded yet</li>
              )}
            </ul>
          </div>

          <div className="card">
            <h2 style={{ marginTop: 0 }}>Recent matched donations</h2>
            <ul style={{ paddingLeft: "1.2rem" }}>
              {(donateFunds?.entries ?? []).map((e) => (
                <li key={e.id} style={{ marginBottom: "0.75rem" }}>
                  <strong>{e.fund === "cloud_vm" ? "Cloud VM" : "Domain"}</strong> — ${e.amount}{" "}
                  {e.currency}
                  {e.supporter_name ? ` · ${e.supporter_name}` : ""}
                  <div className="muted" style={{ fontSize: "0.85rem" }}>
                    {e.support_note}
                  </div>
                  <div className="muted" style={{ fontSize: "0.85rem" }}>
                    {e.donated_at ? new Date(e.donated_at).toLocaleString() : ""} · BMC #
                    {e.bmc_support_id}
                  </div>
                </li>
              ))}
              {(donateFunds?.entries ?? []).length === 0 && (
                <li className="muted">No matched donations yet</li>
              )}
            </ul>
          </div>
        </div>
      )}

      {tab === "maintenance" && (
        <div className="grid grid-2">
          <div className="card">
            <h2 style={{ marginTop: 0 }}>Login announcement</h2>
            <p className="muted">
              Shown as a blocking popup after login until the user clicks OK. Saving creates a
              new announcement id so users must dismiss again.
            </p>
            <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <input
                type="checkbox"
                checked={annEnabled}
                onChange={(e) => setAnnEnabled(e.target.checked)}
              />
              Enabled
            </label>
            <label htmlFor="ann-title">Title</label>
            <input
              id="ann-title"
              value={annTitle}
              onChange={(e) => setAnnTitle(e.target.value)}
            />
            <label htmlFor="ann-body">Message</label>
            <textarea
              id="ann-body"
              rows={6}
              value={annBody}
              onChange={(e) => setAnnBody(e.target.value)}
            />
            <button
              type="button"
              className="btn btn-primary"
              disabled={maintLoading}
              onClick={() => void handleSaveAnnouncement()}
            >
              Save announcement
            </button>
          </div>

          <div className="card">
            <h2 style={{ marginTop: 0 }}>Maintenance gate</h2>
            <p className="muted">
              When enabled (or during a scheduled window), the edge maintenance container shows
              an offline page instead of the site. Deploy updates also set a temporary flag.
            </p>
            {maintenance?.maintenance.active && (
              <p>
                <strong>Currently gated</strong> ({maintenance.maintenance.reason}):{" "}
                {maintenance.maintenance.message}
              </p>
            )}
            <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <input
                type="checkbox"
                checked={manualEnabled}
                onChange={(e) => setManualEnabled(e.target.checked)}
              />
              Enable maintenance now
            </label>
            <label htmlFor="manual-msg">Maintenance message</label>
            <textarea
              id="manual-msg"
              rows={3}
              value={manualMessage}
              onChange={(e) => setManualMessage(e.target.value)}
            />
            <button
              type="button"
              className="btn btn-primary"
              disabled={maintLoading}
              onClick={() => void handleSaveManual()}
            >
              Save maintenance toggle
            </button>
          </div>

          <div className="card" style={{ gridColumn: "1 / -1" }}>
            <h2 style={{ marginTop: 0 }}>Scheduled windows</h2>
            <p className="muted">
              Users see an upcoming banner before the window. During the window the site is
              gated automatically.
            </p>
            <div className="grid grid-2">
              <div>
                <label htmlFor="win-start">Starts</label>
                <input
                  id="win-start"
                  type="datetime-local"
                  value={windowStart}
                  onChange={(e) => setWindowStart(e.target.value)}
                />
              </div>
              <div>
                <label htmlFor="win-end">Ends</label>
                <input
                  id="win-end"
                  type="datetime-local"
                  value={windowEnd}
                  onChange={(e) => setWindowEnd(e.target.value)}
                />
              </div>
            </div>
            <label htmlFor="win-msg">Message (optional)</label>
            <input
              id="win-msg"
              value={windowMessage}
              onChange={(e) => setWindowMessage(e.target.value)}
              placeholder="Why the site will be offline"
            />
            <button
              type="button"
              className="btn btn-primary"
              disabled={maintLoading}
              onClick={() => void handleAddWindow()}
            >
              Add window
            </button>
            {maintError ? <p className="error">{maintError}</p> : null}
            <ul style={{ marginTop: "1rem", paddingLeft: "1.2rem" }}>
              {(maintenance?.windows ?? []).map((w) => (
                <li key={w.id} style={{ marginBottom: "0.75rem" }}>
                  <div>
                    <strong>{toDatetimeLocalValue(w.starts_at).replace("T", " ")}</strong>
                    {" → "}
                    <strong>{toDatetimeLocalValue(w.ends_at).replace("T", " ")}</strong>
                  </div>
                  <div className="muted">{w.message}</div>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ marginTop: "0.35rem" }}
                    disabled={maintLoading}
                    onClick={() => void handleRemoveWindow(w.id)}
                  >
                    Remove
                  </button>
                </li>
              ))}
              {(maintenance?.windows ?? []).length === 0 && (
                <li className="muted">No scheduled windows</li>
              )}
            </ul>
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

function formatExpiresIn(seconds: number | null | undefined): string | null {
  if (seconds == null || !Number.isFinite(seconds)) return null;
  if (seconds <= 0) return "expired";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  if (days > 0) return `${days}d ${hours}h`;
  const mins = Math.floor((seconds % 3600) / 60);
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

function YtdlpCookiesPanel({
  status,
  cookiesText,
  loading,
  error,
  onCookiesTextChange,
  onFile,
  onSave,
  onValidate,
  onClear,
}: {
  status?: YtdlpCookiesStatus;
  cookiesText: string;
  loading: boolean;
  error: string;
  onCookiesTextChange: (value: string) => void;
  onFile: (file: File | null) => void;
  onSave: () => void;
  onValidate: () => void;
  onClear: () => void;
}) {
  const expiresIn = formatExpiresIn(status?.expires_in_seconds);
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
          {status.encrypted_path && (
            <>
              {" "}
              · encrypted: <code>{status.encrypted_path}</code>
            </>
          )}
        </p>
      )}
      <p className="muted" style={{ fontSize: "0.9rem" }}>
        At-rest encryption:{" "}
        <span
          className={`badge badge-${status?.encryption_configured ? "applied" : "rejected"}`}
        >
          {status?.encryption_configured ? "COOKIE_ENCRYPTION_SEED set" : "seed missing"}
        </span>
        {status?.encrypted_at_rest && <> · jar encrypted on disk</>}
      </p>
      {!status?.encryption_configured && (
        <p className="error" style={{ fontSize: "0.9rem" }}>
          Set <code>COOKIE_ENCRYPTION_SEED</code> (64+ character passphrase you choose) in the
          server environment before saving cookies. Donated cookies also require this seed.
        </p>
      )}
      {status?.present && (
        <p className="muted" style={{ fontSize: "0.9rem" }}>
          {status.size_bytes} bytes
          {status.updated_at && <> · updated {new Date(status.updated_at).toLocaleString()}</>}
          {typeof status.auth_cookie_count === "number" && (
            <> · {status.auth_cookie_count} auth cookie{status.auth_cookie_count === 1 ? "" : "s"}</>
          )}
        </p>
      )}
      {status?.expiry_known && (
        <p className="muted" style={{ fontSize: "0.9rem" }}>
          Auth cookie expiry:{" "}
          <span className={`badge badge-${status.expired ? "rejected" : "applied"}`}>
            {status.expired ? "expired" : "ok"}
          </span>
          {status.expires_at && (
            <>
              {" "}
              · {new Date(status.expires_at).toLocaleString()}
              {expiresIn ? ` (${expiresIn})` : ""}
            </>
          )}
        </p>
      )}
      {status?.last_validated_at && (
        <p className="muted" style={{ fontSize: "0.9rem" }}>
          Last live check:{" "}
          <span
            className={`badge badge-${status.last_validation_ok ? "applied" : "rejected"}`}
          >
            {status.last_validation_ok ? "passed" : "failed"}
          </span>{" "}
          · {new Date(status.last_validated_at).toLocaleString()}
        </p>
      )}
      {status?.needs_refresh && (
        <p className="error" style={{ fontSize: "0.9rem" }}>
          Refresh recommended
          {status.refresh_reason ? `: ${status.refresh_reason}` : "."} Export a fresh{" "}
          <code>cookies.txt</code> from a logged-in browser and save it below.
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
          {loading ? "Working…" : "Save cookies"}
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={loading || (!status?.active && !status?.browser_fallback)}
          onClick={onValidate}
        >
          Check validity
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
