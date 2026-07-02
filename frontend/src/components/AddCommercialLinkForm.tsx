import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type CommercialDetail, type SubmissionTerms, type YouTubeMetadataPreview } from "../api";
import { useAuth, canSubmit } from "../auth";
import SubmissionTermsView from "./SubmissionTermsView";
import { extractYouTubeId } from "../utils/youtube";
import { youtubeIdThumbnail } from "../utils/videoThumbnail";

interface Props {
  commercial: CommercialDetail;
  onSubmitted?: () => void;
}

export default function AddCommercialLinkForm({ commercial, onSubmitted }: Props) {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [versionLabel, setVersionLabel] = useState("");
  const [comment, setComment] = useState("");
  const [terms, setTerms] = useState<SubmissionTerms | null>(null);
  const [termsAgreed, setTermsAgreed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [ytMeta, setYtMeta] = useState<YouTubeMetadataPreview | null>(null);
  const lastFetchedId = useRef<string | null>(null);

  useEffect(() => {
    api.getSubmissionTerms().then(setTerms).catch(() => setTerms(null));
  }, []);

  useEffect(() => {
    const youtubeId = extractYouTubeId(youtubeUrl);
    if (!youtubeId || !canSubmit(user)) {
      setYtMeta(null);
      lastFetchedId.current = null;
      return;
    }
    if (youtubeId === lastFetchedId.current) return;

    const timer = window.setTimeout(() => {
      api
        .fetchYouTubeMetadata(youtubeUrl)
        .then((meta) => {
          lastFetchedId.current = meta.youtube_id;
          setYtMeta(meta);
        })
        .catch(() => setYtMeta(null));
    }, 400);
    return () => window.clearTimeout(timer);
  }, [youtubeUrl, user]);

  if (!user || !canSubmit(user)) {
    return (
      <p className="muted">
        <Link to="/login">Log in</Link> with submit access to add another YouTube link to this
        commercial.
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
    setLoading(true);
    try {
      const edit = await api.submitVideo({
        youtube_url: youtubeUrl,
        commercial_id: commercial.sbid,
        version_label: versionLabel.trim() || undefined,
        comment: comment.trim() || undefined,
        terms_agreed: true,
        ...(ytMeta
          ? {
              channel_name: ytMeta.channel_name || undefined,
              upload_date: ytMeta.upload_date || undefined,
              duration_ms: ytMeta.duration_ms ?? undefined,
              aspect_ratio: ytMeta.aspect_ratio || undefined,
              resolution: ytMeta.resolution || undefined,
              thumbnail_url: ytMeta.thumbnail_url || undefined,
              metadata: ytMeta.metadata,
            }
          : {}),
      });
      setYoutubeUrl("");
      setVersionLabel("");
      setComment("");
      setTermsAgreed(false);
      onSubmitted?.();
      navigate(`/edits/${edit.id}`);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card" style={{ marginTop: "1rem" }}>
      <h3 style={{ marginTop: 0 }}>Add another YouTube link</h3>
      <p className="muted" style={{ marginBottom: "1rem" }}>
        Submit alternate cuts, edits, :30/:60 versions, or backup mirrors for{" "}
        <strong>{commercial.title}</strong>. Each link is fingerprinted separately and enters the
        edit queue for approval before voting picks the main link.
      </p>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="add-link-url">YouTube URL</label>
          <input
            id="add-link-url"
            value={youtubeUrl}
            onChange={(e) => setYoutubeUrl(e.target.value)}
            placeholder="https://www.youtube.com/watch?v=..."
            required
          />
        </div>

        {ytMeta?.existing_video_sbid && (
          <p className="error">
            This YouTube ID is already in the archive.{" "}
            <Link to={`/video/${ytMeta.existing_video_sbid}`}>View existing entry</Link>
          </p>
        )}

        {(ytMeta?.thumbnail_url || ytMeta?.youtube_id) && (
          <img
            src={ytMeta.thumbnail_url || youtubeIdThumbnail(ytMeta.youtube_id)}
            alt=""
            style={{
              width: "100%",
              maxWidth: 320,
              aspectRatio: "16 / 9",
              objectFit: "cover",
              borderRadius: "var(--radius)",
              marginBottom: "1rem",
            }}
          />
        )}

        <div className="form-group">
          <label htmlFor="add-link-version">Version label (optional)</label>
          <input
            id="add-link-version"
            value={versionLabel}
            onChange={(e) => setVersionLabel(e.target.value)}
            placeholder='e.g. "30s cut", "Directors edit", "Backup mirror"'
          />
        </div>

        <div className="form-group">
          <label htmlFor="add-link-comment">Comment (optional)</label>
          <textarea
            id="add-link-comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={2}
            placeholder="Why this version belongs with this commercial…"
          />
        </div>

        {terms && (
          <div style={{ marginBottom: "1rem" }}>
            <SubmissionTermsView terms={terms} />
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

        <button type="submit" className="btn btn-primary" disabled={loading || !!ytMeta?.existing_video_sbid}>
          {loading ? "Submitting…" : "Submit link for review"}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      <p className="muted" style={{ marginTop: "0.75rem", marginBottom: 0 }}>
        Need full metadata fields?{" "}
        <Link to={`/submit?commercial=${encodeURIComponent(commercial.sbid)}`}>
          Use the full submit form
        </Link>
      </p>
    </div>
  );
}
