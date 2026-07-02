import { COMMERCIAL_DECADES } from "./commercialPeriod";

export interface CommercialDetail {
  sbid: string;
  title: string;
  description?: string | null;
  year?: number | null;
  decade?: number | null;
  campaign_name?: string | null;
  advertiser_id?: string | null;
  agency_id?: string | null;
  products?: string[];
  advertiser?: { sbid: string; name: string } | null;
  agency?: { sbid: string; name: string } | null;
  videos?: { sbid: string; youtube_id: string | null; slogan: string | null }[];
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
