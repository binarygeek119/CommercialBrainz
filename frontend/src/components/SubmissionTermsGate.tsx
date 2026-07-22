import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api, type SubmissionTerms } from "../api";
import { useAuth } from "../auth";
import { needsSubmissionTermsAgreement } from "../utils/submissionTerms";
import SubmissionTermsView from "./SubmissionTermsView";

/** Routes where the blocking terms popup should not interrupt auth flows. */
const SKIP_PATHS = new Set([
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/verify-email/pending",
]);

export default function SubmissionTermsGate() {
  const { user, loading: authLoading, refresh } = useAuth();
  const location = useLocation();
  const [terms, setTerms] = useState<SubmissionTerms | null>(null);
  const [termsError, setTermsError] = useState("");
  const [agreeing, setAgreeing] = useState(false);
  const [acceptError, setAcceptError] = useState("");

  useEffect(() => {
    if (!user) {
      setTerms(null);
      return;
    }
    let cancelled = false;
    api
      .getSubmissionTerms()
      .then((doc) => {
        if (!cancelled) {
          setTerms(doc);
          setTermsError("");
        }
      })
      .catch((err) => {
        if (!cancelled) setTermsError((err as Error).message);
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (authLoading || !user || SKIP_PATHS.has(location.pathname)) {
    return null;
  }

  const mustAgree = needsSubmissionTermsAgreement(user, terms?.version);
  if (!mustAgree && !termsError) {
    return null;
  }

  // Still loading terms for a user who may need them.
  if (!terms && !termsError) {
    return (
      <div className="terms-gate-overlay" role="dialog" aria-modal="true" aria-labelledby="terms-gate-title">
        <div className="terms-gate-card">
          <p className="muted">Loading Terms of Submission…</p>
        </div>
      </div>
    );
  }

  if (termsError) {
    return (
      <div className="terms-gate-overlay" role="dialog" aria-modal="true" aria-labelledby="terms-gate-title">
        <div className="terms-gate-card">
          <h1 id="terms-gate-title" className="terms-gate-title">
            Terms of Submission
          </h1>
          <p className="error">{termsError}</p>
          <button type="button" className="btn btn-primary" onClick={() => window.location.reload()}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!terms || !mustAgree) {
    return null;
  }

  const accept = async () => {
    setAcceptError("");
    setAgreeing(true);
    try {
      await api.acceptSubmissionTerms();
      await refresh();
    } catch (err) {
      setAcceptError((err as Error).message);
    } finally {
      setAgreeing(false);
    }
  };

  const isUpdate =
    user.submission_terms_version != null && user.submission_terms_version < terms.version;

  return (
    <div className="terms-gate-overlay" role="dialog" aria-modal="true" aria-labelledby="terms-gate-title">
      <div className="terms-gate-card">
        <p className="terms-gate-badge">{isUpdate ? "Updated terms" : "Required once"}</p>
        <h1 id="terms-gate-title" className="terms-gate-title">
          Terms of Submission
        </h1>
        <p>
          {isUpdate
            ? "The Terms of Submission have been updated. Please review and agree to continue."
            : "Before using CommercialBrainz, please read and agree to the Terms of Submission. This is only required once (or again when the terms change)."}
        </p>
        <p className="muted" style={{ fontSize: "0.9rem", marginBottom: "0.75rem" }}>
          Version <strong>v{terms.version}</strong>
          {" · "}
          <Link to="/terms" target="_blank" rel="noreferrer">
            Open full page
          </Link>
        </p>
        <div className="terms-gate-scroll">
          <SubmissionTermsView terms={terms} compact />
        </div>
        {acceptError && <p className="error">{acceptError}</p>}
        <button
          type="button"
          className="btn btn-primary terms-gate-btn"
          onClick={accept}
          disabled={agreeing}
        >
          {agreeing ? "Saving…" : "I agree to the Terms of Submission"}
        </button>
      </div>
    </div>
  );
}
