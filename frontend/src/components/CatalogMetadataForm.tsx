import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type CatalogEntity, type Edit } from "../api";
import {
  SOCIAL_FIELDS,
  type CatalogFieldDef,
  type CatalogKindConfig,
} from "../catalog/kinds";

interface Props {
  kind: CatalogKindConfig;
  entity: CatalogEntity;
}

type FormState = {
  [key: string]: string | Record<string, string>;
  social: Record<string, string>;
};

function fieldValue(entity: CatalogEntity, field: CatalogFieldDef): string {
  if (field.inMetadata) {
    const meta = entity.metadata ?? {};
    if (field.key === "aliases") {
      return ((meta.aliases as string[]) ?? []).join(", ");
    }
    return String((meta as Record<string, unknown>)[field.key] ?? "");
  }
  const raw = (entity as unknown as Record<string, unknown>)[field.key];
  return raw != null ? String(raw) : "";
}

function toFormState(kind: CatalogKindConfig, entity: CatalogEntity): FormState {
  const social = entity.metadata?.social ?? {};
  const state: FormState = {
    social: Object.fromEntries(SOCIAL_FIELDS.map(({ key }) => [key, social[key] ?? ""])),
  };
  for (const field of kind.fields) {
    state[field.key] = fieldValue(entity, field);
  }
  return state;
}

function toPayload(kind: CatalogKindConfig, form: FormState): Record<string, unknown> {
  const aliases = String(form.aliases ?? "")
    .split(/[,;\n]/)
    .map((s) => s.trim())
    .filter(Boolean);
  const social = Object.fromEntries(
    Object.entries(form.social).filter(([, v]) => v.trim())
  );
  const payload: Record<string, unknown> = {
    aliases,
    tagline: String(form.tagline ?? "").trim() || null,
    notes: String(form.notes ?? "").trim() || null,
    social,
  };

  for (const field of kind.fields) {
    if (field.inMetadata) continue;
    const raw = String(form[field.key] ?? "").trim();
    if (field.type === "number") {
      const n = raw ? Number(raw) : null;
      payload[field.key] = n != null && !Number.isNaN(n) ? n : null;
    } else if (field.type === "date") {
      payload[field.key] = raw || null;
    } else {
      payload[field.key] = raw || null;
    }
  }
  return payload;
}

export default function CatalogMetadataForm({ kind, entity }: Props) {
  const initial = useMemo(() => toFormState(kind, entity), [kind, entity]);
  const [form, setForm] = useState<FormState>(initial);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Edit | null>(null);

  const update = (patch: Partial<FormState>) =>
    setForm((prev) => ({ ...prev, ...patch }) as FormState);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const edit = await api.submitCatalogMetadata(kind.key, entity.sbid, toPayload(kind, form));
      setResult(edit);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card" style={{ marginTop: "1rem" }}>
      <h3>{kind.label} metadata</h3>
      <p className="muted" style={{ marginBottom: "0.75rem" }}>
        Add or update facts about {entity.name}. Changes go to the edit queue — 10 votes or 1 mod
        approval.
      </p>
      <form onSubmit={handleSubmit}>
        {kind.fields.map((field) => (
          <div className="form-group" key={field.key}>
            <label htmlFor={`${kind.key}-${field.key}`}>{field.label}</label>
            {field.type === "textarea" ? (
              <textarea
                id={`${kind.key}-${field.key}`}
                rows={field.key === "description" ? 4 : 3}
                value={String(form[field.key] ?? "")}
                onChange={(e) => update({ [field.key]: e.target.value })}
              />
            ) : (
              <input
                id={`${kind.key}-${field.key}`}
                type={
                  field.type === "number"
                    ? "number"
                    : field.type === "url"
                      ? "url"
                      : field.type === "date"
                        ? "date"
                        : "text"
                }
                value={String(form[field.key] ?? "")}
                onChange={(e) => update({ [field.key]: e.target.value })}
                placeholder={
                  field.type === "url"
                    ? "https://…"
                    : field.key === "aliases"
                      ? "Alias one, Alias two"
                      : undefined
                }
              />
            )}
            {field.helper && (
              <p className="muted" style={{ fontSize: "0.85rem", marginTop: "0.25rem" }}>
                {field.helper}
              </p>
            )}
            {field.key === "aliases" && !field.helper && (
              <p className="muted" style={{ fontSize: "0.85rem", marginTop: "0.25rem" }}>
                Separate aliases with commas.
              </p>
            )}
          </div>
        ))}

        <fieldset style={{ border: "none", padding: 0, margin: "0 0 1rem" }}>
          <legend style={{ fontWeight: 600, marginBottom: "0.5rem" }}>Social links</legend>
          {SOCIAL_FIELDS.map(({ key, label }) => (
            <div className="form-group" key={key}>
              <label htmlFor={`${kind.key}-social-${key}`}>{label}</label>
              <input
                id={`${kind.key}-social-${key}`}
                type="url"
                value={form.social[key] ?? ""}
                onChange={(e) =>
                  update({
                    social: { ...form.social, [key]: e.target.value },
                  } as Partial<FormState>)
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
