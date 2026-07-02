import { Link } from "react-router-dom";
import { APP_VERSION } from "../version";

export default function AboutPage() {
  return (
    <div style={{ maxWidth: 760 }}>
      <h1 className="page-title">About CommercialBrainz</h1>
      <p className="muted" style={{ marginBottom: "1.5rem" }}>
        An open, community-maintained archive of TV and online commercials — one YouTube link at a
        time, with rich metadata and MusicBrainz-style editing.
      </p>

      <section className="card" style={{ marginBottom: "1.25rem" }}>
        <h2 style={{ marginTop: 0 }}>What is this?</h2>
        <p>
          <strong>CommercialBrainz</strong> catalogs commercials the way{" "}
          <a href="https://musicbrainz.org" target="_blank" rel="noreferrer">
            MusicBrainz
          </a>{" "}
          catalogs music. Each entry ties a commercial (brand, campaign, air date, products) to a
          specific YouTube upload. The goal is a searchable, scrape-friendly public record that
          outlives broken links and platform churn.
        </p>
        <p style={{ marginBottom: 0 }}>
          Anyone can browse. Registered users vote on community edits. Submitters add new links and
          metadata improvements. Moderators and admins help keep quality high.
        </p>
      </section>

      <section className="card" style={{ marginBottom: "1.25rem" }}>
        <h2 style={{ marginTop: 0 }}>How entries work</h2>
        <ul style={{ marginBottom: 0, paddingLeft: "1.2rem" }}>
          <li>
            <strong>Commercial</strong> — the campaign: title, brand, decade/year, products, and
            related metadata.
          </li>
          <li>
            <strong>YouTube link</strong> — one upload of that spot. A commercial has one{" "}
            <strong>master link</strong> (main upload) and optional <strong>sub links</strong>{" "}
            (alternate cuts, mirrors, regional copies). Each is fingerprinted separately.
          </li>
          <li>
            <strong>Master link</strong> — chosen by community popularity votes; carries the primary
            metadata for the commercial.
          </li>
          <li>
            <strong>Sub links</strong> — inherit master/commercial metadata; only link-specific
            differences are filled in. See <Link to="/terms">Terms</Link> for split rules.
          </li>
          <li>
            <strong>Edits</strong> — changes go through an open review queue. Voters and moderators
            decide whether submissions are applied or rejected.
          </li>
        </ul>
      </section>

      <section className="card" style={{ marginBottom: "1.25rem" }}>
        <h2 style={{ marginTop: 0 }}>Get involved</h2>
        <div className="stack" style={{ gap: "0.75rem" }}>
          <p style={{ margin: 0 }}>
            <Link to="/browse">Browse</Link> recent commercials and{" "}
            <Link to="/search">search</Link> by brand, tag, or title.
          </p>
          <p style={{ margin: 0 }}>
            <Link to="/register">Register</Link> to vote on open edits. Read the{" "}
            <Link to="/terms">Terms of Submission</Link> and complete the submission quiz to unlock{" "}
            <Link to="/submit">submitting</Link> new links and metadata.
          </p>
          <p style={{ margin: 0 }}>
            <Link to="/voting">Vote on submissions</Link> — approvals earn reputation points and
            unlock more concurrent submit slots.
          </p>
          <p style={{ margin: 0 }}>
            Developers: public JSON API and nightly dumps under{" "}
            <a href="/docs" target="_blank" rel="noreferrer">
              CC0
            </a>
            . See <a href="/docs" target="_blank" rel="noreferrer">API docs</a>.
          </p>
        </div>
      </section>

      <section className="card" style={{ marginBottom: "1.25rem" }}>
        <h2 style={{ marginTop: 0 }}>Identifiers</h2>
        <p>
          Every commercial, video, brand, and edit has a <strong>CommercialBrainz ID</strong> (CBID)
          — a UUID used in URLs and the API, for example:
        </p>
        <p className="mono muted" style={{ fontSize: "0.9rem", marginBottom: 0 }}>
          /commercial/550e8400-e29b-41d4-a716-446655440000
        </p>
      </section>

      <section className="card" style={{ marginBottom: "1.25rem" }}>
        <h2 style={{ marginTop: 0 }}>Copyright &amp; takedowns</h2>
        <p>
          Metadata is preserved for archival purposes. Copyright holders can request link removal
          via the <Link to="/dmca">DMCA process</Link>. Contact:{" "}
          <a href="mailto:commercialbrainz@outlook.com">commercialbrainz@outlook.com</a>
        </p>
        <p style={{ marginBottom: 0 }}>
          Database contents are released under{" "}
          <a
            href="https://creativecommons.org/publicdomain/zero/1.0/"
            target="_blank"
            rel="noreferrer"
          >
            CC0 1.0 Universal
          </a>
          .
        </p>
      </section>

      <p className="muted" style={{ fontSize: "0.9rem" }}>
        CommercialBrainz v{APP_VERSION}
      </p>
    </div>
  );
}
