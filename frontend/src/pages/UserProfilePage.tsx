import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type UserEditSummary } from "../api";

function roleLabel(role: string): string | null {
  if (role === "admin") return "Admin";
  if (role === "mod") return "Moderator";
  return null;
}

function UserEditRow({ edit }: { edit: UserEditSummary }) {
  return (
    <Link
      to={`/edits/${edit.id}`}
      className="card"
      style={{ textDecoration: "none", color: "inherit" }}
    >
      <div className="flex-between">
        <span className={`badge badge-${edit.status === "open" ? "open" : edit.status}`}>
          {edit.status}
        </span>
        <span className="muted mono">{edit.edit_type}</span>
      </div>
      <h3 style={{ marginTop: "0.5rem" }}>{edit.title}</h3>
      {edit.comment && <p className="muted">{edit.comment}</p>}
      <p className="muted">
        Submitted {new Date(edit.created_at).toLocaleDateString()}
        {edit.status === "open" && <> · {edit.vote_count} vote(s)</>}
        {edit.closed_at && <> · closed {new Date(edit.closed_at).toLocaleDateString()}</>}
      </p>
    </Link>
  );
}

export default function UserProfilePage() {
  const { username } = useParams<{ username: string }>();
  const [shown, setShown] = useState(25);

  const profileQuery = useQuery({
    queryKey: ["user-profile", username],
    queryFn: () => api.getUserProfile(username!),
    enabled: !!username,
  });

  const editsQuery = useQuery({
    queryKey: ["user-edits", username, shown],
    queryFn: () => api.getUserEdits(username!, 0, shown),
    enabled: !!username,
  });

  if (profileQuery.isLoading) return <p className="muted">Loading profile…</p>;
  if (profileQuery.error) {
    return <p className="error">{(profileQuery.error as Error).message}</p>;
  }
  if (!profileQuery.data) return null;

  const profile = profileQuery.data;
  const badge = roleLabel(profile.role);
  const edits = editsQuery.data?.items ?? [];
  const total = editsQuery.data?.total ?? profile.submission_count;
  const hasMore = edits.length < total;

  return (
    <div>
      <div className="flex-between profile-header" style={{ alignItems: "center", marginBottom: "1rem" }}>
        <h1 className="page-title" style={{ margin: 0 }}>{profile.username}</h1>
        <div className="profile-badges">
          <span className="badge badge-points">{profile.reputation_points.toFixed(2)} pts</span>
          {badge && <span className="badge badge-open">{badge}</span>}
          {profile.is_power_user && <span className="badge badge-open">Power user</span>}
        </div>
      </div>
      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <div>
          <p style={{ margin: 0 }}>
            Member since {new Date(profile.created_at).toLocaleDateString()}
          </p>
          <p className="muted" style={{ marginTop: "0.5rem", marginBottom: 0 }}>
            {profile.accepted_edits_count} accepted edit
            {profile.accepted_edits_count === 1 ? "" : "s"} · {profile.submission_count}{" "}
            submission{profile.submission_count === 1 ? "" : "s"}
          </p>
        </div>
      </div>

      <h2 style={{ marginBottom: "1rem" }}>Submissions</h2>
      {editsQuery.isLoading && shown === 25 ? (
        <p className="muted">Loading submissions…</p>
      ) : editsQuery.error ? (
        <p className="error">{(editsQuery.error as Error).message}</p>
      ) : (
        <>
          <div className="stack">
            {edits.map((edit) => (
              <UserEditRow key={edit.id} edit={edit} />
            ))}
            {edits.length === 0 && (
              <p className="muted">No submissions yet.</p>
            )}
          </div>
          {total > 0 && (
            <p className="muted" style={{ marginTop: "1rem" }}>
              Showing {edits.length} of {total}
            </p>
          )}
          {hasMore && (
            <button
              type="button"
              className="btn btn-secondary"
              style={{ marginTop: "1rem" }}
              disabled={editsQuery.isFetching}
              onClick={() => setShown((current) => current + 25)}
            >
              {editsQuery.isFetching ? "Loading…" : "Load more"}
            </button>
          )}
        </>
      )}
    </div>
  );
}
