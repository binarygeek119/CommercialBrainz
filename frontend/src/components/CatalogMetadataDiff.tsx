import {
  SOCIAL_FIELDS,
  catalogFieldLabel,
  formatCatalogFieldValue,
  type CatalogKindConfig,
} from "../catalog/kinds";

interface Props {
  kind: CatalogKindConfig;
  before?: Record<string, unknown>;
  after: Record<string, unknown>;
}

function collectKeys(
  kind: CatalogKindConfig,
  before: Record<string, unknown>,
  after: Record<string, unknown>
): string[] {
  const keys = new Set<string>();
  for (const key of [...kind.fields.map((f) => f.key), "social"]) {
    if (before[key] !== after[key]) keys.add(key);
  }
  const beforeSocial = (before.social as Record<string, string>) ?? {};
  const afterSocial = (after.social as Record<string, string>) ?? {};
  for (const { key } of SOCIAL_FIELDS) {
    if ((beforeSocial[key] ?? "") !== (afterSocial[key] ?? "")) keys.add("social");
  }
  return [...keys];
}

export default function CatalogMetadataDiff({ kind, before = {}, after }: Props) {
  const changes = collectKeys(kind, before, after);
  if (!changes.length) return null;

  return (
    <div className="card">
      <h3>Proposed {kind.label.toLowerCase()} metadata</h3>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.95rem" }}>
        <thead>
          <tr className="muted">
            <th style={{ textAlign: "left", padding: "0.35rem 0.5rem 0.35rem 0" }}>Field</th>
            <th style={{ textAlign: "left", padding: "0.35rem 0.5rem" }}>Before</th>
            <th style={{ textAlign: "left", padding: "0.35rem 0" }}>After</th>
          </tr>
        </thead>
        <tbody>
          {changes.map((key) => (
            <tr key={key}>
              <td style={{ padding: "0.35rem 0.5rem 0.35rem 0", verticalAlign: "top" }}>
                {catalogFieldLabel(kind, key)}
              </td>
              <td style={{ padding: "0.35rem 0.5rem", verticalAlign: "top" }}>
                {formatCatalogFieldValue(key, before[key])}
              </td>
              <td style={{ padding: "0.35rem 0", verticalAlign: "top" }}>
                {formatCatalogFieldValue(key, after[key])}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function hasCatalogMetadataChanges(
  kind: CatalogKindConfig,
  before: Record<string, unknown>,
  after: Record<string, unknown>
): boolean {
  return collectKeys(kind, before, after).length > 0;
}
