export const BRAND_METADATA_FIELDS = [
  { key: "description", label: "Description", type: "textarea" as const },
  { key: "tagline", label: "Tagline", type: "text" as const, inMetadata: true },
  { key: "website", label: "Website", type: "url" as const },
  { key: "country", label: "Country", type: "text" as const },
  { key: "founded_year", label: "Founded", type: "number" as const },
  { key: "industry", label: "Industry", type: "text" as const },
  { key: "headquarters", label: "Headquarters", type: "text" as const },
  { key: "parent_company", label: "Parent company", type: "text" as const },
  { key: "wikipedia_url", label: "Wikipedia", type: "url" as const },
  { key: "aliases", label: "Also known as", type: "aliases" as const, inMetadata: true },
  { key: "notes", label: "Notes", type: "textarea" as const, inMetadata: true },
] as const;

export const SOCIAL_FIELDS = [
  { key: "twitter", label: "Twitter / X" },
  { key: "instagram", label: "Instagram" },
  { key: "facebook", label: "Facebook" },
  { key: "linkedin", label: "LinkedIn" },
  { key: "youtube", label: "YouTube" },
] as const;

export type BrandMetadataFieldKey =
  | (typeof BRAND_METADATA_FIELDS)[number]["key"]
  | "social";

export function brandFieldLabel(key: string): string {
  const found = BRAND_METADATA_FIELDS.find((f) => f.key === key);
  if (found) return found.label;
  const social = SOCIAL_FIELDS.find((f) => f.key === key);
  if (social) return social.label;
  if (key === "social") return "Social links";
  return key.replace(/_/g, " ");
}

export function formatBrandFieldValue(key: string, value: unknown): string {
  if (value == null || value === "") return "—";
  if (key === "aliases" && Array.isArray(value)) {
    return value.length ? value.join(", ") : "—";
  }
  if (key === "social" && typeof value === "object" && value !== null) {
    const entries = Object.entries(value as Record<string, string>).filter(([, v]) => v?.trim());
    if (!entries.length) return "—";
    return entries.map(([k, v]) => `${brandFieldLabel(k)}: ${v}`).join(" · ");
  }
  if (key === "founded_year") return String(value);
  return String(value);
}

export function getBrandFieldValue(
  data: {
    description?: string | null;
    website?: string | null;
    country?: string | null;
    founded_year?: number | null;
    industry?: string | null;
    headquarters?: string | null;
    parent_company?: string | null;
    wikipedia_url?: string | null;
    metadata?: Record<string, unknown>;
  },
  key: string
): unknown {
  const field = BRAND_METADATA_FIELDS.find((f) => f.key === key);
  if (field && "inMetadata" in field && field.inMetadata) {
    return data.metadata?.[key];
  }
  return (data as Record<string, unknown>)[key];
}
