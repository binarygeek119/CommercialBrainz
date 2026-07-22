import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import OpenEditCard from "../components/OpenEditCard";

export default function HomePage() {
  const { data, isLoading } = useQuery({
    queryKey: ["open-edits-recent"],
    queryFn: () => api.openEdits(0, 12),
  });

  const recentEdits = data?.items ?? [];

  return (
    <div>
      <div className="hero">
        <h1 className="logo">
          Commercial<span>Brainz</span>
        </h1>
        <p>
          The open commercial video database. One entry per YouTube video, rich metadata,
          community edits, and MusicBrainz-style voting.
        </p>
        <div style={{ display: "flex", gap: "1rem", justifyContent: "center", flexWrap: "wrap" }}>
          <Link to="/browse" className="btn btn-primary">
            Browse commercials
          </Link>
          <Link to="/voting" className="btn btn-secondary">
            Vote on submissions
          </Link>
          <Link to="/submit" className="btn btn-secondary">
            Submit a video
          </Link>
          <a href="/docs" className="btn btn-secondary" target="_blank" rel="noreferrer">
            API docs
          </a>
        </div>
      </div>

      <section style={{ marginTop: "2.5rem" }}>
        <div className="flex-between" style={{ marginBottom: "1rem" }}>
          <h2 style={{ margin: 0 }}>Needs votes</h2>
          <Link to="/voting" className="muted">
            View all →
          </Link>
        </div>
        {isLoading && <p className="muted">Loading recent submissions…</p>}
        {!isLoading && recentEdits.length === 0 && (
          <p className="muted">No open submissions right now.</p>
        )}
        <div className="stack">
          {recentEdits.map((edit) => (
            <OpenEditCard key={edit.id} edit={edit} />
          ))}
        </div>
      </section>
    </div>
  );
}
