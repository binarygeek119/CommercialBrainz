import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type CommercialDetail, type SubmissionTerms, type Video } from "../api";
import { useAuth, canSubmit } from "../auth";
import SubmissionTermsView from "./SubmissionTermsView";
import { COMMERCIAL_DECADES } from "../utils/commercialPeriod";
import { commercialInheritanceSummary } from "../utils/addLinkDefaults";
import { videoDisplayTitle } from "../utils/videoMetadata";

interface Props {
  commercial: CommercialDetail;
  video: Video;
  onSubmitted?: () => void;
}

type FormState = {
  title: string;
  campaign_name: string;
  description: string;
  year: string;
  decade: string;
  products: string;
  comment: string;
};

function suggestedSplitTitle(commercial: CommercialDetail, video: Video): string {
  const label = (video.version_label || video.slogan || "").trim();
  if (label) return `${commercial.title} (${label})`;
  return commercial.title;
}

function toFormState(commercial: CommercialDetail, video: Video): FormState {
  return {
    title: suggestedSplitTitle(commercial, video),
    campaign_name: commercial.campaign_name ?? "",
    description: commercial.description ?? "",
    year: commercial.year != null ? String(commercial.year) : "",
    decade: commercial.decade != null ? String(commercial.decade) : "",
    products: (commercial.products ?? []).join(", "),
    comment: "",
  };
}

export default function SplitCommercialLinkForm({ commercial, video, onSubmitted }: Props) {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState(() => toFormState(commercial, video));
  const [terms, setTerms] = useState<SubmissionTerms | null>(null);
  const [termsAgreed, setTermsAgreed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setForm(toFormState(commercial, video));
    setTermsAgreed(false);
    setError("");
  }, [commercial.sbid, video.sbid]);

  useEffect(() => {
    api.getSubmissionTerms().then(setTerms).catch(() => setTerms(null));
  }, []);

  if (!user || !canSubmit(user)) {
    return (
      <p className="muted" style={{ fontSize: "0.85rem" }}>
        <Link to="/login">Log in</Link> with submit access to propose splitting this link into its
        own commercial.
      </p>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!termsAgreed) {
      setError("You must agree to the Terms of Submission.");
      return;
    }
    if (!form.title.trim()) {
      setError("Title is required for the new commercial.");
      return;
    }

    setLoading(true);
    try {
      const year = form.year.trim() ? Number(form.year) : null;
      const decade = form.decade.trim() ? Number(form.decade) : null;
      const products = form.products
        .split(/[,;\n]/)
        .map((s) => s.trim())
        .filter(Boolean);

      const edit = await api.submitCommercialSplit(commercial.sbid, video.sbid, {
        title: form.title.trim(),
        campaign_name: form.campaign_name.trim() || null,
        description: form.description.trim() || null,
        year: year != null && !Number.isNaN(year) ? year : null,
        decade: decade != null && !Number.isNaN(decade) ? decade : null,
        products,
        comment: form.comment.trim() || undefined,
        terms_agreed: true,
      });
      onSubmitted?.();
      navigate(`/edits/${edit.id}`);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const inherited = commercialInheritanceSummary(commercial);

  return (
    <form onSubmit={handleSubmit} className="card" style={{ marginTop: "0.75rem", padding: "0.85rem 1rem" }}>
      <h4 style={{ margin: "0 0 0.35rem" }}>Split into its own commercial</h4>
      <p className="muted" style={{ margin: "0 0 0.75rem", fontSize: "0.85rem" }}>
        Propose that <strong>{videoDisplayTitle(video)}</strong> is a separate commercial (its own
        master link), not a sub link on <strong>{commercial.title}</strong>. Split proposals need{" "}
        <strong>20 yes votes</strong> for early approval, or resolve after <strong>3 months</strong>{" "}
        if yes votes outnumber no (minimum one yes vote). Moderators can decide at any time.
      </p>

      <div
        style={{
          marginBottom: "0.75rem",
          padding: "0.65rem 0.75rem",
          background: "var(--surface)",
          borderRadius: "var(--radius)",
        }}
      >
        <p style={{ margin: 0, fontWeight: 600, fontSize: "0.9rem" }}>Currently grouped with</p>
        <ul style={{ margin: "0.35rem 0 0", paddingLeft: "1.1rem" }}>
          {inherited.map((line) => (
            <li key={line} className="muted" style={{ fontSize: "0.85rem" }}>
              {line}
            </li>
          ))}
        </ul>
      </div>

      <div className="form-group">
        <label htmlFor={`split-title-${video.sbid}`}>New commercial title *</label>
        <input
          id={`split-title-${video.sbid}`}
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
          required
        />
      </div>
      <div className="form-group">
        <label htmlFor={`split-campaign-${video.sbid}`}>Campaign name</label>
        <input
          id={`split-campaign-${video.sbid}`}
          value={form.campaign_name}
          onChange={(e) => setForm({ ...form, campaign_name: e.target.value })}
        />
      </div>
      <div className="form-group">
        <label htmlFor={`split-decade-${video.sbid}`}>Decade aired</label>
        <select
          id={`split-decade-${video.sbid}`}
          value={form.decade}
          onChange={(e) => setForm({ ...form, decade: e.target.value })}
        >
          <option value="">Unknown / not sure</option>
          {COMMERCIAL_DECADES.map((d) => (
            <option key={d} value={d}>
              {d}s
            </option>
          ))}
        </select>
      </div>
      <div className="form-group">
        <label htmlFor={`split-year-${video.sbid}`}>Exact year</label>
        <input
          id={`split-year-${video.sbid}`}
          type="number"
          min={1900}
          max={2100}
          value={form.year}
          onChange={(e) => setForm({ ...form, year: e.target.value })}
        />
      </div>
      <div className="form-group">
        <label htmlFor={`split-products-${video.sbid}`}>Products</label>
        <input
          id={`split-products-${video.sbid}`}
          value={form.products}
          onChange={(e) => setForm({ ...form, products: e.target.value })}
          placeholder="Comma-separated"
        />
      </div>
      <div className="form-group">
        <label htmlFor={`split-description-${video.sbid}`}>Description</label>
        <textarea
          id={`split-description-${video.sbid}`}
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
          rows={2}
        />
      </div>
      <div className="form-group">
        <label htmlFor={`split-comment-${video.sbid}`}>Why is this a separate commercial?</label>
        <textarea
          id={`split-comment-${video.sbid}`}
          value={form.comment}
          onChange={(e) => setForm({ ...form, comment: e.target.value })}
          rows={2}
          placeholder="Different product, campaign, or spot — not just a cut length or mirror…"
        />
      </div>

      {terms && (
        <div style={{ marginBottom: "0.75rem" }}>
          <SubmissionTermsView terms={terms} compact />
          <label style={{ display: "flex", gap: "0.5rem", alignItems: "flex-start" }}>
            <input
              type="checkbox"
              checked={termsAgreed}
              onChange={(e) => setTermsAgreed(e.target.checked)}
            />
            <span>I agree to the Terms of Submission</span>
          </label>
        </div>
      )}

      <button type="submit" className="btn btn-secondary" disabled={loading || !form.title.trim()}>
        {loading ? "Submitting…" : "Submit split proposal for vote"}
      </button>
      {error && <p className="error" style={{ marginTop: "0.5rem" }}>{error}</p>}
    </form>
  );
}
