import { useRef, useState } from "react";
import { Link } from "react-router";
import { api, type Edit } from "../api";

interface Props {
  videoSbid: string;
}

export default function VideoThumbnailUpload({ videoSbid }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);
  const [regrabbing, setRegrabbing] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Edit | null>(null);

  const onFileChange = (file: File | undefined) => {
    setError("");
    setResult(null);
    if (!file) {
      setPreview(null);
      return;
    }
    if (!file.type.match(/^image\/(jpeg|png|webp)$/)) {
      setError("Choose a JPEG, PNG, or WebP image.");
      setPreview(null);
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setError("Image must be 2 MB or smaller.");
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const file = inputRef.current?.files?.[0];
    if (!file) {
      setError("Choose an image first.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const edit = await api.submitVideoThumbnail(videoSbid, file, comment || undefined);
      setResult(edit);
      setPreview(null);
      setComment("");
      if (inputRef.current) inputRef.current.value = "";
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleRegrab = async () => {
    setRegrabbing(true);
    setError("");
    setResult(null);
    try {
      const edit = await api.regrabVideoThumbnail(videoSbid);
      setResult(edit);
      setPreview(null);
      if (inputRef.current) inputRef.current.value = "";
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setRegrabbing(false);
    }
  };

  const busy = loading || regrabbing;

  return (
    <div className="card" style={{ marginTop: "1rem" }}>
      <h3>Thumbnail</h3>
      <p className="muted" style={{ marginBottom: "0.75rem" }}>
        Upload a replacement image, or force re-grab the current YouTube thumbnail. Both enter the
        edit queue for voting like other changes.
      </p>

      <div style={{ marginBottom: "1rem" }}>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={busy}
          onClick={() => void handleRegrab()}
        >
          {regrabbing ? "Re-grabbing…" : "Force re-grab thumbnail"}
        </button>
        <p className="muted" style={{ fontSize: "0.85rem", marginTop: "0.35rem", marginBottom: 0 }}>
          Downloads a fresh copy from YouTube even if the CDN URL looks unchanged.
        </p>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="thumbnail-file">Custom image file</label>
          <input
            ref={inputRef}
            id="thumbnail-file"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(e) => onFileChange(e.target.files?.[0])}
          />
        </div>
        {preview && (
          <img
            src={preview}
            alt="Preview"
            style={{
              width: "100%",
              maxHeight: 240,
              objectFit: "cover",
              borderRadius: 4,
              marginBottom: "0.75rem",
            }}
          />
        )}
        <div className="form-group">
          <label htmlFor="thumbnail-comment">Edit comment (optional)</label>
          <input
            id="thumbnail-comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Why this frame is a better thumbnail…"
          />
        </div>
        {error && <p className="error">{error}</p>}
        {result && (
          <p style={{ marginBottom: "0.75rem" }}>
            Submitted for review —{" "}
            <Link to={`/edits/${result.id}`}>view edit #{result.id.slice(0, 8)}</Link>
            {typeof result.after_state?.thumbnail_url === "string" && (
              <>
                {" "}
                ·{" "}
                <img
                  src={result.after_state.thumbnail_url as string}
                  alt="Proposed thumbnail"
                  style={{
                    height: 48,
                    width: 86,
                    objectFit: "cover",
                    verticalAlign: "middle",
                    borderRadius: 2,
                  }}
                />
              </>
            )}
          </p>
        )}
        <button type="submit" className="btn btn-secondary" disabled={busy}>
          {loading ? "Submitting…" : "Submit custom thumbnail for review"}
        </button>
      </form>
    </div>
  );
}
