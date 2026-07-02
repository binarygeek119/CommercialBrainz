import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Edit } from "../api";
import FingerprintQueuePanel from "../components/FingerprintQueuePanel";

type Tab = "overview" | "dmca" | "edits" | "fp-queue" | "deletions";

export default function ModPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("overview");
  const [dmcaFilter, setDmcaFilter] = useState("submitted");

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

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ["mod-stats"] });
    queryClient.invalidateQueries({ queryKey: ["dmca-queue"] });
    queryClient.invalidateQueries({ queryKey: ["open-edits"] });
    queryClient.invalidateQueries({ queryKey: ["fingerprint-queue"] });
    queryClient.invalidateQueries({ queryKey: ["mod-deletion-requests"] });
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
              <button type="button" className="btn btn-secondary" onClick={() => setTab("fp-queue")}>
                Fingerprint queue
              </button>
              <Link to="/submit" className="btn btn-secondary">
                Submit (auto-apply)
              </Link>
            </div>
            <p className="muted" style={{ marginTop: "0.75rem" }}>
              Mods and auto-editors can submit edits that apply instantly. Use Open edits to apply or
              reject community submissions awaiting votes.
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
    </div>
  );
}
