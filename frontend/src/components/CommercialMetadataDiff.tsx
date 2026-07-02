import {
  COMMERCIAL_METADATA_FIELDS,
  commercialFieldLabel,
  formatCommercialFieldValue,
} from "../utils/commercialMetadata";

interface Props {
  before?: Record<string, unknown>;
  after: Record<string, unknown>;
}

function collectKeys(before: Record<string, unknown>, after: Record<string, unknown>): string[] {
  const keys = new Set<string>();
  for (const { key } of COMMERCIAL_METADATA_FIELDS) {
    if (before[key] !== after[key]) keys.add(key);
  }
  return [...keys];
}

export default function CommercialMetadataDiff({ before = {}, after }: Props) {
  const changes = collectKeys(before, after);
  if (!changes.length) return null;

  return (
    <div className="card">
      <h3>Proposed commercial metadata</h3>
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
                {commercialFieldLabel(key)}
              </td>
              <td style={{ padding: "0.35rem 0.5rem", verticalAlign: "top" }}>
                {formatCommercialFieldValue(key, before[key])}
              </td>
              <td style={{ padding: "0.35rem 0", verticalAlign: "top" }}>
                {formatCommercialFieldValue(key, after[key])}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function hasCommercialMetadataChanges(
  before: Record<string, unknown>,
  after: Record<string, unknown>
): boolean {
  return collectKeys(before, after).length > 0;
}
