import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type CommercialListItem } from "../api";
import { formatCommercialPeriod } from "../utils/commercialPeriod";

async function fetchAllCommercials(query: string): Promise<CommercialListItem[]> {
  const limit = 100;
  let offset = 0;
  let total = Infinity;
  const items: CommercialListItem[] = [];

  while (offset < total) {
    const page = await api.listCommercials(query, offset, limit);
    items.push(...page.items);
    total = page.total;
    offset += limit;
    if (page.items.length === 0) break;
  }

  return items.sort((a, b) => a.title.localeCompare(b.title, undefined, { sensitivity: "base" }));
}

function groupByLetter(commercials: CommercialListItem[]): [string, CommercialListItem[]][] {
  const groups = new Map<string, CommercialListItem[]>();
  for (const commercial of commercials) {
    const first = commercial.title.trim()[0]?.toUpperCase() || "#";
    const letter = /^[A-Z]$/.test(first) ? first : "#";
    const list = groups.get(letter) ?? [];
    list.push(commercial);
    groups.set(letter, list);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

export default function CommercialsPage() {
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

  const { data: commercials = [], isLoading, error, isFetching } = useQuery({
    queryKey: ["commercials", debouncedQuery],
    queryFn: () => fetchAllCommercials(debouncedQuery),
  });

  const grouped = useMemo(() => groupByLetter(commercials), [commercials]);
  const showGroups = !debouncedQuery;

  return (
    <div>
      <h1 className="page-title">Commercials</h1>
      <p className="muted" style={{ marginBottom: "1rem" }}>
        Commercial campaigns in the archive, sorted A–Z.
      </p>

      <div className="form-group" style={{ maxWidth: 480, marginBottom: "1.5rem" }}>
        <label htmlFor="commercial-search">Search commercials</label>
        <input
          id="commercial-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter by title, campaign, or description…"
          autoComplete="off"
        />
      </div>

      {isLoading && <p className="muted">Loading commercials…</p>}
      {error && <p className="error">{(error as Error).message}</p>}
      {!isLoading && !error && commercials.length === 0 && (
        <p className="muted">
          {debouncedQuery
            ? `No commercials matching “${debouncedQuery}”.`
            : "No commercials in the archive yet."}
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
              <CommercialGrid commercials={items} />
            </section>
          ))
        : commercials.length > 0 && <CommercialGrid commercials={commercials} />}

      {!isLoading && commercials.length > 0 && (
        <p className="muted" style={{ marginTop: "1.5rem" }}>
          {commercials.length} commercial{commercials.length === 1 ? "" : "s"}
          {debouncedQuery ? ` matching “${debouncedQuery}”` : ""}.
        </p>
      )}
    </div>
  );
}

function CommercialGrid({ commercials }: { commercials: CommercialListItem[] }) {
  return (
    <div className="grid grid-2">
      {commercials.map((commercial) => {
        const period = formatCommercialPeriod(commercial.year, commercial.decade);
        const meta = [
          commercial.advertiser_name,
          period,
          commercial.public_video_count
            ? `${commercial.public_video_count} video${commercial.public_video_count === 1 ? "" : "s"}`
            : null,
        ].filter(Boolean);

        return (
          <Link
            key={commercial.sbid}
            to={`/commercial/${commercial.sbid}`}
            className="card"
            style={{ textDecoration: "none", color: "inherit", display: "block" }}
          >
            <h3 style={{ margin: 0, fontSize: "1rem" }}>{commercial.title}</h3>
            {commercial.campaign_name && commercial.campaign_name !== commercial.title && (
              <p className="muted" style={{ margin: "0.25rem 0 0", fontSize: "0.85rem" }}>
                {commercial.campaign_name}
              </p>
            )}
            {meta.length > 0 && (
              <p className="muted" style={{ margin: "0.35rem 0 0", fontSize: "0.85rem" }}>
                {meta.join(" · ")}
              </p>
            )}
            {commercial.description && (
              <p className="muted" style={{ margin: "0.35rem 0 0", fontSize: "0.85rem" }}>
                {commercial.description.length > 120
                  ? `${commercial.description.slice(0, 120)}…`
                  : commercial.description}
              </p>
            )}
          </Link>
        );
      })}
    </div>
  );
}
