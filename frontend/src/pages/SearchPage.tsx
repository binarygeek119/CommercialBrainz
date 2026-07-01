import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["search", submitted],
    queryFn: () => api.search(submitted, "all"),
    enabled: submitted.length > 0,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(query);
  };

  return (
    <div>
      <h1 className="page-title">Search</h1>
      <form className="search-bar" onSubmit={handleSearch} style={{ marginBottom: "2rem" }}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search commercials, advertisers, videos..."
        />
        <button type="submit" className="btn btn-primary">
          Search
        </button>
      </form>

      {isLoading && <p className="muted">Searching...</p>}
      {data && (
        <div className="stack">
          {data.map((r) => (
            <Link
              key={`${r.type}-${r.sbid}`}
              to={`/${r.type}/${r.sbid}`}
              className="card"
              style={{ textDecoration: "none", color: "inherit" }}
            >
              <span className="badge badge-open">{r.type}</span>
              <h3 style={{ marginTop: "0.5rem" }}>{r.title}</h3>
              {r.subtitle && <p className="muted mono">{r.subtitle}</p>}
            </Link>
          ))}
          {data.length === 0 && <p className="muted">No results found.</p>}
        </div>
      )}
    </div>
  );
}
