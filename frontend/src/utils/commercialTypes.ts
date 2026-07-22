import { COMMERCIAL_DECADES } from "./commercialPeriod";

import type { Video } from "../api";

export type CommercialTypeValue = "general_ad" | "psa" | "service" | "store" | "bumper";

export const COMMERCIAL_TYPES: { value: CommercialTypeValue; label: string }[] = [
  { value: "general_ad", label: "General ad" },
  { value: "psa", label: "PSA" },
  { value: "service", label: "Service" },
  { value: "store", label: "Store" },
  { value: "bumper", label: "Bumper" },
];

export function commercialTypeLabel(value: string | null | undefined): string {
  if (!value) return "—";
  const found = COMMERCIAL_TYPES.find((t) => t.value === value);
  return found?.label ?? value.replace(/_/g, " ");
}

export function isBumperType(value: string | null | undefined): boolean {
  return value === "bumper";
}

export interface CommercialDetail {
  sbid: string;
  title: string;
  description?: string | null;
  year?: number | null;
  decade?: number | null;
  commercial_type?: CommercialTypeValue | null;
  bumper_channel?: string | null;
  campaign_name?: string | null;
  advertiser_id?: string | null;
  store_id?: string | null;
  service_id?: string | null;
  event_id?: string | null;
  holiday_id?: string | null;
  agency_id?: string | null;
  external_ids?: Record<string, unknown>;
  created_at?: string;
  products?: string[];
  advertiser?: { sbid: string; name: string } | null;
  store?: { sbid: string; name: string } | null;
  service?: { sbid: string; name: string } | null;
  event?: { sbid: string; name: string } | null;
  holiday?: { sbid: string; name: string } | null;
  agency?: { sbid: string; name: string; slug?: string } | null;
  videos?: Video[];
}

export interface CommercialMetadataUpdate {
  title?: string | null;
  year?: number | null;
  decade?: number | null;
  commercial_type?: CommercialTypeValue | null;
  bumper_channel?: string | null;
  campaign_name?: string | null;
  description?: string | null;
  products?: string[];
  store_id?: string | null;
  service_id?: string | null;
  event_id?: string | null;
  holiday_id?: string | null;
}

export { COMMERCIAL_DECADES };
