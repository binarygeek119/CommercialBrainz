import { BRAND_METADATA_FIELDS, SOCIAL_FIELDS, brandFieldLabel, formatBrandFieldValue } from "../utils/brandMetadata";

interface Props {
  before?: Record<string, unknown>;
  after: Record<string, unknown>;
}

function collectKeys(before: Record<string, unknown>, after: Record<string, unknown>): string[] {
  const keys = new Set<string>();
  for (const key of [...BRAND_METADATA_FIELDS.map((f) => f.key), "social"]) {
    if (before[key] !== after[key]) keys.add(key);
  }
  const beforeSocial = (before.social as Record<string, string>) ?? {};
  const afterSocial = (after.social as Record<string, string>) ?? {};
  for (const { key } of SOCIAL_FIELDS) {
    if ((beforeSocial[key] ?? "") !== (afterSocial[key] ?? "")) keys.add("social");
  }
  return [...keys];
}

export default function BrandMetadataDiff({ before = {}, after }: Props) {
  const changes = collectKeys(before, after);
  if (!changes.length) return null;

  return (
    <div className="card">
      <h3>Proposed brand metadata</h3>
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
                {brandFieldLabel(key)}
              </td>
              <td style={{ padding: "0.35rem 0.5rem", verticalAlign: "top" }}>
                {formatBrandFieldValue(key, before[key])}
              </td>
              <td style={{ padding: "0.35rem 0", verticalAlign: "top" }}>
                {formatBrandFieldValue(key, after[key])}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function hasMetadataChanges(before: Record<string, unknown>, after: Record<string, unknown>): boolean {
  return collectKeys(before, after).length > 0;
}

export { hasMetadataChanges };
