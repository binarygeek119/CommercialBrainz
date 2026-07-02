import { Link } from "react-router-dom";
import {
  BRAND_METADATA_FIELDS,
  SOCIAL_FIELDS,
  getBrandFieldValue,
} from "../utils/brandMetadata";
import type { Advertiser } from "../api";

function renderAliasLinks(brand: Advertiser) {
  const aliases = (brand.metadata?.aliases as string[] | undefined) ?? [];
  const links =
    brand.alias_links?.length === aliases.length
      ? brand.alias_links
      : aliases.map((name) => ({ name, sbid: null as string | null }));

  return links.map((link, index) => (
    <span key={link.name}>
      {index > 0 && ", "}
      {link.sbid ? (
        <Link to={`/advertiser/${link.sbid}`}>{link.name}</Link>
      ) : (
        <Link to={`/brands?q=${encodeURIComponent(link.name)}`}>{link.name}</Link>
      )}
    </span>
  ));
}

export default function BrandMetadataDisplay({ brand }: { brand: Advertiser }) {
  const social = brand.metadata?.social ?? {};
  const hasSocial = SOCIAL_FIELDS.some(({ key }) => social[key]?.trim());

  const rows = BRAND_METADATA_FIELDS.filter(({ key }) => {
    const value = getBrandFieldValue(brand, key);
    if (key === "aliases") return Array.isArray(value) && value.length > 0;
    return value != null && value !== "";
  });

  if (!rows.length && !hasSocial) return null;

  return (
    <section style={{ marginTop: "1.25rem" }}>
      <h2 style={{ fontSize: "1.1rem", marginBottom: "0.75rem" }}>About</h2>
      <dl className="metadata-list" style={{ margin: 0 }}>
        {rows.map(({ key, label }) => {
          const value = getBrandFieldValue(brand, key);
          const isUrl = key.endsWith("_url") || key === "website";
          const isAliases = key === "aliases";

          return (
            <div key={key} style={{ marginBottom: "0.65rem" }}>
              <dt className="muted" style={{ fontSize: "0.85rem", marginBottom: "0.15rem" }}>
                {label}
              </dt>
              <dd style={{ margin: 0 }}>
                {isAliases ? (
                  renderAliasLinks(brand)
                ) : isUrl && value ? (
                  <a href={String(value)} target="_blank" rel="noreferrer noopener">
                    {String(value)}
                  </a>
                ) : (
                  String(value ?? "")
                )}
              </dd>
            </div>
          );
        })}
        {hasSocial && (
          <div style={{ marginBottom: "0.65rem" }}>
            <dt className="muted" style={{ fontSize: "0.85rem", marginBottom: "0.15rem" }}>
              Social
            </dt>
            <dd style={{ margin: 0, display: "flex", flexWrap: "wrap", gap: "0.5rem 1rem" }}>
              {SOCIAL_FIELDS.filter(({ key }) => social[key]?.trim()).map(({ key, label }) => (
                <a key={key} href={social[key]} target="_blank" rel="noreferrer noopener">
                  {label}
                </a>
              ))}
            </dd>
          </div>
        )}
      </dl>
    </section>
  );
}
