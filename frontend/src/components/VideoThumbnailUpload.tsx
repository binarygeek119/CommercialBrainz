import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Edit } from "../api";

interface Props {
  videoSbid: string;
}

export default function VideoThumbnailUpload({ videoSbid }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);
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

  return (
    <div className="card" style={{ marginTop: "1rem" }}>
      <h3>Custom thumbnail</h3>
      <p className="muted" style={{ marginBottom: "0.75rem" }}>
        Upload a replacement thumbnail (JPEG, PNG, or WebP, max 2 MB). It enters the edit queue for
        voting like other changes.
      </p>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="thumbnail-file">Image file</label>
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
          </p>
        )}
        <button type="submit" className="btn btn-secondary" disabled={loading}>
          {loading ? "Submitting…" : "Submit thumbnail for review"}
        </button>
      </form>
    </div>
  );
}
