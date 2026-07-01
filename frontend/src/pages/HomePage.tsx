import { Link } from "react-router-dom";

export default function HomePage() {
  return (
    <div className="hero">
      <h1>CommercialBrainz</h1>
      <p>
        The open commercial video database. One entry per YouTube video, rich metadata,
        community edits, and MusicBrainz-style voting.
      </p>
      <div style={{ display: "flex", gap: "1rem", justifyContent: "center", flexWrap: "wrap" }}>
        <Link to="/browse" className="btn btn-primary">
          Browse commercials
        </Link>
        <Link to="/submit" className="btn btn-secondary">
          Submit a video
        </Link>
        <a href="/docs" className="btn btn-secondary" target="_blank" rel="noreferrer">
          API docs
        </a>
      </div>
    </div>
  );
}
