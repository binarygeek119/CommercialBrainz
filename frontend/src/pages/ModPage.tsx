import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Edit } from "../api";
import FingerprintQueuePanel from "../components/FingerprintQueuePanel";
import { REPORT_REASONS } from "../components/ReportContentDialog";

type Tab =
  | "overview"
  | "dmca"
  | "edits"
  | "fp-queue"
  | "deletions"
  | "dead-links"
  | "reports";

function reportReasonLabel(reason: string): string {
  return REPORT_REASONS.find((r) => r.value === reason)?.label || reason;
}

export default function ModPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("overview");
  const [dmcaFilter, setDmcaFilter] = useState("submitted");
  const [checkBusy, setCheckBusy] = useState(false);

  const { data: stats } = useQuery({
    queryKey: ["mod-stats"],
    queryFn: () => api.modStats(),
  });

  const { data: dmcaQueue, isLoading: dmcaLoading } = useQuery({
    queryKey: ["dmca-queue", dmcaFilter],
    queryFn: () => api.dmcaQueue(dmcaFilter),
    enabled: tab === "dmca",
  });

  const { data: openEdits, isLoading: editsLoading } = useQuery({
    queryKey: ["open-edits"],
    queryFn: () => api.openEdits(),
    enabled: tab === "edits",
  });

  const { data: deletionRequests, isLoading: deletionsLoading } = useQuery({
    queryKey: ["mod-deletion-requests"],
    queryFn: () => api.modDeletionRequests(),
    enabled: tab === "deletions",
  });

  const { data: deadLinks, isLoading: deadLinksLoading } = useQuery({
    queryKey: ["mod-dead-links"],
    queryFn: () => api.modDeadLinks(),
    enabled: tab === "dead-links",
  });

  const { data: contentReports, isLoading: reportsLoading } = useQuery({
    queryKey: ["mod-content-reports"],
    queryFn: () => api.modContentReports(),
    enabled: tab === "reports",
  });

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ["mod-stats"] });
    queryClient.invalidateQueries({ queryKey: ["dmca-queue"] });
    queryClient.invalidateQueries({ queryKey: ["open-edits"] });
    queryClient.invalidateQueries({ queryKey: ["fingerprint-queue"] });
    queryClient.invalidateQueries({ queryKey: ["mod-deletion-requests"] });
    queryClient.invalidateQueries({ queryKey: ["mod-dead-links"] });
    queryClient.invalidateQueries({ queryKey: ["mod-content-reports"] });
  };

  const handleDmcaReview = async (id: string, status: string) => {
    const notes = prompt("Review notes (optional):");
    await api.reviewDmca(id, status, notes || undefined);
    queryClient.invalidateQueries({ queryKey: ["dmca-queue"] });
    queryClient.invalidateQueries({ queryKey: ["mod-stats"] });
  };

  const handleApplyEdit = async (editId: string) => {
    if (!confirm("Apply this edit immediately?")) return;
    await api.modApplyEdit(editId);
    queryClient.invalidateQueries({ queryKey: ["open-edits"] });
    queryClient.invalidateQueries({ queryKey: ["mod-stats"] });
  };

  const handleRejectEdit = async (editId: string) => {
    if (!confirm("Reject this edit?")) return;
    await api.modRejectEdit(editId);
    queryClient.invalidateQueries({ queryKey: ["open-edits"] });
    queryClient.invalidateQueries({ queryKey: ["mod-stats"] });
  };

  const handleApproveDeletion = async (requestId: string) => {
    if (!confirm("Approve account deletion? This deactivates the account immediately.")) return;
    const notes = prompt("Review notes (optional):");
    await api.modApproveDeletion(requestId, notes || undefined);
    queryClient.invalidateQueries({ queryKey: ["mod-deletion-requests"] });
    queryClient.invalidateQueries({ queryKey: ["mod-stats"] });
  };

  const handleRejectDeletion = async (requestId: string) => {
    const notes = prompt("Reason for rejection (optional):");
    await api.modRejectDeletion(requestId, notes || undefined);
    queryClient.invalidateQueries({ queryKey: ["mod-deletion-requests"] });
    queryClient.invalidateQueries({ queryKey: ["mod-stats"] });
  };

  const handleTriggerLinkCheck = async () => {
    if (
      !confirm(
        "Queue a full public YouTube link scan on the worker? This runs in the background and may take a while."
      )
    ) {
      return;
    }
    setCheckBusy(true);
    try {
      const result = await api.modTriggerDeadLinkCheck();
      alert(result.message || "Link check queued.");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to queue link check");
    } finally {
      setCheckBusy(false);
    }
  };

  const handleDismissDeadLink = async (videoId: string) => {
    if (!confirm("Dismiss this dead-link flag? Visibility is unchanged.")) return;
    await api.modDismissDeadLink(videoId);
    queryClient.invalidateQueries({ queryKey: ["mod-dead-links"] });
    queryClient.invalidateQueries({ queryKey: ["mod-stats"] });
  };

  const handleRecheckDeadLink = async (videoId: string) => {
    await api.modRecheckDeadLink(videoId);
    queryClient.invalidateQueries({ queryKey: ["mod-dead-links"] });
    queryClient.invalidateQueries({ queryKey: ["mod-stats"] });
  };

  const handleReviewReport = async (reportId: string, status: string) => {
    const notes = prompt("Review notes (optional):");
    await api.modReviewContentReport(reportId, status, notes || undefined);
    queryClient.invalidateQueries({ queryKey: ["mod-content-reports"] });
    queryClient.invalidateQueries({ queryKey: ["mod-stats"] });
  };

  const editTitle = (edit: Edit) =>
    (edit.after_state.title as string) ||
    (edit.after_state.commercial as { title?: string })?.title ||
    edit.entity_type;

  return (
    <div>
      <div className="flex-between" style={{ marginBottom: "1.5rem" }}>
        <h1 className="page-title" style={{ marginBottom: 0 }}>
          Moderator
        </h1>
        <button type="button" className="btn btn-secondary" onClick={refreshAll}>
          Refresh
        </button>
      </div>

      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem", flexWrap: "wrap" }}>
        {(
          [
            ["overview", "Overview"],
            ["dmca", "DMCA queue"],
            ["edits", "Open edits"],
            ["deletions", "Account deletions"],
            ["dead-links", "Dead links"],
            ["reports", "Reports"],
            ["fp-queue", "Fingerprint queue"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`btn ${tab === id ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setTab(id)}
          >
            {label}
            {id === "dead-links" && stats && stats.dead_links > 0 ? ` (${stats.dead_links})` : ""}
            {id === "reports" &&
            stats &&
            (stats.open_content_reports ?? stats.open_commercial_reports ?? 0) > 0
              ? ` (${stats.open_content_reports ?? stats.open_commercial_reports})`
              : ""}
          </button>
        ))}
      </div>

      {tab === "overview" && stats && (
        <>
          <div className="grid grid-2">
            <div className="card admin-stat">
              <span className="admin-stat-value">{stats.open_edits}</span>
              <span className="muted">Open edits</span>
            </div>
            <div className="card admin-stat">
              <span className="admin-stat-value">{stats.dmca_submitted}</span>
              <span className="muted">DMCA submitted</span>
            </div>
            <div className="card admin-stat">
              <span className="admin-stat-value">{stats.dmca_under_review}</span>
              <span className="muted">DMCA under review</span>
            </div>
            <div className="card admin-stat">
              <span className="admin-stat-value">{stats.dmca_link_hidden}</span>
              <span className="muted">Links hidden</span>
            </div>
            <div className="card admin-stat">
              <span className="admin-stat-value">{stats.pending_fingerprints}</span>
              <span className="muted">Pending fingerprints</span>
            </div>
            <div className="card admin-stat">
              <span className="admin-stat-value">{stats.failed_fingerprints}</span>
              <span className="muted">Failed fingerprints</span>
            </div>
            <div className="card admin-stat">
              <span className="admin-stat-value">{stats.pending_deletion_requests}</span>
              <span className="muted">Deletion requests</span>
            </div>
            <div className="card admin-stat">
              <span className="admin-stat-value">{stats.dead_links}</span>
              <span className="muted">Dead / blocked links</span>
            </div>
            <div className="card admin-stat">
              <span className="admin-stat-value">
                {stats.open_content_reports ?? stats.open_commercial_reports ?? 0}
              </span>
              <span className="muted">Open content reports</span>
            </div>
          </div>
          <div className="card" style={{ marginTop: "1rem" }}>
            <h3>Quick actions</h3>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.5rem" }}>
              <button type="button" className="btn btn-primary" onClick={() => setTab("edits")}>
                Review open edits
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => setTab("dmca")}>
                DMCA queue
              </button>
              {stats.pending_deletion_requests > 0 && (
                <button type="button" className="btn btn-secondary" onClick={() => setTab("deletions")}>
                  Account deletions ({stats.pending_deletion_requests})
                </button>
              )}
              {stats.dead_links > 0 && (
                <button type="button" className="btn btn-secondary" onClick={() => setTab("dead-links")}>
                  Dead links ({stats.dead_links})
                </button>
              )}
              {(stats.open_content_reports ?? stats.open_commercial_reports ?? 0) > 0 && (
                <button type="button" className="btn btn-secondary" onClick={() => setTab("reports")}>
                  Reports ({stats.open_content_reports ?? stats.open_commercial_reports})
                </button>
              )}
              <button type="button" className="btn btn-secondary" onClick={() => setTab("fp-queue")}>
                Fingerprint queue
              </button>
              <Link to="/submit" className="btn btn-secondary">
                Submit (auto-apply)
              </Link>
            </div>
            <p className="muted" style={{ marginTop: "0.75rem" }}>
              Mods and auto-editors can submit edits that apply instantly. Use Open edits to apply or
              reject community submissions awaiting votes. Public YouTube links are scanned monthly
              for removals and access blocks.
            </p>
          </div>
        </>
      )}

      {tab === "dmca" && (
        <div>
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem", flexWrap: "wrap" }}>
            {["submitted", "under_review", "link_hidden"].map((s) => (
              <button
                key={s}
                type="button"
                className={`btn ${dmcaFilter === s ? "btn-primary" : "btn-secondary"}`}
                onClick={() => setDmcaFilter(s)}
              >
                {s.replace("_", " ")}
              </button>
            ))}
          </div>

          {dmcaLoading && <p className="muted">Loading DMCA queue…</p>}
          <div className="stack">
            {dmcaQueue?.items.map((item) => (
              <div key={item.id} className="card">
                <div className="flex-between">
                  <span className="badge badge-submitted">{item.status}</span>
                  <Link to={`/video/${item.video_id}`}>View video</Link>
                </div>
                <p>
                  <strong>{item.claimant_name}</strong> ({item.claimant_email})
                </p>
                <p className="muted">{item.claim_text}</p>
                {item.review_notes && <p className="muted">Notes: {item.review_notes}</p>}
                {dmcaFilter !== "link_hidden" && (
                  <div className="vote-buttons">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => handleDmcaReview(item.id, "under_review")}
                    >
                      Under review
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger"
                      onClick={() => handleDmcaReview(item.id, "link_hidden")}
                    >
                      Hide link
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => handleDmcaReview(item.id, "rejected")}
                    >
                      Reject
                    </button>
                  </div>
                )}
                {dmcaFilter === "link_hidden" && (
                  <button
                    type="button"
                    className="btn btn-success"
                    onClick={() => handleDmcaReview(item.id, "restored")}
                  >
                    Restore link
                  </button>
                )}
              </div>
            ))}
            {dmcaQueue?.items.length === 0 && <p className="muted">Queue empty.</p>}
          </div>
        </div>
      )}

      {tab === "edits" && (
        <div>
          {editsLoading && <p className="muted">Loading open edits…</p>}
          <div className="stack">
            {openEdits?.items.map((edit) => (
              <div key={edit.id} className="card">
                <div className="flex-between">
                  <span className="badge badge-open">{edit.status}</span>
                  <span className="mono muted">{edit.edit_type}</span>
                </div>
                <h3 style={{ marginTop: "0.5rem" }}>{editTitle(edit)}</h3>
                {edit.comment && <p className="muted">{edit.comment}</p>}
                <p className="muted">
                  {edit.votes.length} vote(s) · expires{" "}
                  {new Date(edit.expires_at).toLocaleDateString()}
                </p>
                {edit.fingerprint_preview && (
                  <p className="mono muted" style={{ fontSize: "0.85rem" }}>
                    Fingerprint: {edit.fingerprint_preview.status}
                    {edit.fingerprint_preview.phash && ` · ${edit.fingerprint_preview.phash}`}
                  </p>
                )}
                <div className="vote-buttons" style={{ marginTop: "0.75rem" }}>
                  <Link to={`/edits/${edit.id}`} className="btn btn-secondary">
                    Details
                  </Link>
                  <button
                    type="button"
                    className="btn btn-success"
                    onClick={() => handleApplyEdit(edit.id)}
                  >
                    Apply now
                  </button>
                  <button
                    type="button"
                    className="btn btn-danger"
                    onClick={() => handleRejectEdit(edit.id)}
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))}
            {openEdits?.items.length === 0 && <p className="muted">No open edits.</p>}
          </div>
        </div>
      )}

      {tab === "fp-queue" && (
        <FingerprintQueuePanel queryKey="mod" fetchQueue={() => api.modFingerprintQueue()} />
      )}

      {tab === "deletions" && (
        <div>
          {deletionsLoading && <p className="muted">Loading deletion requests…</p>}
          <div className="stack">
            {deletionRequests?.map((item) => (
              <div key={item.id} className="card">
                <div className="flex-between">
                  <strong>
                    {item.username ? (
                      <Link to={`/user/${encodeURIComponent(item.username)}`}>{item.username}</Link>
                    ) : (
                      "Unknown user"
                    )}
                  </strong>
                  <span className="badge badge-submitted">{item.status}</span>
                </div>
                <p className="muted" style={{ margin: "0.5rem 0" }}>
                  Requested {new Date(item.created_at).toLocaleString()}
                </p>
                {item.points_to_transfer > 0 && item.recipient_username && (
                  <p>
                    Transfer <strong>{item.points_to_transfer}</strong> points to{" "}
                    <Link to={`/user/${encodeURIComponent(item.recipient_username)}`}>
                      {item.recipient_username}
                    </Link>
                  </p>
                )}
                {item.points_to_transfer === 0 && (
                  <p className="muted">No points to transfer.</p>
                )}
                <div className="vote-buttons" style={{ marginTop: "0.75rem" }}>
                  <button
                    type="button"
                    className="btn btn-danger"
                    onClick={() => handleApproveDeletion(item.id)}
                  >
                    Approve deletion
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => handleRejectDeletion(item.id)}
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))}
            {deletionRequests?.length === 0 && <p className="muted">No pending deletion requests.</p>}
          </div>
        </div>
      )}

      {tab === "dead-links" && (
        <div>
          <div className="flex-between" style={{ marginBottom: "1rem", gap: "0.75rem", flexWrap: "wrap" }}>
            <p className="muted" style={{ margin: 0, maxWidth: "40rem" }}>
              Public YouTube links flagged as unavailable, private, or age-restricted. Scanned
              monthly (1st of month, 04:00 UTC). Does not auto-hide videos.
            </p>
            <button
              type="button"
              className="btn btn-primary"
              disabled={checkBusy}
              onClick={() => void handleTriggerLinkCheck()}
            >
              {checkBusy ? "Queuing…" : "Run link check now"}
            </button>
          </div>
          {deadLinksLoading && <p className="muted">Loading flagged links…</p>}
          <div className="stack">
            {deadLinks?.map((item) => (
              <div key={item.sbid} className="card">
                <div className="flex-between">
                  <span className="badge badge-submitted">{item.link_check_status || "unknown"}</span>
                  <Link to={`/video/${item.sbid}`}>View video</Link>
                </div>
                <h3 style={{ marginTop: "0.5rem" }}>
                  {item.commercial_title || "Untitled commercial"}
                </h3>
                <p className="mono muted" style={{ fontSize: "0.85rem" }}>
                  <a href={item.youtube_url} target="_blank" rel="noreferrer">
                    {item.youtube_id}
                  </a>
                </p>
                {item.link_check_detail && <p className="muted">{item.link_check_detail}</p>}
                <p className="muted" style={{ fontSize: "0.85rem" }}>
                  Flagged{" "}
                  {item.link_flagged_at
                    ? new Date(item.link_flagged_at).toLocaleString()
                    : "—"}
                  {item.link_checked_at
                    ? ` · checked ${new Date(item.link_checked_at).toLocaleString()}`
                    : ""}
                </p>
                <div className="vote-buttons" style={{ marginTop: "0.75rem" }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => void handleRecheckDeadLink(item.sbid)}
                  >
                    Recheck
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => void handleDismissDeadLink(item.sbid)}
                  >
                    Dismiss flag
                  </button>
                </div>
              </div>
            ))}
            {deadLinks?.length === 0 && <p className="muted">No flagged dead links.</p>}
          </div>
        </div>
      )}

      {tab === "reports" && (
        <div>
          <p className="muted" style={{ marginBottom: "1rem" }}>
            User reports on commercials and brands. Banned / adult-ad items should be flagged
            correctly; porn (non-ad) should be removed.
          </p>
          {reportsLoading && <p className="muted">Loading reports…</p>}
          <div className="stack">
            {contentReports?.map((item) => {
              const isBrand = item.target_type === "brand" || Boolean(item.advertiser_id);
              const href = isBrand
                ? `/advertiser/${item.advertiser_id}`
                : `/commercial/${item.commercial_id}`;
              const title =
                item.target_title ||
                item.advertiser_name ||
                item.commercial_title ||
                (isBrand ? item.advertiser_id : item.commercial_id) ||
                "Unknown";
              return (
              <div key={item.id} className="card">
                <div className="flex-between">
                  <strong>
                    <Link to={href}>{title}</Link>
                  </strong>
                  <span className="badge badge-submitted">
                    {isBrand ? "brand" : "commercial"} · {item.status}
                  </span>
                </div>
                <p style={{ margin: "0.5rem 0" }}>
                  <strong>{reportReasonLabel(item.reason)}</strong>
                  {item.outcome_hint ? (
                    <span className="muted"> — {item.outcome_hint}</span>
                  ) : null}
                </p>
                {item.details && <p className="muted">{item.details}</p>}
                <p className="muted" style={{ margin: "0.35rem 0" }}>
                  Reported by{" "}
                  {item.reporter_username ? (
                    <Link to={`/user/${encodeURIComponent(item.reporter_username)}`}>
                      {item.reporter_username}
                    </Link>
                  ) : (
                    "unknown"
                  )}{" "}
                  · {new Date(item.created_at).toLocaleString()}
                </p>
                <div className="vote-buttons" style={{ marginTop: "0.75rem" }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => void handleReviewReport(item.id, "under_review")}
                  >
                    Under review
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => void handleReviewReport(item.id, "resolved")}
                  >
                    Resolve
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => void handleReviewReport(item.id, "dismissed")}
                  >
                    Dismiss
                  </button>
                </div>
              </div>
              );
            })}
            {contentReports?.length === 0 && <p className="muted">No open content reports.</p>}
          </div>
        </div>
      )}
    </div>
  );
}
