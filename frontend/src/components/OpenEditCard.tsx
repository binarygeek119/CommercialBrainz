import { Link } from "react-router-dom";
import type { Edit } from "../api";
import { editTitle } from "../utils/editDisplay";

export default function OpenEditCard({ edit }: { edit: Edit }) {
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
      <h3 style={{ marginTop: "0.5rem" }}>{editTitle(edit)}</h3>
      {edit.editor_username && (
        <p className="muted" style={{ marginTop: "0.35rem" }}>
          by{" "}
          <Link
            to={`/user/${encodeURIComponent(edit.editor_username)}`}
            onClick={(e) => e.stopPropagation()}
          >
            {edit.editor_username}
          </Link>
        </p>
      )}
      {edit.comment && <p className="muted">{edit.comment}</p>}
      <p className="muted">
        {edit.votes.length} vote(s) · expires {new Date(edit.expires_at).toLocaleDateString()}
      </p>
    </Link>
  );
}
