import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Edit } from "../api";
import {
  COMMERCIAL_DECADES,
  COMMERCIAL_TYPES,
  type CommercialDetail,
  type CommercialMetadataUpdate,
  type CommercialTypeValue,
} from "../utils/commercialTypes";

interface Props {
  commercial: CommercialDetail;
  onSubmitted?: () => void;
}

type FormState = {
  title: string;
  commercial_type: string;
  campaign_name: string;
  description: string;
  year: string;
  decade: string;
  products: string;
};

function toFormState(commercial: CommercialDetail): FormState {
  return {
    title: commercial.title ?? "",
    commercial_type: commercial.commercial_type ?? "",
    campaign_name: commercial.campaign_name ?? "",
    description: commercial.description ?? "",
    year: commercial.year != null ? String(commercial.year) : "",
    decade: commercial.decade != null ? String(commercial.decade) : "",
    products: (commercial.products ?? []).join(", "),
  };
}

function toPayload(form: FormState): CommercialMetadataUpdate {
  const year = form.year.trim() ? Number(form.year) : null;
  const decade = form.decade.trim() ? Number(form.decade) : null;
  const products = form.products
    .split(/[,;\n]/)
    .map((s) => s.trim())
    .filter(Boolean);
  const commercial_type = (form.commercial_type.trim() || null) as CommercialTypeValue | null;

  return {
    title: form.title.trim() || null,
    commercial_type,
    campaign_name: form.campaign_name.trim() || null,
    description: form.description.trim() || null,
    year: year != null && !Number.isNaN(year) ? year : null,
    decade: decade != null && !Number.isNaN(decade) ? decade : null,
    products,
  };
}

export default function CommercialMetadataForm({ commercial, onSubmitted }: Props) {
  const initial = useMemo(() => toFormState(commercial), [commercial]);
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
      const edit = await api.submitCommercialMetadata(commercial.sbid, toPayload(form));
      setResult(edit);
      onSubmitted?.();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card" style={{ marginTop: "1rem" }}>
      <h3>Commercial metadata</h3>
      <p className="muted" style={{ marginBottom: "0.75rem" }}>
        Propose changes to this commercial&apos;s title, type, campaign, air date, description, or
        products. Submissions go to the edit queue — 3 votes or 1 mod approval.
      </p>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="commercial-title">Title</label>
          <input
            id="commercial-title"
            required
            value={form.title}
            onChange={(e) => update({ title: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label htmlFor="commercial-type">Type of commercial</label>
          <select
            id="commercial-type"
            value={form.commercial_type}
            onChange={(e) => update({ commercial_type: e.target.value })}
          >
            <option value="">Unknown / not set</option>
            {COMMERCIAL_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label htmlFor="commercial-campaign">Campaign name</label>
          <input
            id="commercial-campaign"
            value={form.campaign_name}
            onChange={(e) => update({ campaign_name: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label htmlFor="commercial-description">Description</label>
          <textarea
            id="commercial-description"
            rows={4}
            value={form.description}
            onChange={(e) => update({ description: e.target.value })}
          />
        </div>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <div className="form-group" style={{ flex: "1 1 140px" }}>
            <label htmlFor="commercial-year">Year aired</label>
            <input
              id="commercial-year"
              type="number"
              min={1900}
              max={2100}
              value={form.year}
              onChange={(e) => update({ year: e.target.value })}
              placeholder="1997"
            />
          </div>
          <div className="form-group" style={{ flex: "1 1 160px" }}>
            <label htmlFor="commercial-decade">Decade aired</label>
            <select
              id="commercial-decade"
              value={form.decade}
              onChange={(e) => update({ decade: e.target.value })}
            >
              <option value="">Unknown</option>
              {COMMERCIAL_DECADES.map((d) => (
                <option key={d} value={String(d)}>
                  {d}s
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="form-group">
          <label htmlFor="commercial-products">Products featured</label>
          <input
            id="commercial-products"
            value={form.products}
            onChange={(e) => update({ products: e.target.value })}
            placeholder="Product A, Product B"
          />
          <p className="muted" style={{ fontSize: "0.85rem", marginTop: "0.25rem" }}>
            Separate products with commas.
          </p>
        </div>

        {error && <p className="error">{error}</p>}
        {result && (
          <p style={{ marginBottom: "0.75rem" }}>
            Submitted for review —{" "}
            <Link to={`/edits/${result.id}`}>view edit #{result.id.slice(0, 8)}</Link>
          </p>
        )}
        <button type="submit" className="btn btn-secondary" disabled={loading}>
          {loading ? "Submitting…" : "Submit metadata for review"}
        </button>
      </form>
    </div>
  );
}
