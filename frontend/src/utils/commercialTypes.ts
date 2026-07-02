import { COMMERCIAL_DECADES } from "./commercialPeriod";

import type { Video } from "../api";

export interface CommercialDetail {
  sbid: string;
  title: string;
  description?: string | null;
  year?: number | null;
  decade?: number | null;
  campaign_name?: string | null;
  advertiser_id?: string | null;
  agency_id?: string | null;
  external_ids?: Record<string, unknown>;
  created_at?: string;
  products?: string[];
  advertiser?: { sbid: string; name: string } | null;
  agency?: { sbid: string; name: string; slug?: string } | null;
  videos?: Video[];
}

export interface CommercialMetadataUpdate {
  title?: string | null;
  year?: number | null;
  decade?: number | null;
  campaign_name?: string | null;
  description?: string | null;
  products?: string[];
}

export { COMMERCIAL_DECADES };
