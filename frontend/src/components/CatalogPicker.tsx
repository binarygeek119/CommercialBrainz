import { useEffect, useRef, useState } from "react";
import { api, type SearchResult } from "../api";
import type { CatalogKindConfig } from "../catalog/kinds";

export type CatalogSelection = {
  id?: string;
  name?: string;
};

interface Props {
  kind: CatalogKindConfig;
  value: CatalogSelection;
  onChange: (value: CatalogSelection) => void;
  /** When false, only existing entities can be selected (no create-by-name). */
  allowCreate?: boolean;
}

export default function CatalogPicker({
  kind,
  value,
  onChange,
  allowCreate = true,
}: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (value.id && value.name) {
      setQuery(value.name);
    } else if (value.name) {
      setQuery(value.name);
    } else if (!value.id) {
      setQuery("");
    }
  }, [value.id, value.name]);

  useEffect(() => {
    if (!open) return;
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const items = query.trim()
          ? await api.searchCatalog(kind.key, query.trim())
          : (await api.listCatalog(kind.key, "", 0, 30)).items.map((a) => ({
              type: kind.key,
              sbid: a.sbid,
              title: a.name,
              subtitle: null,
            }));
        setResults(items);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [query, open, kind.key]);

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const selectExisting = (item: SearchResult) => {
    setQuery(item.title);
    onChange({ id: item.sbid, name: item.title });
    setOpen(false);
  };

  const handleInputChange = (text: string) => {
    setQuery(text);
    const trimmed = text.trim();
    if (!trimmed) {
      onChange({});
    } else if (allowCreate) {
      onChange({ name: trimmed });
    } else {
      onChange({});
    }
    setOpen(true);
  };

  const trimmed = query.trim();
  const exactMatch = results.some((r) => r.title.toLowerCase() === trimmed.toLowerCase());
  const showCreateHint =
    allowCreate && trimmed.length > 0 && !exactMatch && !value.id;

  return (
    <div ref={wrapRef} className="advertiser-picker">
      <input
        type="text"
        value={query}
        onChange={(e) => handleInputChange(e.target.value)}
        onFocus={() => setOpen(true)}
        placeholder={
          allowCreate
            ? `Search existing ${kind.plural.toLowerCase()} or type a new one`
            : `Search existing ${kind.plural.toLowerCase()}`
        }
        autoComplete="off"
      />
      {value.id && (
        <p className="muted" style={{ marginTop: "0.35rem", fontSize: "0.85rem" }}>
          Using existing {kind.label.toLowerCase()}. Clear the field to pick or create another.
        </p>
      )}
      {showCreateHint && (
        <p className="muted" style={{ marginTop: "0.35rem", fontSize: "0.85rem" }}>
          New {kind.label.toLowerCase()} &quot;{trimmed}&quot; will be submitted for approval (10
          community votes or 1 mod).
        </p>
      )}
      {!allowCreate && trimmed && !value.id && !loading && (
        <p className="muted" style={{ marginTop: "0.35rem", fontSize: "0.85rem" }}>
          Select an existing {kind.label.toLowerCase()} from the list, or clear the field.
        </p>
      )}
      {open && (loading || results.length > 0) && (
        <ul className="advertiser-picker-list">
          {loading && <li className="muted">Searching…</li>}
          {!loading &&
            results.map((item) => (
              <li key={item.sbid}>
                <button type="button" onClick={() => selectExisting(item)}>
                  {item.title}
                </button>
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}
