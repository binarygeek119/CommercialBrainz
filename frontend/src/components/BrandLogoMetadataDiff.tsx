import {
  LOGO_METADATA_FIELDS,
  formatLogoFieldValue,
  logoFieldLabel,
} from "../utils/logoMetadata";

interface Props {
  before?: Record<string, unknown>;
  after: Record<string, unknown>;
}

function collectKeys(before: Record<string, unknown>, after: Record<string, unknown>): string[] {
  const keys = new Set<string>();
  for (const { key } of LOGO_METADATA_FIELDS) {
    if (before[key] !== after[key]) keys.add(key);
  }
  return [...keys];
}

export default function BrandLogoMetadataDiff({ before = {}, after }: Props) {
  const changes = collectKeys(before, after);
  if (!changes.length) return null;

  return (
    <div className="card">
      <h3>Proposed logo metadata</h3>
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
                {logoFieldLabel(key)}
              </td>
              <td style={{ padding: "0.35rem 0.5rem", verticalAlign: "top" }}>
                {formatLogoFieldValue(key, before[key])}
              </td>
              <td style={{ padding: "0.35rem 0", verticalAlign: "top" }}>
                {formatLogoFieldValue(key, after[key])}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function hasLogoMetadataChanges(
  before: Record<string, unknown>,
  after: Record<string, unknown>
): boolean {
  return collectKeys(before, after).length > 0;
}
