import { Link } from "react-router-dom";
import type { CommercialDetail } from "../api";
import {
  COMMERCIAL_METADATA_FIELDS,
  commercialHasFieldValue,
  formatCommercialFieldValue,
} from "../utils/commercialMetadata";

function renderCommercialField(commercial: CommercialDetail, key: string) {
  if (key === "advertiser" && commercial.advertiser) {
    return (
      <Link to={`/advertiser/${commercial.advertiser.sbid}`}>{commercial.advertiser.name}</Link>
    );
  }
  if (key === "store" && commercial.store) {
    return <Link to={`/store/${commercial.store.sbid}`}>{commercial.store.name}</Link>;
  }
  if (key === "service" && commercial.service) {
    return <Link to={`/service/${commercial.service.sbid}`}>{commercial.service.name}</Link>;
  }
  if (key === "event" && commercial.event) {
    return <Link to={`/event/${commercial.event.sbid}`}>{commercial.event.name}</Link>;
  }
  if (key === "holiday" && commercial.holiday) {
    return <Link to={`/holiday/${commercial.holiday.sbid}`}>{commercial.holiday.name}</Link>;
  }
  if (key === "agency" && commercial.agency) {
    return commercial.agency.name;
  }
  if (key === "sbid") {
    return <span className="mono">{commercial.sbid}</span>;
  }
  const value =
    key === "advertiser" ||
    key === "store" ||
    key === "service" ||
    key === "event" ||
    key === "holiday" ||
    key === "agency"
      ? null
      : commercial[key as keyof CommercialDetail];
  return formatCommercialFieldValue(key, value);
}

export default function CommercialMetadataDisplay({ commercial }: { commercial: CommercialDetail }) {
  const rows = COMMERCIAL_METADATA_FIELDS.filter(({ key }) =>
    commercialHasFieldValue(commercial as unknown as Record<string, unknown>, key)
  );

  if (rows.length === 0) return null;

  return (
    <section className="card" style={{ marginTop: "1rem" }}>
      <h2 style={{ fontSize: "1.1rem", marginTop: 0, marginBottom: "0.75rem" }}>Details</h2>
      <dl className="metadata-list">
        {rows.map(({ key, label }) => (
          <div key={key} className="metadata-row">
            <dt className="muted">{label}</dt>
            <dd>{renderCommercialField(commercial, key)}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
