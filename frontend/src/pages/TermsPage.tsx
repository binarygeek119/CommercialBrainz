import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type SubmissionTerms } from "../api";
import { useAuth, canSubmit, isVoteOnly } from "../auth";
import SubmissionTermsView from "../components/SubmissionTermsView";

const SPLIT_VOTE_THRESHOLD = 20;
const SPLIT_OPEN_MONTHS = 3;

export default function TermsPage() {
  const { user } = useAuth();
  const [terms, setTerms] = useState<SubmissionTerms | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getSubmissionTerms()
      .then(setTerms)
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, []);

  const termsOutdated =
    terms != null &&
    user != null &&
    canSubmit(user) &&
    (user.submission_terms_version == null || user.submission_terms_version < terms.version);

  return (
    <div style={{ maxWidth: 760 }}>
      <h1 className="page-title">Terms of Submission</h1>
      <p className="muted" style={{ marginBottom: "1.25rem" }}>
        Rules for adding commercials, YouTube links, and metadata to CommercialBrainz. You must
        read and agree to the current version before submitting edits.
      </p>

      <section className="card" style={{ marginBottom: "1.25rem" }}>
        <h2 style={{ marginTop: 0 }}>Master links and sub links</h2>
        <p>
          A <strong>commercial</strong> is one campaign or spot. It can have one{" "}
          <strong>master link</strong> — the main YouTube upload — plus optional{" "}
          <strong>sub links</strong>, which are additional uploads on the same commercial.
        </p>
        <ul style={{ paddingLeft: "1.2rem", marginBottom: "1rem" }}>
          <li>
            <strong>Master link</strong> — the primary link for the commercial. It holds the main
            metadata (title, brand, air date, products, and so on). Popularity votes pick which link
            is the master link.
          </li>
          <li>
            <strong>Sub link</strong> — an extra upload on the same commercial (alternate cut,
            backup mirror, regional copy, etc.). Sub links inherit metadata from the master link and
            the commercial; you only fill in what differs for that upload.
          </li>
        </ul>
        <p style={{ marginBottom: 0 }}>
          If a sub link is really a different commercial, anyone with submit access can propose a{" "}
          <strong>split</strong> so it becomes its own master link. Split proposals stay open for up
          to {SPLIT_OPEN_MONTHS} months. They pass early with{" "}
          <strong>{SPLIT_VOTE_THRESHOLD} yes votes</strong>, or after {SPLIT_OPEN_MONTHS} months if
          yes votes outnumber no votes (at least one yes vote required). Moderators can approve or
          reject at any time. Full rules are in section 2 below.
        </p>
      </section>

      {!loading && !error && terms && (
        <p className="muted" style={{ marginBottom: "1.25rem", fontSize: "0.9rem" }}>
          Current version: <strong>v{terms.version}</strong>
          {user && canSubmit(user) && user.submission_terms_version != null && (
            <>
              {" "}
              · Your accepted version:{" "}
              <strong>v{user.submission_terms_version}</strong>
              {termsOutdated && (
                <span className="error"> — please review and re-agree on your next submission</span>
              )}
            </>
          )}
        </p>
      )}

      {loading && <p className="muted">Loading terms…</p>}
      {error && <p className="error">{error}</p>}

      {terms && (
        <div className="card terms-card" style={{ marginBottom: "1.25rem" }}>
          <SubmissionTermsView terms={terms} />
        </div>
      )}

      <section className="card">
        <h2 style={{ marginTop: 0 }}>Next steps</h2>
        {!user && (
          <p style={{ marginBottom: 0 }}>
            <Link to="/register">Create an account</Link> to vote on edits. New accounts start as
            vote-only — pass the submission quiz to unlock submitting.
          </p>
        )}
        {user && isVoteOnly(user) && (
          <p style={{ marginBottom: 0 }}>
            Your account is vote-only. After reading the terms above, take the{" "}
            <Link to="/submit/upgrade">submission quiz</Link> to unlock submit access.
          </p>
        )}
        {user && canSubmit(user) && (
          <p style={{ marginBottom: 0 }}>
            You can submit commercials and links from the{" "}
            <Link to="/submit">submit page</Link>. Each submission requires agreeing to the current
            terms version.
            {termsOutdated && (
              <>
                {" "}
                Your saved acceptance is outdated — open <Link to="/submit">Submit</Link> to review
                and agree again.
              </>
            )}
          </p>
        )}
        {user && !canSubmit(user) && !isVoteOnly(user) && (
          <p className="muted" style={{ marginBottom: 0 }}>
            Submit access is not enabled on your account. Contact a moderator if you believe this is
            an error.
          </p>
        )}
      </section>

      <p className="muted" style={{ marginTop: "1.25rem", fontSize: "0.9rem" }}>
        See also <Link to="/about">About</Link> and <Link to="/dmca">DMCA policy</Link>.
      </p>
    </div>
  );
}
