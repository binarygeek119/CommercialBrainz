import { useState } from "react";
import { Link, useParams } from "react-router-dom";
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
    refetchInterval: (query) => {
      const fp = query.state.data?.fingerprint_preview;
      if (query.state.data?.status === "open" && fp?.status !== "completed" && fp?.status !== "failed") {
        return 5000;
      }
      return false;
    },
  });

  const { data: duplicates } = useQuery({
    queryKey: ["edit-duplicates", id],
    queryFn: () => api.getEditDuplicates(id!),
    enabled: !!id && edit?.fingerprint_preview?.status === "completed",
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
  const fp = edit.fingerprint_preview;

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

      {edit.edit_type === "create_video" && (
        <div className="card">
          <h3>Fingerprint preview</h3>
          {!fp && <p className="muted">Queued for fingerprinting…</p>}
          {fp && (
            <>
              <p className="muted">Status: {fp.status}</p>
              {fp.phash && <p className="mono">pHash: {fp.phash}</p>}
              {fp.file_sha256 && (
                <p className="mono" style={{ wordBreak: "break-all" }}>
                  SHA256: {fp.file_sha256}
                </p>
              )}
              {fp.audio_fingerprint && (
                <p className="mono" style={{ wordBreak: "break-all" }}>
                  Chromaprint: {fp.audio_fingerprint.slice(0, 64)}…
                </p>
              )}
              {fp.error_message && <p className="error">{fp.error_message}</p>}
            </>
          )}
          {duplicates && duplicates.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <h4>Possible duplicates</h4>
              <ul>
                {duplicates.map((d) => (
                  <li key={d.video_sbid}>
                    <Link to={`/video/${d.video_sbid}`}>{d.youtube_id}</Link>
                    {" "}(distance {d.hamming_distance})
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

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
