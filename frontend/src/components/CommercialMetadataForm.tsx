import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Edit } from "../api";
import CatalogPicker, { type CatalogSelection } from "./CatalogPicker";
import { CATALOG_KIND_LIST } from "../catalog/kinds";
import {
  COMMERCIAL_DECADES,
  COMMERCIAL_TYPES,
  isBumperType,
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
  bumper_channel: string;
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
    bumper_channel: commercial.bumper_channel ?? "",
    campaign_name: commercial.campaign_name ?? "",
    description: commercial.description ?? "",
    year: commercial.year != null ? String(commercial.year) : "",
    decade: commercial.decade != null ? String(commercial.decade) : "",
    products: (commercial.products ?? []).join(", "),
  };
}

function catalogSelectionFromCommercial(
  commercial: CommercialDetail
): Record<string, CatalogSelection> {
  const out: Record<string, CatalogSelection> = {};
  for (const kind of CATALOG_KIND_LIST) {
    const ref = (commercial as unknown as Record<string, unknown>)[kind.key] as
      | { sbid: string; name: string }
      | null
      | undefined;
    out[kind.key] = ref ? { id: ref.sbid, name: ref.name } : {};
  }
  return out;
}

function toPayload(
  form: FormState,
  catalogs: Record<string, CatalogSelection>
): CommercialMetadataUpdate & {
  store_id?: string | null;
  service_id?: string | null;
  event_id?: string | null;
  holiday_id?: string | null;
} {
  const year = form.year.trim() ? Number(form.year) : null;
  const decade = form.decade.trim() ? Number(form.decade) : null;
  const products = form.products
    .split(/[,;\n]/)
    .map((s) => s.trim())
    .filter(Boolean);
  const commercial_type = (form.commercial_type.trim() || null) as CommercialTypeValue | null;
  const bumper_channel = isBumperType(commercial_type)
    ? form.bumper_channel.trim() || null
    : null;

  const catalogIds = Object.fromEntries(
    CATALOG_KIND_LIST.map((kind) => {
      const sel = catalogs[kind.key] ?? {};
      return [kind.idKey, sel.id ?? null];
    })
  );

  return {
    title: form.title.trim() || null,
    commercial_type,
    bumper_channel,
    campaign_name: form.campaign_name.trim() || null,
    description: form.description.trim() || null,
    year: year != null && !Number.isNaN(year) ? year : null,
    decade: decade != null && !Number.isNaN(decade) ? decade : null,
    products,
    ...catalogIds,
  };
}

export default function CommercialMetadataForm({ commercial, onSubmitted }: Props) {
  const initial = useMemo(() => toFormState(commercial), [commercial]);
  const [form, setForm] = useState<FormState>(initial);
  const [catalogs, setCatalogs] = useState(() => catalogSelectionFromCommercial(commercial));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Edit | null>(null);

  const update = (patch: Partial<FormState>) => setForm((prev) => ({ ...prev, ...patch }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (isBumperType(form.commercial_type) && !form.bumper_channel.trim()) {
      setError("Channel is required for bumpers.");
      return;
    }
    setLoading(true);
    try {
      const edit = await api.submitCommercialMetadata(commercial.sbid, toPayload(form, catalogs));
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
        Propose changes to this commercial&apos;s title, type, campaign, catalog links, air date,
        description, or products. Submissions go to the edit queue — 3 votes or 1 mod approval.
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
            onChange={(e) =>
              update({
                commercial_type: e.target.value,
                ...(e.target.value === "bumper" ? {} : { bumper_channel: "" }),
              })
            }
          >
            <option value="">Unknown / not set</option>
            {COMMERCIAL_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        {isBumperType(form.commercial_type) && (
          <div className="form-group">
            <label htmlFor="commercial-bumper-channel">Channel *</label>
            <input
              id="commercial-bumper-channel"
              required
              value={form.bumper_channel}
              onChange={(e) => update({ bumper_channel: e.target.value })}
              placeholder="e.g. Cartoon Network, Nickelodeon"
            />
            <p className="muted" style={{ fontSize: "0.85rem", marginTop: "0.25rem" }}>
              Which channel this bumper is for.
            </p>
          </div>
        )}
        {CATALOG_KIND_LIST.map((kind) => (
          <div className="form-group" key={kind.key}>
            <label>{kind.label}</label>
            <CatalogPicker
              kind={kind}
              value={catalogs[kind.key] ?? {}}
              allowCreate={false}
              onChange={(next) =>
                setCatalogs((prev) => ({ ...prev, [kind.key]: next }))
              }
            />
            <p className="muted" style={{ fontSize: "0.85rem", marginTop: "0.25rem" }}>
              Link an existing approved {kind.label.toLowerCase()}, or clear to unlink.
            </p>
          </div>
        ))}
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
