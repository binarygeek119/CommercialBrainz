import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth";
import { api } from "../api";

export default function EditDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const [voteComment, setVoteComment] = useState("");

  const { data: edit, isLoading } = useQuery({
    queryKey: ["edit", id],
    queryFn: () => api.getEdit(id!),
    enabled: !!id,
  });

  const handleVote = async (choice: string) => {
    if (!user) return;
    setError("");
    try {
      await api.vote(id!, choice, voteComment || undefined);
      queryClient.invalidateQueries({ queryKey: ["edit", id] });
      queryClient.invalidateQueries({ queryKey: ["open-edits"] });
    } catch (err) {
      setError((err as Error).message);
    }
  };

  if (isLoading) return <p className="muted">Loading...</p>;
  if (!edit) return null;

  const yesVotes = edit.votes.filter((v) => v.choice === "yes").length;
  const noVotes = edit.votes.filter((v) => v.choice === "no").length;

  return (
    <div>
      <h1 className="page-title">Edit #{edit.id.slice(0, 8)}</h1>
      <div className="card">
        <div className="flex-between">
          <span className={`badge badge-${edit.status === "open" ? "open" : edit.status}`}>
            {edit.status}
          </span>
          <span className="mono muted">{edit.edit_type}</span>
        </div>
        {edit.comment && <p style={{ marginTop: "1rem" }}>{edit.comment}</p>}
        <p className="muted">
          Expires: {new Date(edit.expires_at).toLocaleString()} · Yes: {yesVotes} · No: {noVotes}
        </p>
      </div>

      <div className="card">
        <h3>Proposed changes</h3>
        <pre style={{ overflow: "auto", fontSize: "0.85rem", color: "var(--text-muted)" }}>
          {JSON.stringify(edit.after_state, null, 2)}
        </pre>
      </div>

      {edit.votes.length > 0 && (
        <div className="card">
          <h3>Votes</h3>
          {edit.votes.map((v) => (
            <p key={v.id}>
              <strong>{v.choice}</strong>
              {v.comment && ` — ${v.comment}`}
            </p>
          ))}
        </div>
      )}

      {edit.status === "open" && user && (
        <div className="card">
          <h3>Cast your vote</h3>
          <div className="form-group">
            <label>Comment (optional)</label>
            <textarea value={voteComment} onChange={(e) => setVoteComment(e.target.value)} />
          </div>
          <div className="vote-buttons">
            <button className="btn btn-success" onClick={() => handleVote("yes")}>
              Yes
            </button>
            <button className="btn btn-danger" onClick={() => handleVote("no")}>
              No
            </button>
            <button className="btn btn-secondary" onClick={() => handleVote("abstain")}>
              Abstain
            </button>
          </div>
          {error && <p className="error">{error}</p>}
        </div>
      )}

      {!user && edit.status === "open" && (
        <p className="muted"><a href="/login">Log in</a> to vote on this edit.</p>
      )}
    </div>
  );
}
