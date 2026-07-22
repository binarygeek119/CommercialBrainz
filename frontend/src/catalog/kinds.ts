import { SOCIAL_FIELDS } from "../utils/brandMetadata";

export type CatalogKindKey = "store" | "service" | "event" | "holiday";

export type CatalogFieldType =
  | "text"
  | "textarea"
  | "url"
  | "number"
  | "date"
  | "aliases";

export interface CatalogFieldDef {
  key: string;
  label: string;
  type: CatalogFieldType;
  inMetadata?: boolean;
  helper?: string;
  /** Shown in list card subtitle when present */
  listHint?: boolean;
}

export interface CatalogKindConfig {
  key: CatalogKindKey;
  label: string;
  plural: string;
  listPath: string;
  detailPath: (sbid: string) => string;
  apiPath: string;
  searchType: CatalogKindKey;
  idKey: `${CatalogKindKey}_id`;
  nameKey: `${CatalogKindKey}_name`;
  createEdit: string;
  editEdit: string;
  addLogoEdit: string;
  editLogoEdit: string;
  fields: CatalogFieldDef[];
}

const SHARED_BASE: CatalogFieldDef[] = [
  { key: "description", label: "Description", type: "textarea" },
  { key: "tagline", label: "Tagline", type: "text", inMetadata: true },
  { key: "website", label: "Website", type: "url" },
  { key: "country", label: "Country", type: "text", listHint: true },
  { key: "wikipedia_url", label: "Wikipedia", type: "url" },
  { key: "aliases", label: "Also known as", type: "aliases", inMetadata: true },
  { key: "notes", label: "Notes", type: "textarea", inMetadata: true },
];

function withOrgFields(typeKey: string, typeLabel: string): CatalogFieldDef[] {
  return [
    SHARED_BASE[0],
    SHARED_BASE[1],
    SHARED_BASE[2],
    SHARED_BASE[3],
    { key: "founded_year", label: "Founded", type: "number" },
    { key: typeKey, label: typeLabel, type: "text", listHint: true },
    { key: "headquarters", label: "Headquarters", type: "text" },
    { key: "parent_company", label: "Parent company", type: "text" },
    SHARED_BASE[4],
    SHARED_BASE[5],
    SHARED_BASE[6],
  ];
}

export const CATALOG_KINDS: Record<CatalogKindKey, CatalogKindConfig> = {
  store: {
    key: "store",
    label: "Store",
    plural: "Stores",
    listPath: "/stores",
    detailPath: (sbid) => `/store/${sbid}`,
    apiPath: "/stores",
    searchType: "store",
    idKey: "store_id",
    nameKey: "store_name",
    createEdit: "create_store",
    editEdit: "edit_store",
    addLogoEdit: "add_store_logo",
    editLogoEdit: "edit_store_logo",
    fields: withOrgFields("store_type", "Store type"),
  },
  service: {
    key: "service",
    label: "Service",
    plural: "Services",
    listPath: "/services",
    detailPath: (sbid) => `/service/${sbid}`,
    apiPath: "/services",
    searchType: "service",
    idKey: "service_id",
    nameKey: "service_name",
    createEdit: "create_service",
    editEdit: "edit_service",
    addLogoEdit: "add_service_logo",
    editLogoEdit: "edit_service_logo",
    fields: withOrgFields("service_type", "Service type"),
  },
  event: {
    key: "event",
    label: "Event",
    plural: "Events",
    listPath: "/events",
    detailPath: (sbid) => `/event/${sbid}`,
    apiPath: "/events",
    searchType: "event",
    idKey: "event_id",
    nameKey: "event_name",
    createEdit: "create_event",
    editEdit: "edit_event",
    addLogoEdit: "add_event_logo",
    editLogoEdit: "edit_event_logo",
    fields: [
      SHARED_BASE[0],
      SHARED_BASE[1],
      SHARED_BASE[2],
      SHARED_BASE[3],
      { key: "location", label: "Location", type: "text", listHint: true },
      { key: "start_year", label: "Start year", type: "number" },
      { key: "end_year", label: "End year", type: "number" },
      { key: "start_date", label: "Start date", type: "date" },
      { key: "end_date", label: "End date", type: "date" },
      SHARED_BASE[4],
      SHARED_BASE[5],
      SHARED_BASE[6],
    ],
  },
  holiday: {
    key: "holiday",
    label: "Holiday",
    plural: "Holidays",
    listPath: "/holidays",
    detailPath: (sbid) => `/holiday/${sbid}`,
    apiPath: "/holidays",
    searchType: "holiday",
    idKey: "holiday_id",
    nameKey: "holiday_name",
    createEdit: "create_holiday",
    editEdit: "edit_holiday",
    addLogoEdit: "add_holiday_logo",
    editLogoEdit: "edit_holiday_logo",
    fields: [
      SHARED_BASE[0],
      SHARED_BASE[1],
      SHARED_BASE[2],
      SHARED_BASE[3],
      {
        key: "date_text",
        label: "Date",
        type: "text",
        listHint: true,
        helper: "Examples: 10/31/1999, 10/31, Halloween - 1999, Halloween",
      },
      { key: "year", label: "Year (parsed)", type: "number" },
      { key: "month", label: "Month (parsed)", type: "number" },
      { key: "day", label: "Day (parsed)", type: "number" },
      SHARED_BASE[4],
      SHARED_BASE[5],
      SHARED_BASE[6],
    ],
  },
};

export const CATALOG_KIND_LIST = Object.values(CATALOG_KINDS);

export const CATALOG_EDIT_TYPES: string[] = CATALOG_KIND_LIST.flatMap((k) => [
  k.createEdit,
  k.editEdit,
  k.addLogoEdit,
  k.editLogoEdit,
]);

export function catalogKindFromEditType(editType: string): CatalogKindConfig | null {
  return (
    CATALOG_KIND_LIST.find(
      (k) =>
        editType === k.createEdit ||
        editType === k.editEdit ||
        editType === k.addLogoEdit ||
        editType === k.editLogoEdit
    ) ?? null
  );
}

export function isCatalogLogoEdit(editType: string): boolean {
  return CATALOG_KIND_LIST.some(
    (k) => editType === k.addLogoEdit || editType === k.editLogoEdit
  );
}

export function catalogFieldLabel(kind: CatalogKindConfig, key: string): string {
  const found = kind.fields.find((f) => f.key === key);
  if (found) return found.label;
  const social = SOCIAL_FIELDS.find((f) => f.key === key);
  if (social) return social.label;
  if (key === "social") return "Social links";
  return key.replace(/_/g, " ");
}

export function formatCatalogFieldValue(key: string, value: unknown): string {
  if (value == null || value === "") return "—";
  if (key === "aliases" && Array.isArray(value)) {
    return value.length ? value.join(", ") : "—";
  }
  if (key === "social" && typeof value === "object" && value !== null) {
    const entries = Object.entries(value as Record<string, string>).filter(([, v]) => v?.trim());
    if (!entries.length) return "—";
    return entries
      .map(([k, v]) => `${SOCIAL_FIELDS.find((f) => f.key === k)?.label ?? k}: ${v}`)
      .join(" · ");
  }
  return String(value);
}

export function getCatalogFieldValue(
  data: Record<string, unknown> & { metadata?: Record<string, unknown> },
  field: CatalogFieldDef
): unknown {
  if (field.inMetadata) return data.metadata?.[field.key];
  return data[field.key];
}

export { SOCIAL_FIELDS };
