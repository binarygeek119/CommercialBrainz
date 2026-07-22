import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type CatalogLogo, type CatalogLogoSubmit, type Edit } from "../api";
import { LOGO_MONTHS } from "../utils/brandLogos";
import type { CatalogKindConfig } from "../catalog/kinds";

interface Props {
  kind: CatalogKindConfig;
  entitySbid: string;
  logo: CatalogLogo;
  onSubmitted?: () => void;
}

type FormState = {
  label: string;
  year: string;
  month: string;
  event: string;
  notes: string;
};

function toFormState(logo: CatalogLogo): FormState {
  return {
    label: logo.label ?? "",
    year: logo.year != null ? String(logo.year) : "",
    month: logo.month != null ? String(logo.month) : "",
    event: logo.event ?? "",
    notes: logo.notes ?? "",
  };
}

function toPayload(form: FormState): CatalogLogoSubmit {
  const year = form.year.trim() ? Number(form.year) : undefined;
  const month = form.month ? Number(form.month) : undefined;
  return {
    label: form.label.trim() || undefined,
    year: year != null && !Number.isNaN(year) ? year : undefined,
    month: month != null && !Number.isNaN(month) ? month : undefined,
    event: form.event.trim() || undefined,
    notes: form.notes.trim() || undefined,
  };
}

export default function CatalogLogoMetadataForm({
  kind,
  entitySbid,
  logo,
  onSubmitted,
}: Props) {
  const initial = useMemo(() => toFormState(logo), [logo]);
  const [form, setForm] = useState<FormState>(initial);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Edit | null>(null);

  const update = (patch: Partial<FormState>) => setForm((prev) => ({ ...prev, ...patch }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const edit = await api.submitCatalogLogoMetadata(
        kind.key,
        entitySbid,
        logo.id,
        toPayload(form)
      );
      setResult(edit);
      onSubmitted?.();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ marginTop: "0.75rem" }}>
      <div className="form-group">
        <label htmlFor={`cat-logo-label-${logo.id}`}>Version label</label>
        <input
          id={`cat-logo-label-${logo.id}`}
          value={form.label}
          onChange={(e) => update({ label: e.target.value })}
        />
      </div>
      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
        <div className="form-group" style={{ flex: "1 1 120px" }}>
          <label htmlFor={`cat-logo-year-${logo.id}`}>Year</label>
          <input
            id={`cat-logo-year-${logo.id}`}
            type="number"
            min={1800}
            max={2100}
            value={form.year}
            onChange={(e) => update({ year: e.target.value })}
          />
        </div>
        <div className="form-group" style={{ flex: "1 1 160px" }}>
          <label htmlFor={`cat-logo-month-${logo.id}`}>Month (optional)</label>
          <select
            id={`cat-logo-month-${logo.id}`}
            value={form.month}
            onChange={(e) => update({ month: e.target.value })}
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
        <label htmlFor={`cat-logo-event-${logo.id}`}>Event / occasion</label>
        <input
          id={`cat-logo-event-${logo.id}`}
          value={form.event}
          onChange={(e) => update({ event: e.target.value })}
        />
      </div>
      <div className="form-group">
        <label htmlFor={`cat-logo-notes-${logo.id}`}>Notes (optional)</label>
        <textarea
          id={`cat-logo-notes-${logo.id}`}
          rows={2}
          value={form.notes}
          onChange={(e) => update({ notes: e.target.value })}
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
        {loading ? "Submitting…" : "Submit logo metadata"}
      </button>
    </form>
  );
}
