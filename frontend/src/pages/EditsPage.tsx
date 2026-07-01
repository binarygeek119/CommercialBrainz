import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";

export default function EditsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["open-edits"],
    queryFn: () => api.openEdits(),
  });

  if (isLoading) return <p className="muted">Loading...</p>;
  if (error) return <p className="error">{(error as Error).message}</p>;

  return (
    <div>
      <h1 className="page-title">Open Edits</h1>
      <p className="muted" style={{ marginBottom: "1.5rem" }}>
        Community-submitted changes awaiting votes. Edits close after 7 days or 3 unanimous votes.
      </p>
      <div className="stack">
        {(data?.items as unknown as import("../api").Edit[])?.map((edit) => (
          <Link
            key={edit.id}
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
            <h3 style={{ marginTop: "0.5rem" }}>
              {(edit.after_state.title as string) ||
                (edit.after_state.commercial as { title?: string })?.title ||
                edit.entity_type}
            </h3>
            {edit.comment && <p className="muted">{edit.comment}</p>}
            <p className="muted">
              {edit.votes.length} vote(s) · expires {new Date(edit.expires_at).toLocaleDateString()}
            </p>
          </Link>
        ))}
        {data?.items.length === 0 && <p className="muted">No open edits.</p>}
      </div>
    </div>
  );
}
