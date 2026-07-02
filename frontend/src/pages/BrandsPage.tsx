import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type Advertiser } from "../api";
import BrandLogoImage from "../components/BrandLogoImage";

async function fetchAllBrands(query: string): Promise<Advertiser[]> {
  const limit = 100;
  let offset = 0;
  let total = Infinity;
  const items: Advertiser[] = [];

  while (offset < total) {
    const page = await api.listAdvertisers(query, offset, limit);
    items.push(...page.items);
    total = page.total;
    offset += limit;
    if (page.items.length === 0) break;
  }

  return items.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }));
}

function groupByLetter(brands: Advertiser[]): [string, Advertiser[]][] {
  const groups = new Map<string, Advertiser[]>();
  for (const brand of brands) {
    const first = brand.name.trim()[0]?.toUpperCase() || "#";
    const letter = /^[A-Z]$/.test(first) ? first : "#";
    const list = groups.get(letter) ?? [];
    list.push(brand);
    groups.set(letter, list);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

export default function BrandsPage() {
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

  const { data: brands = [], isLoading, error, isFetching } = useQuery({
    queryKey: ["brands", debouncedQuery],
    queryFn: () => fetchAllBrands(debouncedQuery),
  });

  const grouped = useMemo(() => groupByLetter(brands), [brands]);
  const showGroups = !debouncedQuery;

  return (
    <div>
      <h1 className="page-title">Brands</h1>
      <p className="muted" style={{ marginBottom: "1rem" }}>
        Approved advertisers and brands, sorted A–Z.
      </p>

      <div className="form-group" style={{ maxWidth: 480, marginBottom: "1.5rem" }}>
        <label htmlFor="brand-search">Search brands</label>
        <input
          id="brand-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter by name…"
          autoComplete="off"
        />
      </div>

      {isLoading && <p className="muted">Loading brands…</p>}
      {error && <p className="error">{(error as Error).message}</p>}
      {!isLoading && !error && brands.length === 0 && (
        <p className="muted">
          {debouncedQuery ? `No brands matching “${debouncedQuery}”.` : "No approved brands yet."}
        </p>
      )}

      {isFetching && !isLoading && (
        <p className="muted" style={{ marginBottom: "1rem" }}>
          Updating…
        </p>
      )}

      {showGroups
        ? grouped.map(([letter, items]) => (
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
              <BrandGrid brands={items} />
            </section>
          ))
        : brands.length > 0 && <BrandGrid brands={brands} />}

      {!isLoading && brands.length > 0 && (
        <p className="muted" style={{ marginTop: "1.5rem" }}>
          {brands.length} brand{brands.length === 1 ? "" : "s"}
          {debouncedQuery ? ` matching “${debouncedQuery}”` : ""}.
        </p>
      )}
    </div>
  );
}

function BrandGrid({ brands }: { brands: Advertiser[] }) {
  return (
    <div className="grid grid-2">
      {brands.map((brand) => (
        <Link
          key={brand.sbid}
          to={`/advertiser/${brand.sbid}`}
          className="card"
          style={{
            textDecoration: "none",
            color: "inherit",
            display: "flex",
            gap: "0.75rem",
            alignItems: "center",
          }}
        >
          {brand.logo_url ? (
            <BrandLogoImage src={brand.logo_url} alt="" size="sm" />
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
              {brand.name[0]?.toUpperCase() ?? "?"}
            </div>
          )}
          <div style={{ minWidth: 0 }}>
            <h3 style={{ margin: 0, fontSize: "1rem" }}>{brand.name}</h3>
            {(brand.industry || brand.country) && (
              <p className="muted" style={{ margin: "0.25rem 0 0", fontSize: "0.85rem" }}>
                {[brand.industry, brand.country].filter(Boolean).join(" · ")}
              </p>
            )}
            {brand.description && (
              <p className="muted" style={{ margin: "0.25rem 0 0", fontSize: "0.85rem" }}>
                {brand.description.length > 80
                  ? `${brand.description.slice(0, 80)}…`
                  : brand.description}
              </p>
            )}
          </div>
        </Link>
      ))}
    </div>
  );
}
