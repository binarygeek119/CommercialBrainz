import { useEffect, useState } from "react";
import { Link } from "react-router";
import termsOverviewMd from "@site-docs/terms-overview.md?raw";
import { api, type SubmissionTerms } from "../api";
import { useAuth, canSubmit, isVoteOnly } from "../auth";
import SiteDocMarkdown from "../components/SiteDocMarkdown";
import SubmissionTermsView from "../components/SubmissionTermsView";
import { needsSubmissionTermsAgreement } from "../utils/submissionTerms";

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

  const termsOutdated = needsSubmissionTermsAgreement(user, terms?.version);

  return (
    <div style={{ maxWidth: 760 }}>
      <SiteDocMarkdown
        source={termsOverviewMd}
        file="terms-overview.md"
        className="card"
      />

      <div style={{ marginTop: "1.25rem" }}>
        {!loading && !error && terms && (
          <p className="muted" style={{ marginBottom: "1.25rem", fontSize: "0.9rem" }}>
            Current Submission Terms version: <strong>v{terms.version}</strong>
            {user && user.submission_terms_version != null && (
              <>
                {" "}
                · Your accepted version:{" "}
                <strong>v{user.submission_terms_version}</strong>
                {user.submission_terms_accepted_at && (
                  <>
                    {" "}
                    on{" "}
                    <strong>
                      {new Date(user.submission_terms_accepted_at).toLocaleDateString()}
                    </strong>
                  </>
                )}
                {termsOutdated && (
                  <span className="error"> — please review and agree again in the popup</span>
                )}
              </>
            )}
            {user && user.submission_terms_version == null && (
              <span className="error"> · You have not agreed yet</span>
            )}
          </p>
        )}

        {loading && <p className="muted">Loading Submission Terms…</p>}
        {error && <p className="error">{error}</p>}

        {terms && (
          <div className="card terms-card" style={{ marginBottom: "1.25rem" }}>
            <SubmissionTermsView terms={terms} />
          </div>
        )}
      </div>

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
            <Link to="/submit">submit page</Link>. Agreement is recorded once in your account
            (and again if the terms version changes).
            {termsOutdated && (
              <>
                {" "}
                Your saved acceptance is outdated — use the Terms popup to agree again.
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
        See also <Link to="/about">About</Link>, <Link to="/help">Help</Link>, and{" "}
        <Link to="/dmca">DMCA policy</Link>.
      </p>
    </div>
  );
}
