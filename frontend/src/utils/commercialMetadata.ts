export const COMMERCIAL_METADATA_FIELDS = [
  { key: "title", label: "Title" },
  { key: "campaign_name", label: "Campaign name" },
  { key: "description", label: "Description" },
  { key: "year", label: "Year aired" },
  { key: "decade", label: "Decade aired" },
  { key: "products", label: "Products" },
] as const;

export function commercialFieldLabel(key: string): string {
  const found = COMMERCIAL_METADATA_FIELDS.find((f) => f.key === key);
  return found?.label ?? key.replace(/_/g, " ");
}

export function formatCommercialFieldValue(key: string, value: unknown): string {
  if (value == null || value === "") return "—";
  if (key === "products" && Array.isArray(value)) {
    return value.length ? value.join(", ") : "—";
  }
  if (key === "decade" && typeof value === "number") {
    return `${value}s`;
  }
  return String(value);
}
