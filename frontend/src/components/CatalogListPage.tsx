import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type CatalogEntity } from "../api";
import BrandLogoImage from "./BrandLogoImage";
import type { CatalogKindConfig } from "../catalog/kinds";

async function fetchAll(kind: CatalogKindConfig, query: string): Promise<CatalogEntity[]> {
  const limit = 100;
  let offset = 0;
  let total = Infinity;
  const items: CatalogEntity[] = [];

  while (offset < total) {
    const page = await api.listCatalog(kind.key, query, offset, limit);
    items.push(...page.items);
    total = page.total;
    offset += limit;
    if (page.items.length === 0) break;
  }

  return items.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }));
}

function groupByLetter(entities: CatalogEntity[]): [string, CatalogEntity[]][] {
  const groups = new Map<string, CatalogEntity[]>();
  for (const entity of entities) {
    const first = entity.name.trim()[0]?.toUpperCase() || "#";
    const letter = /^[A-Z]$/.test(first) ? first : "#";
    const list = groups.get(letter) ?? [];
    list.push(entity);
    groups.set(letter, list);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

function listSubtitle(kind: CatalogKindConfig, entity: CatalogEntity): string {
  const parts: string[] = [];
  const data = entity as unknown as Record<string, unknown>;
  for (const field of kind.fields.filter((f) => f.listHint)) {
    const value = data[field.key];
    if (value != null && value !== "") parts.push(String(value));
  }
  return parts.join(" · ");
}

export default function CatalogListPage({ kind }: { kind: CatalogKindConfig }) {
  const [searchParams] = useSearchParams();
  const initialQuery = searchParams.get("q") ?? "";
  const [query, setQuery] = useState(initialQuery);
  const [debouncedQuery, setDebouncedQuery] = useState(initialQuery.trim());

  useEffect(() => {
    const q = searchParams.get("q") ?? "";
    setQuery(q);
    setDebouncedQuery(q.trim());
  }, [searchParams]);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [query]);

  const { data: items = [], isLoading, error, isFetching } = useQuery({
    queryKey: [kind.key, "list", debouncedQuery],
    queryFn: () => fetchAll(kind, debouncedQuery),
  });

  const grouped = useMemo(() => groupByLetter(items), [items]);
  const showGroups = !debouncedQuery;

  return (
    <div>
      <h1 className="page-title">{kind.plural}</h1>
      <p className="muted" style={{ marginBottom: "1rem" }}>
        Approved {kind.plural.toLowerCase()}, sorted A–Z.
      </p>

      <div className="form-group" style={{ maxWidth: 480, marginBottom: "1.5rem" }}>
        <label htmlFor={`${kind.key}-search`}>Search {kind.plural.toLowerCase()}</label>
        <input
          id={`${kind.key}-search`}
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter by name…"
          autoComplete="off"
        />
      </div>

      {isLoading && <p className="muted">Loading {kind.plural.toLowerCase()}…</p>}
      {error && <p className="error">{(error as Error).message}</p>}
      {!isLoading && !error && items.length === 0 && (
        <p className="muted">
          {debouncedQuery
            ? `No ${kind.plural.toLowerCase()} matching “${debouncedQuery}”.`
            : `No approved ${kind.plural.toLowerCase()} yet.`}
        </p>
      )}

      {isFetching && !isLoading && (
        <p className="muted" style={{ marginBottom: "1rem" }}>
          Updating…
        </p>
      )}

      {showGroups
        ? grouped.map(([letter, group]) => (
            <section key={letter} style={{ marginBottom: "2rem" }}>
              <h2
                className="muted"
                style={{
                  fontSize: "1.1rem",
                  letterSpacing: "0.08em",
                  borderBottom: "1px solid var(--border, #333)",
                  paddingBottom: "0.35rem",
                  marginBottom: "0.75rem",
                }}
              >
                {letter}
              </h2>
              <EntityGrid kind={kind} items={group} />
            </section>
          ))
        : items.length > 0 && <EntityGrid kind={kind} items={items} />}

      {!isLoading && items.length > 0 && (
        <p className="muted" style={{ marginTop: "1.5rem" }}>
          {items.length} {items.length === 1 ? kind.label.toLowerCase() : kind.plural.toLowerCase()}
          {debouncedQuery ? ` matching “${debouncedQuery}”` : ""}.
        </p>
      )}
    </div>
  );
}

function EntityGrid({ kind, items }: { kind: CatalogKindConfig; items: CatalogEntity[] }) {
  return (
    <div className="grid grid-2">
      {items.map((entity) => {
        const subtitle = listSubtitle(kind, entity);
        return (
          <Link
            key={entity.sbid}
            to={kind.detailPath(entity.sbid)}
            className="card"
            style={{
              textDecoration: "none",
              color: "inherit",
              display: "flex",
              gap: "0.75rem",
              alignItems: "center",
            }}
          >
            {entity.logo_url ? (
              <BrandLogoImage src={entity.logo_url} alt="" size="sm" />
            ) : (
              <div
                aria-hidden
                style={{
                  width: 48,
                  height: 48,
                  flexShrink: 0,
                  borderRadius: 4,
                  background: "var(--border, #333)",
                  display: "grid",
                  placeItems: "center",
                  fontWeight: 600,
                  fontSize: "1.1rem",
                }}
              >
                {entity.name[0]?.toUpperCase() ?? "?"}
              </div>
            )}
            <div style={{ minWidth: 0 }}>
              <h3 style={{ margin: 0, fontSize: "1rem" }}>{entity.name}</h3>
              {subtitle && (
                <p className="muted" style={{ margin: "0.25rem 0 0", fontSize: "0.85rem" }}>
                  {subtitle}
                </p>
              )}
              {entity.description && (
                <p className="muted" style={{ margin: "0.25rem 0 0", fontSize: "0.85rem" }}>
                  {entity.description.length > 80
                    ? `${entity.description.slice(0, 80)}…`
                    : entity.description}
                </p>
              )}
            </div>
          </Link>
        );
      })}
    </div>
  );
}
