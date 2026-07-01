import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate } from "react-router-dom";
import { useAuth, isMod } from "../auth";
import { api } from "../api";

export default function ModQueuePage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("submitted");

  const { data, isLoading } = useQuery({
    queryKey: ["dmca-queue", statusFilter],
    queryFn: () => api.dmcaQueue(statusFilter),
    enabled: isMod(user),
  });

  if (!user) return <Navigate to="/login" />;
  if (!isMod(user)) return <p className="error">Moderator access required.</p>;

  const handleReview = async (id: string, status: string) => {
    const notes = prompt("Review notes (optional):");
    await api.reviewDmca(id, status, notes || undefined);
    queryClient.invalidateQueries({ queryKey: ["dmca-queue"] });
  };

  return (
    <div>
      <h1 className="page-title">Moderator Queue</h1>

      <div style={{ marginBottom: "1.5rem", display: "flex", gap: "0.5rem" }}>
        {["submitted", "under_review", "link_hidden"].map((s) => (
          <button
            key={s}
            className={`btn ${statusFilter === s ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setStatusFilter(s)}
          >
            {s.replace("_", " ")}
          </button>
        ))}
      </div>

      <Link to="/edits" className="btn btn-secondary" style={{ marginBottom: "1rem", display: "inline-block" }}>
        Review open edits
      </Link>

      {isLoading && <p className="muted">Loading...</p>}
      <div className="stack">
        {(data?.items as Record<string, unknown>[])?.map((item) => (
          <div key={item.id as string} className="card">
            <div className="flex-between">
              <span className="badge badge-submitted">{item.status as string}</span>
              <Link to={`/video/${item.video_id}`}>View video</Link>
            </div>
            <p><strong>{item.claimant_name as string}</strong> ({item.claimant_email as string})</p>
            <p className="muted">{item.claim_text as string}</p>
            {statusFilter !== "link_hidden" && (
              <div className="vote-buttons">
                <button className="btn btn-secondary" onClick={() => handleReview(item.id as string, "under_review")}>
                  Mark under review
                </button>
                <button className="btn btn-danger" onClick={() => handleReview(item.id as string, "link_hidden")}>
                  Hide link
                </button>
                <button className="btn btn-secondary" onClick={() => handleReview(item.id as string, "rejected")}>
                  Reject
                </button>
              </div>
            )}
            {statusFilter === "link_hidden" && (
              <button className="btn btn-success" onClick={() => handleReview(item.id as string, "restored")}>
                Restore link
              </button>
            )}
          </div>
        ))}
        {data?.items.length === 0 && <p className="muted">Queue empty.</p>}
      </div>
    </div>
  );
}
