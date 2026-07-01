import { useEffect, useRef, useState } from "react";
import { api, type SearchResult } from "../api";

export interface AdvertiserSelection {
  advertiser_id?: string;
  advertiser_name?: string;
}

interface Props {
  value: AdvertiserSelection;
  onChange: (value: AdvertiserSelection) => void;
}

export default function AdvertiserPicker({ value, onChange }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (value.advertiser_id && value.advertiser_name) {
      setQuery(value.advertiser_name);
    } else if (value.advertiser_name) {
      setQuery(value.advertiser_name);
    } else if (!value.advertiser_id) {
      setQuery("");
    }
  }, [value.advertiser_id, value.advertiser_name]);

  useEffect(() => {
    if (!open) return;
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const items = query.trim()
          ? await api.searchAdvertisers(query.trim())
          : (await api.listAdvertisers("", 0, 30)).items.map((a) => ({
              type: "advertiser",
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
  }, [query, open]);

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
    onChange({ advertiser_id: item.sbid, advertiser_name: item.title });
    setOpen(false);
  };

  const handleInputChange = (text: string) => {
    setQuery(text);
    onChange({ advertiser_name: text.trim() || undefined });
    setOpen(true);
  };

  const trimmed = query.trim();
  const exactMatch = results.some((r) => r.title.toLowerCase() === trimmed.toLowerCase());
  const showCreateHint = trimmed.length > 0 && !exactMatch && !value.advertiser_id;

  return (
    <div ref={wrapRef} className="advertiser-picker">
      <input
        type="text"
        value={query}
        onChange={(e) => handleInputChange(e.target.value)}
        onFocus={() => setOpen(true)}
        placeholder="Search existing brands or type a new one"
        autoComplete="off"
      />
      {value.advertiser_id && (
        <p className="muted" style={{ marginTop: "0.35rem", fontSize: "0.85rem" }}>
          Using existing brand. Clear the field to pick or create another.
        </p>
      )}
      {showCreateHint && (
        <p className="muted" style={{ marginTop: "0.35rem", fontSize: "0.85rem" }}>
          New brand &quot;{trimmed}&quot; will be submitted for approval (10 community votes or 1
          mod).
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
