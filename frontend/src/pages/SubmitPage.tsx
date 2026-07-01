import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, canSubmit } from "../auth";
import { api, type SubmissionTerms } from "../api";
import SubmissionTermsView from "../components/SubmissionTermsView";

export default function SubmitPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [terms, setTerms] = useState<SubmissionTerms | null>(null);
  const [termsAgreed, setTermsAgreed] = useState(false);
  const [termsLoading, setTermsLoading] = useState(true);

  const [form, setForm] = useState({
    youtube_url: "",
    commercial_title: "",
    advertiser_name: "",
    year: "",
    language: "",
    region: "",
    transcript: "",
    slogan: "",
    tags: "",
    comment: "",
  });

  useEffect(() => {
    if (!user || !canSubmit(user)) {
      setTermsLoading(false);
      return;
    }
    api
      .getSubmissionTerms()
      .then(setTerms)
      .catch((err) => setError((err as Error).message))
      .finally(() => setTermsLoading(false));
  }, [user]);

  if (!user) {
    return (
      <div className="card">
        <p>You must <a href="/login">log in</a> to submit commercials.</p>
      </div>
    );
  }

  if (!canSubmit(user)) {
    return (
      <div className="card">
        <h2 className="page-title">Submit access required</h2>
        <p>
          Your account can vote on edits but cannot submit links yet. Complete the{" "}
          <a href="/submit/upgrade">submission terms quiz</a> to upgrade to a submit &amp; vote account.
        </p>
      </div>
    );
  }

  const termsOutdated =
    terms != null &&
    (user.submission_terms_version == null || user.submission_terms_version < terms.version);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!termsAgreed) {
      setError("You must agree to the Terms of Submission.");
      return;
    }
    setLoading(true);
    try {
      const edit = await api.submitVideo({
        youtube_url: form.youtube_url,
        commercial: {
          title: form.commercial_title,
          advertiser_name: form.advertiser_name || undefined,
          year: form.year ? parseInt(form.year) : undefined,
        },
        language: form.language || undefined,
        region: form.region || undefined,
        transcript: form.transcript || undefined,
        slogan: form.slogan || undefined,
        tags: form.tags ? form.tags.split(",").map((t) => t.trim()).filter(Boolean) : [],
        comment: form.comment || undefined,
        terms_agreed: true,
      });
      navigate(`/edits/${edit.id}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 760 }}>
      <h1 className="page-title">Submit Commercial Video</h1>
      <p className="muted" style={{ marginBottom: "1.5rem" }}>
        Submissions enter the edit queue for community voting. Review the terms before submitting.
      </p>

      {termsLoading && <p className="muted">Loading terms...</p>}

      {terms && (
        <details className="card terms-card" style={{ marginBottom: "1.5rem" }} open={termsOutdated}>
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>
            Terms of Submission (v{terms.version})
          </summary>
          <div style={{ marginTop: "1rem" }}>
            <SubmissionTermsView terms={terms} compact />
          </div>
        </details>
      )}

      {termsOutdated && (
        <p className="error" style={{ marginBottom: "1rem" }}>
          The submission terms have been updated. Please review and agree before submitting.
        </p>
      )}

      <form onSubmit={handleSubmit} className="card">
        <div className="form-group">
          <label>YouTube URL *</label>
          <input
            required
            value={form.youtube_url}
            onChange={(e) => setForm({ ...form, youtube_url: e.target.value })}
            placeholder="https://www.youtube.com/watch?v=..."
          />
        </div>
        <div className="form-group">
          <label>Commercial Title *</label>
          <input
            required
            value={form.commercial_title}
            onChange={(e) => setForm({ ...form, commercial_title: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label>Advertiser / Brand</label>
          <input
            value={form.advertiser_name}
            onChange={(e) => setForm({ ...form, advertiser_name: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label>Year</label>
          <input
            type="number"
            value={form.year}
            onChange={(e) => setForm({ ...form, year: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label>Language</label>
          <input
            value={form.language}
            onChange={(e) => setForm({ ...form, language: e.target.value })}
            placeholder="en"
          />
        </div>
        <div className="form-group">
          <label>Region</label>
          <input
            value={form.region}
            onChange={(e) => setForm({ ...form, region: e.target.value })}
            placeholder="US"
          />
        </div>
        <div className="form-group">
          <label>Slogan</label>
          <input
            value={form.slogan}
            onChange={(e) => setForm({ ...form, slogan: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label>Transcript</label>
          <textarea
            value={form.transcript}
            onChange={(e) => setForm({ ...form, transcript: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label>Tags (comma-separated)</label>
          <input
            value={form.tags}
            onChange={(e) => setForm({ ...form, tags: e.target.value })}
            placeholder="superbowl, automotive, humor"
          />
        </div>
        <div className="form-group">
          <label>Edit comment</label>
          <textarea
            value={form.comment}
            onChange={(e) => setForm({ ...form, comment: e.target.value })}
            placeholder="Source, context, version label, or notes for voters..."
          />
        </div>

        <label style={{ display: "flex", gap: "0.5rem", alignItems: "flex-start", marginBottom: "1rem" }}>
          <input
            type="checkbox"
            checked={termsAgreed}
            onChange={(e) => setTermsAgreed(e.target.checked)}
            style={{ marginTop: "0.25rem" }}
          />
          <span>
            I have read and agree to the{" "}
            <strong>Terms of Submission</strong>
            {terms ? ` (version ${terms.version})` : ""}.
          </span>
        </label>

        {error && <p className="error">{error}</p>}
        <button type="submit" className="btn btn-primary" disabled={loading || !termsAgreed}>
          {loading ? "Submitting..." : "Submit for review"}
        </button>
      </form>
    </div>
  );
}
