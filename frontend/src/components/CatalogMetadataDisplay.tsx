import { Link } from "react-router-dom";
import type { CatalogEntity } from "../api";
import {
  SOCIAL_FIELDS,
  getCatalogFieldValue,
  type CatalogKindConfig,
} from "../catalog/kinds";

function renderAliasLinks(kind: CatalogKindConfig, entity: CatalogEntity) {
  const aliases = (entity.metadata?.aliases as string[] | undefined) ?? [];
  const links =
    entity.alias_links?.length === aliases.length
      ? entity.alias_links
      : aliases.map((name) => ({ name, sbid: null as string | null }));

  return links.map((link, index) => (
    <span key={link.name}>
      {index > 0 && ", "}
      {link.sbid ? (
        <Link to={kind.detailPath(link.sbid)}>{link.name}</Link>
      ) : (
        <Link to={`${kind.listPath}?q=${encodeURIComponent(link.name)}`}>{link.name}</Link>
      )}
    </span>
  ));
}

export default function CatalogMetadataDisplay({
  kind,
  entity,
}: {
  kind: CatalogKindConfig;
  entity: CatalogEntity;
}) {
  const social = entity.metadata?.social ?? {};
  const hasSocial = SOCIAL_FIELDS.some(({ key }) => social[key]?.trim());
  const data = entity as unknown as Record<string, unknown> & {
    metadata?: Record<string, unknown>;
  };

  const rows = kind.fields.filter((field) => {
    const value = getCatalogFieldValue(data, field);
    if (field.key === "aliases") return Array.isArray(value) && value.length > 0;
    return value != null && value !== "";
  });

  if (!rows.length && !hasSocial) return null;

  return (
    <section style={{ marginTop: "1.25rem" }}>
      <h2 style={{ fontSize: "1.1rem", marginBottom: "0.75rem" }}>About</h2>
      <dl className="metadata-list" style={{ margin: 0 }}>
        {rows.map((field) => {
          const value = getCatalogFieldValue(data, field);
          const isUrl = field.key.endsWith("_url") || field.key === "website";
          const isAliases = field.key === "aliases";

          return (
            <div key={field.key} style={{ marginBottom: "0.65rem" }}>
              <dt className="muted" style={{ fontSize: "0.85rem", marginBottom: "0.15rem" }}>
                {field.label}
              </dt>
              <dd style={{ margin: 0 }}>
                {isAliases ? (
                  renderAliasLinks(kind, entity)
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
