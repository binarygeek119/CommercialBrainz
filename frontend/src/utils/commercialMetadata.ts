export const COMMERCIAL_METADATA_FIELDS = [
  { key: "sbid", label: "Commercial ID" },
  { key: "title", label: "Title" },
  { key: "campaign_name", label: "Campaign name" },
  { key: "description", label: "Description" },
  { key: "year", label: "Year aired" },
  { key: "decade", label: "Decade aired" },
  { key: "advertiser", label: "Brand" },
  { key: "agency", label: "Agency" },
  { key: "products", label: "Products" },
  { key: "external_ids", label: "External IDs" },
  { key: "created_at", label: "Added to archive" },
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
  if (key === "created_at" && typeof value === "string") {
    return new Date(value).toLocaleString();
  }
  if (key === "external_ids" && typeof value === "object" && value !== null) {
    const entries = Object.entries(value as Record<string, unknown>).filter(
      ([, v]) => v != null && v !== ""
    );
    return entries.length ? entries.map(([k, v]) => `${k}: ${v}`).join("; ") : "—";
  }
  return String(value);
}

export function commercialHasFieldValue(
  commercial: Record<string, unknown>,
  key: string
): boolean {
  const value = commercial[key];
  if (key === "products") return Array.isArray(value) && value.length > 0;
  if (key === "external_ids") {
    return (
      typeof value === "object" &&
      value !== null &&
      Object.values(value as Record<string, unknown>).some((v) => v != null && v !== "")
    );
  }
  if (key === "advertiser") return !!commercial.advertiser;
  if (key === "agency") return !!commercial.agency;
  return value != null && value !== "";
}
