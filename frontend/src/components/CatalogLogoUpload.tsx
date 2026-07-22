import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, type CatalogLogoSubmit, type Edit } from "../api";
import BrandLogoImage from "./BrandLogoImage";
import { LOGO_MONTHS } from "../utils/brandLogos";
import type { CatalogKindConfig } from "../catalog/kinds";

const ALLOWED_LOGO_TYPES = new Set(["image/png", "image/svg+xml", "image/webp"]);

interface Props {
  kind: CatalogKindConfig;
  entitySbid: string;
  entityName: string;
  onSubmitted?: () => void;
}

export default function CatalogLogoUpload({
  kind,
  entitySbid,
  entityName,
  onSubmitted,
}: Props) {
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
      setError("Logo must be a PNG, WebP, or SVG file.");
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
      setError("Choose a PNG, WebP, or SVG file first.");
      return;
    }
    setLoading(true);
    setError("");
    const meta: CatalogLogoSubmit = {
      label: label.trim() || undefined,
      year: year.trim() ? Number(year) : undefined,
      month: month ? Number(month) : undefined,
      event: event.trim() || undefined,
      notes: notes.trim() || undefined,
      comment: comment.trim() || undefined,
    };
    try {
      const edit = await api.submitCatalogLogo(kind.key, entitySbid, file, meta);
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
        Upload a transparent PNG, WebP, or SVG for {entityName} (max 5 MB). Goes to the edit queue
        (10 votes or mod approval), then joins the logo gallery.
      </p>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor={`${kind.key}-logo-file`}>Logo file (PNG, WebP, or SVG)</label>
          <input
            ref={inputRef}
            id={`${kind.key}-logo-file`}
            type="file"
            accept="image/png,image/webp,image/svg+xml"
            onChange={(e) => onFileChange(e.target.files?.[0])}
          />
        </div>
        {preview && (
          <div style={{ marginBottom: "0.75rem" }}>
            <BrandLogoImage src={preview} alt="Logo preview" size="preview" />
          </div>
        )}
        <div className="form-group">
          <label htmlFor={`${kind.key}-logo-label`}>Version label</label>
          <input
            id={`${kind.key}-logo-label`}
            value={label}
            onChange={(e) => setLabel(e.target.value)}
          />
        </div>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <div className="form-group" style={{ flex: "1 1 120px" }}>
            <label htmlFor={`${kind.key}-logo-year`}>Year</label>
            <input
              id={`${kind.key}-logo-year`}
              type="number"
              min={1800}
              max={2100}
              value={year}
              onChange={(e) => setYear(e.target.value)}
            />
          </div>
          <div className="form-group" style={{ flex: "1 1 160px" }}>
            <label htmlFor={`${kind.key}-logo-month`}>Month (optional)</label>
            <select
              id={`${kind.key}-logo-month`}
              value={month}
              onChange={(e) => setMonth(e.target.value)}
            >
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
          <label htmlFor={`${kind.key}-logo-event`}>Event / occasion</label>
          <input
            id={`${kind.key}-logo-event`}
            value={event}
            onChange={(e) => setEvent(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label htmlFor={`${kind.key}-logo-notes`}>Notes (optional)</label>
          <textarea
            id={`${kind.key}-logo-notes`}
            rows={2}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label htmlFor={`${kind.key}-logo-comment`}>Edit comment (optional)</label>
          <input
            id={`${kind.key}-logo-comment`}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
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
