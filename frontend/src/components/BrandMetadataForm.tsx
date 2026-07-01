import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Advertiser, type AdvertiserMetadataUpdate, type Edit } from "../api";
import { SOCIAL_FIELDS } from "../utils/brandMetadata";

interface Props {
  advertiser: Advertiser;
}

type FormState = {
  description: string;
  website: string;
  country: string;
  founded_year: string;
  industry: string;
  headquarters: string;
  parent_company: string;
  wikipedia_url: string;
  tagline: string;
  aliases: string;
  notes: string;
  social: Record<string, string>;
};

function toFormState(advertiser: Advertiser): FormState {
  const social = advertiser.metadata?.social ?? {};
  return {
    description: advertiser.description ?? "",
    website: advertiser.website ?? "",
    country: advertiser.country ?? "",
    founded_year: advertiser.founded_year != null ? String(advertiser.founded_year) : "",
    industry: advertiser.industry ?? "",
    headquarters: advertiser.headquarters ?? "",
    parent_company: advertiser.parent_company ?? "",
    wikipedia_url: advertiser.wikipedia_url ?? "",
    tagline: (advertiser.metadata?.tagline as string) ?? "",
    aliases: ((advertiser.metadata?.aliases as string[]) ?? []).join(", "),
    notes: (advertiser.metadata?.notes as string) ?? "",
    social: Object.fromEntries(SOCIAL_FIELDS.map(({ key }) => [key, social[key] ?? ""])),
  };
}

function toPayload(form: FormState): AdvertiserMetadataUpdate {
  const aliases = form.aliases
    .split(/[,;\n]/)
    .map((s) => s.trim())
    .filter(Boolean);
  const social = Object.fromEntries(
    Object.entries(form.social).filter(([, v]) => v.trim())
  );
  const founded = form.founded_year.trim() ? Number(form.founded_year) : null;

  return {
    description: form.description.trim() || null,
    website: form.website.trim() || null,
    country: form.country.trim() || null,
    founded_year: founded != null && !Number.isNaN(founded) ? founded : null,
    industry: form.industry.trim() || null,
    headquarters: form.headquarters.trim() || null,
    parent_company: form.parent_company.trim() || null,
    wikipedia_url: form.wikipedia_url.trim() || null,
    tagline: form.tagline.trim() || null,
    aliases,
    notes: form.notes.trim() || null,
    social,
  };
}

export default function BrandMetadataForm({ advertiser }: Props) {
  const initial = useMemo(() => toFormState(advertiser), [advertiser]);
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
      const edit = await api.submitAdvertiserMetadata(advertiser.sbid, toPayload(form));
      setResult(edit);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card" style={{ marginTop: "1rem" }}>
      <h3>Brand metadata</h3>
      <p className="muted" style={{ marginBottom: "0.75rem" }}>
        Add or update facts about {advertiser.name}. Changes go to the edit queue — 10 votes or 1
        mod approval.
      </p>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="brand-description">Description</label>
          <textarea
            id="brand-description"
            rows={4}
            value={form.description}
            onChange={(e) => update({ description: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label htmlFor="brand-tagline">Tagline</label>
          <input
            id="brand-tagline"
            value={form.tagline}
            onChange={(e) => update({ tagline: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label htmlFor="brand-website">Website</label>
          <input
            id="brand-website"
            type="url"
            value={form.website}
            onChange={(e) => update({ website: e.target.value })}
            placeholder="https://…"
          />
        </div>
        <div className="form-group">
          <label htmlFor="brand-country">Country</label>
          <input
            id="brand-country"
            value={form.country}
            onChange={(e) => update({ country: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label htmlFor="brand-founded">Founded</label>
          <input
            id="brand-founded"
            type="number"
            min={1800}
            max={2100}
            value={form.founded_year}
            onChange={(e) => update({ founded_year: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label htmlFor="brand-industry">Industry</label>
          <input
            id="brand-industry"
            value={form.industry}
            onChange={(e) => update({ industry: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label htmlFor="brand-headquarters">Headquarters</label>
          <input
            id="brand-headquarters"
            value={form.headquarters}
            onChange={(e) => update({ headquarters: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label htmlFor="brand-parent">Parent company</label>
          <input
            id="brand-parent"
            value={form.parent_company}
            onChange={(e) => update({ parent_company: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label htmlFor="brand-wikipedia">Wikipedia</label>
          <input
            id="brand-wikipedia"
            type="url"
            value={form.wikipedia_url}
            onChange={(e) => update({ wikipedia_url: e.target.value })}
            placeholder="https://en.wikipedia.org/wiki/…"
          />
        </div>
        <div className="form-group">
          <label htmlFor="brand-aliases">Also known as</label>
          <input
            id="brand-aliases"
            value={form.aliases}
            onChange={(e) => update({ aliases: e.target.value })}
            placeholder="Acme Inc., ACME Corp."
          />
          <p className="muted" style={{ fontSize: "0.85rem", marginTop: "0.25rem" }}>
            Separate aliases with commas.
          </p>
        </div>
        <div className="form-group">
          <label htmlFor="brand-notes">Notes</label>
          <textarea
            id="brand-notes"
            rows={3}
            value={form.notes}
            onChange={(e) => update({ notes: e.target.value })}
          />
        </div>

        <fieldset style={{ border: "none", padding: 0, margin: "0 0 1rem" }}>
          <legend style={{ fontWeight: 600, marginBottom: "0.5rem" }}>Social links</legend>
          {SOCIAL_FIELDS.map(({ key, label }) => (
            <div className="form-group" key={key}>
              <label htmlFor={`brand-social-${key}`}>{label}</label>
              <input
                id={`brand-social-${key}`}
                type="url"
                value={form.social[key] ?? ""}
                onChange={(e) =>
                  update({ social: { ...form.social, [key]: e.target.value } })
                }
                placeholder="https://…"
              />
            </div>
          ))}
        </fieldset>

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
