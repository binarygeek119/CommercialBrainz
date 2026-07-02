import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, type AdvertiserLogoSubmit, type Edit } from "../api";
import { LOGO_MONTHS } from "../utils/brandLogos";

const ALLOWED_LOGO_TYPES = new Set(["image/png", "image/svg+xml"]);

interface Props {
  advertiserSbid: string;
  brandName: string;
  onSubmitted?: () => void;
}

export default function BrandLogoUpload({ advertiserSbid, brandName, onSubmitted }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [label, setLabel] = useState("");
  const [year, setYear] = useState("");
  const [month, setMonth] = useState("");
  const [event, setEvent] = useState("");
  const [notes, setNotes] = useState("");
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
    if (!ALLOWED_LOGO_TYPES.has(file.type)) {
      setError("Logo must be a PNG or SVG file.");
      setPreview(null);
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError("Logo must be 5 MB or smaller.");
      setPreview(null);
      return;
    }
    setPreview(URL.createObjectURL(file));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const file = inputRef.current?.files?.[0];
    if (!file) {
      setError("Choose a PNG or SVG file first.");
      return;
    }
    setLoading(true);
    setError("");
    const meta: AdvertiserLogoSubmit = {
      label: label.trim() || undefined,
      year: year.trim() ? Number(year) : undefined,
      month: month ? Number(month) : undefined,
      event: event.trim() || undefined,
      notes: notes.trim() || undefined,
      comment: comment.trim() || undefined,
    };
    try {
      const edit = await api.submitAdvertiserLogo(advertiserSbid, file, meta);
      setResult(edit);
      setPreview(null);
      setLabel("");
      setYear("");
      setMonth("");
      setEvent("");
      setNotes("");
      setComment("");
      if (inputRef.current) inputRef.current.value = "";
      onSubmitted?.();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card" style={{ marginTop: "1rem" }}>
      <h3>Submit logo version</h3>
      <p className="muted" style={{ marginBottom: "0.75rem" }}>
        Upload a transparent PNG or SVG for {brandName} (max 5 MB; PNG must be at least 32×32 px).
        Add context for historical or event-specific wordmarks — e.g. a 2019 refresh, Olympic
        campaign, or 50th anniversary lockup. Goes to the edit queue (10 votes or mod approval),
        then joins the logo gallery where users vote on popularity to pick the main logo.
      </p>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="logo-file">Logo file (PNG or SVG)</label>
          <input
            ref={inputRef}
            id="logo-file"
            type="file"
            accept="image/png,image/svg+xml"
            onChange={(e) => onFileChange(e.target.files?.[0])}
          />
        </div>
        {preview && (
          <div
            style={{
              background:
                "repeating-conic-gradient(#ccc 0% 25%, #fff 0% 50%) 50% / 16px 16px",
              padding: "1rem",
              borderRadius: 4,
              marginBottom: "0.75rem",
              display: "inline-block",
            }}
          >
            <img
              src={preview}
              alt="Logo preview"
              style={{ maxWidth: 240, maxHeight: 240, display: "block" }}
            />
          </div>
        )}
        <div className="form-group">
          <label htmlFor="logo-label">Version label</label>
          <input
            id="logo-label"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder='e.g. "2019 wordmark", "Script logo"'
          />
        </div>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <div className="form-group" style={{ flex: "1 1 120px" }}>
            <label htmlFor="logo-year">Year</label>
            <input
              id="logo-year"
              type="number"
              min={1800}
              max={2100}
              value={year}
              onChange={(e) => setYear(e.target.value)}
              placeholder="2019"
            />
          </div>
          <div className="form-group" style={{ flex: "1 1 160px" }}>
            <label htmlFor="logo-month">Month (optional)</label>
            <select id="logo-month" value={month} onChange={(e) => setMonth(e.target.value)}>
              <option value="">—</option>
              {LOGO_MONTHS.map((name, index) => (
                <option key={name} value={String(index + 1)}>
                  {name}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="form-group">
          <label htmlFor="logo-event">Event / occasion</label>
          <input
            id="logo-event"
            value={event}
            onChange={(e) => setEvent(e.target.value)}
            placeholder='e.g. "50th anniversary", "Super Bowl LVIII"'
          />
        </div>
        <div className="form-group">
          <label htmlFor="logo-notes">Notes (optional)</label>
          <textarea
            id="logo-notes"
            rows={2}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Source, usage context, or differences from other versions…"
          />
        </div>
        <div className="form-group">
          <label htmlFor="logo-comment">Edit comment (optional)</label>
          <input
            id="logo-comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Why this version belongs in the archive…"
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
          {loading ? "Submitting…" : "Submit logo for review"}
        </button>
      </form>
    </div>
  );
}
