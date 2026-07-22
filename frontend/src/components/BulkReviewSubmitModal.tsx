import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, type BulkSubmissionItem, type SubmissionTerms } from "../api";
import AdvertiserPicker, { type AdvertiserSelection } from "./AdvertiserPicker";
import CatalogPicker, { type CatalogSelection } from "./CatalogPicker";
import { CATALOG_KIND_LIST } from "../catalog/kinds";
import {
  RegionSelect,
  SubRegionSelect,
  regionHasSubRegionPicker,
  regionSelectionToPayload,
  subRegionFieldLabel,
  type RegionSelection,
} from "./RegionPicker";
import SubmissionGenresFields, {
  EMPTY_SUBMISSION_GENRES,
} from "./SubmissionGenresFields";
import type { SubmissionGenres } from "../utils/submissionGenres";
import { submissionGenresPayload } from "../utils/submissionGenres";
import { COMMERCIAL_DECADES } from "../utils/commercialPeriod";
import { COMMERCIAL_TYPES, isBumperType } from "../utils/commercialTypes";
import { formatDurationMs } from "../utils/youtube";
import { youtubeIdThumbnail } from "../utils/videoThumbnail";
import SubmissionTermsView from "./SubmissionTermsView";

type FormState = {
  commercial_title: string;
  year: string;
  decade: string;
  commercial_type: string;
  bumper_channel: string;
  language: string;
  transcript: string;
  slogan: string;
  tags: string;
  comment: string;
};

function tagsFromMeta(meta: Record<string, unknown>): string {
  const raw = meta.tags;
  if (Array.isArray(raw)) {
    return raw.map(String).filter(Boolean).join(", ");
  }
  if (typeof raw === "string") return raw;
  return "";
}

function formFromItem(item: BulkSubmissionItem): FormState {
  const meta = (item.metadata || {}) as Record<string, unknown>;
  return {
    commercial_title: String(meta.title || meta.youtube_title || item.title || ""),
    year: "",
    decade: "",
    commercial_type: "",
    bumper_channel: "",
    language: String(meta.language || ""),
    transcript: String(meta.transcript || ""),
    slogan: String(meta.slogan || ""),
    tags: tagsFromMeta(meta),
    comment: String(meta.suggested_comment || ""),
  };
}

async function suggestAdvertiserFromChannel(channel: string): Promise<AdvertiserSelection> {
  const trimmed = channel.trim();
  if (!trimmed) return {};
  try {
    const matches = await api.searchAdvertisers(trimmed);
    const exact = matches.find((m) => m.title.toLowerCase() === trimmed.toLowerCase());
    if (exact) return { advertiser_id: exact.sbid, advertiser_name: exact.title };
    const partial = matches.find((m) => m.title.toLowerCase().includes(trimmed.toLowerCase()));
    if (partial) return { advertiser_id: partial.sbid, advertiser_name: partial.title };
  } catch {
    /* ignore */
  }
  return { advertiser_name: trimmed };
}

interface Props {
  item: BulkSubmissionItem;
  onClose: () => void;
  onSubmitted: () => void;
}

