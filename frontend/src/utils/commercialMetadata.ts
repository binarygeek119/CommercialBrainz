export const COMMERCIAL_METADATA_FIELDS = [
  { key: "sbid", label: "Commercial ID" },
  { key: "title", label: "Title" },
  { key: "commercial_type", label: "Type of commercial" },
  { key: "bumper_channel", label: "Channel" },
  { key: "campaign_name", label: "Campaign name" },
  { key: "description", label: "Description" },
  { key: "year", label: "Year aired" },
  { key: "decade", label: "Decade aired" },
  { key: "advertiser", label: "Brand" },
  { key: "store", label: "Store" },
  { key: "service", label: "Service" },
  { key: "event", label: "Event" },
  { key: "holiday", label: "Holiday" },
  { key: "store_id", label: "Store" },
  { key: "service_id", label: "Service" },
  { key: "event_id", label: "Event" },
  { key: "holiday_id", label: "Holiday" },
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
  if (key === "commercial_type" && typeof value === "string") {
    const labels: Record<string, string> = {
      general_ad: "General ad",
      psa: "PSA",
      service: "Service",
      store: "Store",
      bumper: "Bumper",
    };
    return labels[value] ?? value.replace(/_/g, " ");
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
  if (key === "store") return !!commercial.store;
  if (key === "service") return !!commercial.service;
  if (key === "event") return !!commercial.event;
  if (key === "holiday") return !!commercial.holiday;
  // Edit-diff keys only — display uses nested store/service/event/holiday objects
  if (
    key === "store_id" ||
    key === "service_id" ||
    key === "event_id" ||
    key === "holiday_id"
  ) {
    return false;
  }
  if (key === "agency") return !!commercial.agency;
  return value != null && value !== "";
}
