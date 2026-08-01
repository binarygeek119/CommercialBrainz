import { useRef, useState } from "react";
import { Link } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { api, type Edit } from "../api";

interface Props {
  videoSbid: string;
  thumbnailFetchStatus?: string | null;
}

export default function VideoThumbnailUpload({ videoSbid, thumbnailFetchStatus }: Props) {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [refreshMsg, setRefreshMsg] = useState("");
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

  const handleForceRefresh = async () => {
    setRefreshing(true);
    setError("");
    setRefreshMsg("");
    try {
      await api.refreshVideoThumbnail(videoSbid);
      setRefreshMsg(
        "Queued: trying YouTube thumbnail again, then a random padded frame from the stream if needed."
      );
      await queryClient.invalidateQueries({ queryKey: ["video", videoSbid] });
      await queryClient.invalidateQueries({ queryKey: ["commercial"] });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setRefreshing(false);
    }
  };

  const fetchBusy =
    thumbnailFetchStatus === "pending" || thumbnailFetchStatus === "retry";

  return (
    <div className="card" style={{ marginTop: "1rem" }}>
      <h3>Thumbnail</h3>
      <p className="muted" style={{ marginBottom: "0.75rem" }}>
        Re-grab from YouTube, or upload a custom image for the edit queue.
      </p>

      <div style={{ marginBottom: "1rem" }}>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={handleForceRefresh}
          disabled={refreshing || fetchBusy}
        >
          {refreshing || fetchBusy ? "Refreshing thumbnail…" : "Force re-grab thumbnail"}
        </button>
        <p className="muted" style={{ marginTop: "0.5rem", marginBottom: 0, fontSize: "0.85rem" }}>
          Tries the YouTube thumbnail again. If that fails, streams the video and grabs a random
          frame with padding at the start and end.
          {thumbnailFetchStatus ? ` Status: ${thumbnailFetchStatus}.` : ""}
        </p>
        {refreshMsg && <p style={{ marginTop: "0.5rem", marginBottom: 0 }}>{refreshMsg}</p>}
      </div>

      <hr style={{ border: 0, borderTop: "1px solid var(--border, #ddd)", margin: "1rem 0" }} />

      <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem" }}>Custom thumbnail</h4>
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