export default function BulkReviewSubmitModal({ item, onClose, onSubmitted }: Props) {
  const meta = (item.metadata || {}) as Record<string, unknown>;
  const [form, setForm] = useState<FormState>(() => formFromItem(item));
  const [genres, setGenres] = useState<SubmissionGenres>({ ...EMPTY_SUBMISSION_GENRES });
  const [advertiser, setAdvertiser] = useState<AdvertiserSelection>({});
  const [catalogSelections, setCatalogSelections] = useState<Record<string, CatalogSelection>>({
    store: {},
    service: {},
    event: {},
    holiday: {},
  });
  const [regionSelection, setRegionSelection] = useState<RegionSelection>({});
  const [terms, setTerms] = useState<SubmissionTerms | null>(null);
  const [termsAgreed, setTermsAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const advertiserTouched = useRef(false);

  const thumbnail =
    (typeof meta.thumbnail_url === "string" && meta.thumbnail_url) ||
    youtubeIdThumbnail(item.youtube_id);
  const channelName = typeof meta.channel_name === "string" ? meta.channel_name : "";
  const durationMs = typeof meta.duration_ms === "number" ? meta.duration_ms : null;
  const resolution = typeof meta.resolution === "string" ? meta.resolution : "";
  const aspectRatio = typeof meta.aspect_ratio === "string" ? meta.aspect_ratio : "";
  const uploadDate = typeof meta.upload_date === "string" ? meta.upload_date : "";
  const displayTitle =
    (typeof meta.title === "string" && meta.title) ||
    (typeof meta.youtube_title === "string" && meta.youtube_title) ||
    item.title ||
    item.youtube_id;

  useEffect(() => {
    setForm(formFromItem(item));
    setGenres({ ...EMPTY_SUBMISSION_GENRES });
    setCatalogSelections({ store: {}, service: {}, event: {}, holiday: {} });
    setRegionSelection({});
    setTermsAgreed(false);
    setError(null);
    advertiserTouched.current = false;

    const channel = typeof item.metadata?.channel_name === "string" ? item.metadata.channel_name : "";
    if (channel) {
      setGenres((prev) =>
        prev.target_channel.trim() ? prev : { ...prev, target_channel: channel }
      );
      void suggestAdvertiserFromChannel(channel).then((suggestion) => {
        if (!advertiserTouched.current) setAdvertiser(suggestion);
      });
    } else {
      setAdvertiser({});
    }
  }, [item]);

  useEffect(() => {
    api
      .getSubmissionTerms()
      .then(setTerms)
      .catch(() => setTerms(null));
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!termsAgreed) {
      setError("You must agree to the Terms of Submission.");
      return;
    }
    if (!form.commercial_title.trim()) {
      setError("Commercial title is required.");
      return;
    }
    if (isBumperType(form.commercial_type) && !form.bumper_channel.trim()) {
      setError("Channel is required when type is Bumper.");
      return;
    }

    setBusy(true);
    try {
      const catalogFields = (() => {
        const entries: [string, string][] = [];
        for (const kind of CATALOG_KIND_LIST) {
          const sel = catalogSelections[kind.key] ?? {};
          if (sel.id) entries.push([kind.idKey, sel.id]);
          else if (sel.name) entries.push([kind.nameKey, sel.name]);
        }
        return Object.fromEntries(entries);
      })();

      await api.bulkSubmitItemSubmit(item.id, {
        commercial: {
          title: form.commercial_title.trim(),
          ...(advertiser.advertiser_id
            ? { advertiser_id: advertiser.advertiser_id }
            : advertiser.advertiser_name
              ? { advertiser_name: advertiser.advertiser_name }
              : {}),
          ...catalogFields,
          year: form.year ? parseInt(form.year, 10) : undefined,
          decade: form.decade ? parseInt(form.decade, 10) : undefined,
          ...(form.commercial_type
            ? {
                commercial_type: form.commercial_type,
                ...(isBumperType(form.commercial_type)
                  ? { bumper_channel: form.bumper_channel.trim() }
                  : {}),
              }
            : {}),
        },
        channel_name: channelName || undefined,
        upload_date: uploadDate || undefined,
        duration_ms: durationMs ?? undefined,
        aspect_ratio: aspectRatio || undefined,
        resolution: resolution || undefined,
        thumbnail_url: typeof meta.thumbnail_url === "string" ? meta.thumbnail_url : undefined,
        language: form.language || undefined,
        ...regionSelectionToPayload(regionSelection),
        transcript: form.transcript || undefined,
        slogan: form.slogan || undefined,
        tags: form.tags
          ? form.tags
              .split(",")
              .map((t) => t.trim())
              .filter(Boolean)
          : [],
        genres: submissionGenresPayload(genres),
        comment: form.comment || undefined,
        metadata: typeof meta.metadata === "object" && meta.metadata ? meta.metadata : meta,
        terms_agreed: true,
      });
      onSubmitted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="add-link-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="bulk-review-dialog-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !busy) onClose();
      }}
    >
      <div className="add-link-dialog-card bulk-review-dialog-card">
        <div className="flex-between" style={{ gap: "0.75rem", marginBottom: "0.75rem" }}>
          <h2 id="bulk-review-dialog-title" className="add-link-dialog-title">
            Review &amp; submit
          </h2>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={busy}>
            Close
          </button>
        </div>

        <div className="add-link-dialog-body">
          <p className="muted" style={{ marginTop: 0 }}>
            Same fields as single submit. Prefetched hash stays attached. After submit this popup
            closes and the next playlist link enters the review window.
          </p>

          <div style={{ marginBottom: "1rem" }}>
            {thumbnail && (
              <img
                src={thumbnail}
                alt=""
                style={{
                  width: "100%",
                  maxHeight: 220,
                  objectFit: "cover",
                  borderRadius: 4,
                  marginBottom: "0.75rem",
                }}
              />
            )}
            <div
              style={{
                position: "relative",
                paddingBottom: "56.25%",
                height: 0,
                overflow: "hidden",
                borderRadius: 4,
                background: "#000",
              }}
            >
              <iframe
                title="YouTube preview"
                src={`https://www.youtube-nocookie.com/embed/${item.youtube_id}`}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  height: "100%",
                  border: 0,
                }}
              />
            </div>
            <div className="card" style={{ marginTop: "0.75rem", padding: "0.75rem" }}>
              <p style={{ margin: 0, fontWeight: 600 }}>{displayTitle}</p>
              <p className="muted" style={{ margin: "0.25rem 0 0", fontSize: "0.85rem" }}>
                <a href={item.youtube_url} target="_blank" rel="noreferrer" className="mono">
                  {item.youtube_id}
                </a>
                {channelName ? ` · ${channelName}` : ""}
                {durationMs ? ` · ${formatDurationMs(durationMs)}` : ""}
                {resolution ? ` · ${resolution}` : ""}
                {aspectRatio ? ` · ${aspectRatio}` : ""}
                {uploadDate ? ` · uploaded ${uploadDate}` : ""}
              </p>
              <p className="muted" style={{ margin: "0.35rem 0 0", fontSize: "0.85rem" }}>
                Status: <span className="badge badge-submitted">{item.status}</span>
              </p>
            </div>
          </div>

          {terms && (
            <details className="card terms-card" style={{ marginBottom: "1rem" }}>
              <summary style={{ cursor: "pointer", fontWeight: 600 }}>
                Terms of Submission (v{terms.version})
              </summary>
              <div style={{ marginTop: "1rem" }}>
                <SubmissionTermsView terms={terms} compact />
              </div>
            </details>
          )}

          <form onSubmit={(e) => void handleSubmit(e)}>
            <div className="form-group">
              <label htmlFor="bulk-review-title">Commercial Title *</label>
              <input
                id="bulk-review-title"
                required
                value={form.commercial_title}
                onChange={(e) => setForm({ ...form, commercial_title: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label>Advertiser / Brand</label>
              <AdvertiserPicker
                value={advertiser}
                onChange={(next) => {
                  advertiserTouched.current = true;
                  setAdvertiser(next);
                }}
              />
              <p className="muted" style={{ marginTop: "0.35rem", fontSize: "0.85rem" }}>
                Search an existing brand or enter a new one.
              </p>
            </div>

            {CATALOG_KIND_LIST.map((kind) => (
              <div className="form-group" key={kind.key}>
                <label>{kind.label}</label>
                <CatalogPicker
                  kind={kind}
                  value={catalogSelections[kind.key] ?? {}}
                  onChange={(next) =>
                    setCatalogSelections((prev) => ({ ...prev, [kind.key]: next }))
                  }
                />
              </div>
            ))}

            <div className="form-group">
              <label htmlFor="bulk-review-type">Type of commercial</label>
              <select
                id="bulk-review-type"
                value={form.commercial_type}
                onChange={(e) =>
                  setForm({
                    ...form,
                    commercial_type: e.target.value,
                    ...(e.target.value === "bumper" ? {} : { bumper_channel: "" }),
                  })
                }
              >
                <option value="">Unknown / not sure</option>
                {COMMERCIAL_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>

            {isBumperType(form.commercial_type) && (
              <div className="form-group">
                <label htmlFor="bulk-review-bumper">Channel *</label>
                <input
                  id="bulk-review-bumper"
                  required
                  value={form.bumper_channel}
                  onChange={(e) => setForm({ ...form, bumper_channel: e.target.value })}
                  placeholder="e.g. Cartoon Network, Nickelodeon"
                />
              </div>
            )}

            <div className="form-group">
              <label htmlFor="bulk-review-decade">Decade aired (rough estimate)</label>
              <select
                id="bulk-review-decade"
                value={form.decade}
                onChange={(e) => setForm({ ...form, decade: e.target.value })}
              >
                <option value="">Unknown / not sure</option>
                {COMMERCIAL_DECADES.map((d) => (
                  <option key={d} value={d}>
                    {d}s
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="bulk-review-year">Exact year (if known)</label>
              <input
                id="bulk-review-year"
                type="number"
                min={1900}
                max={2100}
                value={form.year}
                onChange={(e) => setForm({ ...form, year: e.target.value })}
                placeholder="e.g. 1997"
              />
            </div>

            <div className="form-group">
              <label htmlFor="bulk-review-language">Language</label>
              <input
                id="bulk-review-language"
                value={form.language}
                onChange={(e) => setForm({ ...form, language: e.target.value })}
                placeholder="en"
              />
            </div>

            <div className="form-group">
              <label htmlFor="region-select">Region</label>
              <RegionSelect value={regionSelection} onChange={setRegionSelection} />
            </div>
            {regionHasSubRegionPicker(regionSelection.region) && (
              <div className="form-group">
                <label htmlFor="sub-region-select">
                  {subRegionFieldLabel(regionSelection.region)}
                </label>
                <SubRegionSelect value={regionSelection} onChange={setRegionSelection} />
              </div>
            )}

            <div className="form-group">
              <label htmlFor="bulk-review-slogan">Slogan</label>
              <input
                id="bulk-review-slogan"
                value={form.slogan}
                onChange={(e) => setForm({ ...form, slogan: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label htmlFor="bulk-review-transcript">Transcript</label>
              <textarea
                id="bulk-review-transcript"
                value={form.transcript}
                onChange={(e) => setForm({ ...form, transcript: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label htmlFor="bulk-review-tags">Tags (comma-separated)</label>
              <input
                id="bulk-review-tags"
                value={form.tags}
                onChange={(e) => setForm({ ...form, tags: e.target.value })}
                placeholder="superbowl, automotive, humor"
              />
            </div>

            <SubmissionGenresFields value={genres} onChange={setGenres} />

            <div className="form-group">
              <label htmlFor="bulk-review-comment">Edit comment</label>
              <textarea
                id="bulk-review-comment"
                value={form.comment}
                onChange={(e) => setForm({ ...form, comment: e.target.value })}
                placeholder="Source, context, version label, or notes for voters…"
              />
            </div>

            <label
              style={{
                display: "flex",
                gap: "0.5rem",
                alignItems: "flex-start",
                marginBottom: "1rem",
              }}
            >
              <input
                type="checkbox"
                checked={termsAgreed}
                onChange={(e) => setTermsAgreed(e.target.checked)}
                style={{ marginTop: "0.25rem" }}
              />
              <span>
                I have read and agree to the <strong>Terms of Submission</strong>
                {terms ? ` (version ${terms.version})` : ""}.
              </span>
            </label>

            {error && <p className="error">{error}</p>}

            <div className="vote-buttons" style={{ marginBottom: "0.5rem" }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={busy || !termsAgreed || !form.commercial_title.trim()}
              >
                {busy ? "Submitting…" : "Submit for review"}
              </button>
              <button type="button" className="btn btn-secondary" onClick={onClose} disabled={busy}>
                Cancel
              </button>
              <Link
                to={item.youtube_url}
                target="_blank"
                rel="noreferrer"
                className="btn btn-secondary"
              >
                Open on YouTube
              </Link>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
