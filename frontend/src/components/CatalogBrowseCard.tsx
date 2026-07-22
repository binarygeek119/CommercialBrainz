import { Link } from "react-router-dom";
import type { BrowseCatalogEntity } from "../api";
import BrandLogoImage from "./BrandLogoImage";

const DETAIL_PATH: Record<string, (sbid: string) => string> = {
  brand: (sbid) => `/advertiser/${sbid}`,
  store: (sbid) => `/store/${sbid}`,
  service: (sbid) => `/service/${sbid}`,
  event: (sbid) => `/event/${sbid}`,
  holiday: (sbid) => `/holiday/${sbid}`,
};

function subtitle(entity: BrowseCatalogEntity): string {
  const parts: string[] = [];
  if (entity.catalog_key === "store" && entity.store_type) parts.push(entity.store_type);
  if (entity.catalog_key === "service" && entity.service_type) parts.push(entity.service_type);
  if (entity.catalog_key === "brand" && entity.industry) parts.push(entity.industry);
  if (entity.catalog_key === "event" && entity.location) parts.push(entity.location);
  if (entity.catalog_key === "holiday" && entity.date_text) parts.push(entity.date_text);
  if (entity.country) parts.push(entity.country);
  return parts.join(" · ");
}

export default function CatalogBrowseCard({ entity }: { entity: BrowseCatalogEntity }) {
  const key = entity.catalog_key || "brand";
  const to = (DETAIL_PATH[key] || DETAIL_PATH.brand)(entity.sbid);
  const hint = subtitle(entity);

  return (
    <Link to={to} className="catalog-browse-card">
      <div className="catalog-browse-card-logo">
        {entity.logo_url ? (
          <BrandLogoImage src={entity.logo_url} alt="" size="sm" />
        ) : (
          <div className="catalog-browse-card-placeholder" aria-hidden>
            {entity.name[0]?.toUpperCase() ?? "?"}
          </div>
        )}
      </div>
      <div className="catalog-browse-card-info">
        <h3 className="catalog-browse-card-title">{entity.name}</h3>
        {hint && <p className="catalog-browse-card-meta">{hint}</p>}
      </div>
    </Link>
  );
}
