import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type BulkPlaylistCheck, type BulkPlaylistDefaults } from "../api";
import { useAuth } from "../auth";
import AdvertiserPicker, { type AdvertiserSelection } from "../components/AdvertiserPicker";
import {
  RegionSelect,
  SubRegionSelect,
  regionHasSubRegionPicker,
  regionSelectionToPayload,
  subRegionFieldLabel,
  type RegionSelection,
} from "../components/RegionPicker";
import { COMMERCIAL_DECADES } from "../utils/commercialPeriod";
import { COMMERCIAL_TYPES, isBumperType } from "../utils/commercialTypes";

function duplicateReasonLabel(reason: string | null | undefined): string {
  switch (reason) {
    case "catalog":
      return "Already in catalog";
    case "queue":
      return "Already in your review queue";
    case "playlist_duplicate":
      return "Duplicate entry in this playlist";
    default:
      return "Duplicate link";
  }
}

function buildDefaultsPayload(
  commercialType: string,
  bumperChannel: string,
  decade: string,
  year: string,
  advertiser: AdvertiserSelection,
  language: string,
  regionSelection: RegionSelection,
  tags: string,
  slogan: string,
  campaignName: string
): BulkPlaylistDefaults | null {
  const tagsList = tags
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
  const regionPayload = regionSelectionToPayload(regionSelection);
  const payload: BulkPlaylistDefaults = {
    ...(commercialType ? { commercial_type: commercialType } : {}),
    ...(isBumperType(commercialType) && bumperChannel.trim()
      ? { bumper_channel: bumperChannel.trim() }
      : {}),
    ...(decade ? { decade: parseInt(decade, 10) } : {}),
    ...(year ? { year: parseInt(year, 10) } : {}),
    ...(advertiser.advertiser_id
      ? { advertiser_id: advertiser.advertiser_id }
      : advertiser.advertiser_name
        ? { advertiser_name: advertiser.advertiser_name }
        : {}),
    ...(language.trim() ? { language: language.trim() } : {}),
    ...(regionPayload.region ? { region: regionPayload.region } : {}),
    ...(regionPayload.sub_region ? { sub_region: regionPayload.sub_region } : {}),
    ...(tagsList.length ? { tags: tagsList } : {}),
    ...(slogan.trim() ? { slogan: slogan.trim() } : {}),
    ...(campaignName.trim() ? { campaign_name: campaignName.trim() } : {}),
  };
  return Object.keys(payload).length ? payload : null;
}

export default function BulkSubmitPage() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [playlistUrl, setPlaylistUrl] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [check, setCheck] = useState<BulkPlaylistCheck | null>(null);

  const [commercialType, setCommercialType] = useState("");
  const [bumperChannel, setBumperChannel] = useState("");
  const [decade, setDecade] = useState("");
  const [year, setYear] = useState("");
  const [advertiser, setAdvertiser] = useState<AdvertiserSelection>({});
  const [language, setLanguage] = useState("");
  const [regionSelection, setRegionSelection] = useState<RegionSelection>({});
  const [tags, setTags] = useState("");
  const [slogan, setSlogan] = useState("");
  const [campaignName, setCampaignName] = useState("");

  const needsTerms = Boolean(user?.bulk_submit_enabled) && !user?.can_bulk_submit;

  const defaultsPreview = useMemo(
    () =>
      buildDefaultsPayload(
        commercialType,
        bumperChannel,
        decade,
        year,
        advertiser,
        language,
        regionSelection,
        tags,
        slogan,
        campaignName
      ),
    [
      commercialType,
      bumperChannel,
      decade,
      year,
      advertiser,
      language,
      regionSelection,
      tags,
      slogan,
      campaignName,
    ]
  );

  const { data: terms, isLoading: termsLoading } = useQuery({
    queryKey: ["bulk-submit-terms"],
    queryFn: () => api.bulkSubmitTerms(),
    enabled: needsTerms,
  });

  const handleAcceptTerms = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.bulkSubmitAcceptTerms(agreed);
      await refresh();
      queryClient.invalidateQueries({ queryKey: ["bulk-submit-terms"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to accept terms");
    } finally {
      setBusy(false);
    }
  };

  const handleCheck = async () => {
    setBusy(true);
    setError(null);
    setCheck(null);
    try {
      const result = await api.bulkSubmitCheckPlaylist(playlistUrl.trim());
      setCheck(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Duplicate check failed");
    } finally {
      setBusy(false);
    }
  };

  const handleImport = async () => {
    if (!check || check.counts.ok < 1) return;
    if (isBumperType(commercialType) && !bumperChannel.trim()) {
      setError("Channel is required when commercial type is Bumper.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.bulkSubmitPlaylist(check.playlist_url, defaultsPreview);
      setPlaylistUrl("");
      setCheck(null);
      navigate("/submit/bulk/queue");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(false);
    }
  };

  if (needsTerms) {
    if (termsLoading) return <p className="muted">Loading…</p>;
    if (!terms) return <p className="muted">Unable to load terms.</p>;
    return (
      <div>
        <h1 className="page-title">{terms.title}</h1>
        <p>{terms.intro}</p>
        <div className="stack" style={{ marginTop: "1rem" }}>
          {terms.sections.map((section) => (
            <div key={section.heading} className="card">
              <h3>
                {section.number != null ? `${section.number}. ` : ""}
                {section.heading}
              </h3>
              {section.paragraphs?.map((p) => (
                <p key={p}>{p}</p>
              ))}
              {section.bullet_label && <p>{section.bullet_label}</p>}
              {section.bullets && section.bullets.length > 0 && (
                <ul>
                  {section.bullets.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
        <label style={{ display: "flex", gap: "0.5rem", marginTop: "1rem", alignItems: "flex-start" }}>
          <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
          <span>I agree to the Power User Terms and will personally QC each bulk item.</span>
        </label>
        {error && <p className="error">{error}</p>}
        <button
          type="button"
          className="btn btn-primary"
          style={{ marginTop: "1rem" }}
          disabled={!agreed || busy}
          onClick={() => void handleAcceptTerms()}
        >
          {busy ? "Saving…" : "Accept and continue"}
        </button>
      </div>
    );
  }

  const duplicates = check?.entries.filter((e) => e.status === "duplicate") ?? [];
  const importable = check?.counts.ok ?? 0;

  return (
    <div>
      <div className="flex-between" style={{ marginBottom: "1rem" }}>
        <h1 className="page-title" style={{ margin: 0 }}>
          Playlist import
        </h1>
        <Link to="/submit/bulk/queue" className="btn btn-secondary">
          Review queue
        </Link>
      </div>
      <p className="muted">
        Paste a YouTube playlist URL, optionally set shared commercial defaults for every video,
        check duplicates, then import. Defaults prefill the review form; YouTube metadata still
        loads per video before editing.
      </p>

      <div className="card" style={{ marginTop: "1rem" }}>
        <label htmlFor="playlist-url">Playlist URL</label>
        <input
          id="playlist-url"
          value={playlistUrl}
          onChange={(e) => {
            setPlaylistUrl(e.target.value);
            setCheck(null);
          }}
          placeholder="https://www.youtube.com/playlist?list=…"
          style={{ width: "100%" }}
        />
      </div>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h2 style={{ marginTop: 0, fontSize: "1.1rem" }}>Shared defaults (optional)</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          Applied to every video from this playlist when you review/submit. Leave blank to fill
          per video.
        </p>

        <div className="form-group">
          <label htmlFor="bulk-default-type">Commercial type</label>
          <select
            id="bulk-default-type"
            value={commercialType}
            onChange={(e) => {
              setCommercialType(e.target.value);
              if (e.target.value !== "bumper") setBumperChannel("");
            }}
          >
            <option value="">Unknown / not sure</option>
            {COMMERCIAL_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        {isBumperType(commercialType) && (
          <div className="form-group">
            <label htmlFor="bulk-default-bumper">Channel *</label>
            <input
              id="bulk-default-bumper"
              value={bumperChannel}
              onChange={(e) => setBumperChannel(e.target.value)}
              placeholder="e.g. Cartoon Network, Nickelodeon"
            />
          </div>
        )}

        <div className="form-group">
          <label>Advertiser / Brand</label>
          <AdvertiserPicker value={advertiser} onChange={setAdvertiser} />
        </div>

        <div className="form-group">
          <label htmlFor="bulk-default-decade">Decade aired</label>
          <select
            id="bulk-default-decade"
            value={decade}
            onChange={(e) => setDecade(e.target.value)}
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
          <label htmlFor="bulk-default-year">Exact year (if known)</label>
          <input
            id="bulk-default-year"
            type="number"
            min={1900}
            max={2100}
            value={year}
            onChange={(e) => setYear(e.target.value)}
            placeholder="e.g. 1997"
          />
        </div>

        <div className="form-group">
          <label htmlFor="bulk-default-language">Language</label>
          <input
            id="bulk-default-language"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            placeholder="en"
          />
        </div>

        <div className="form-group">
          <label htmlFor="region-select">Region</label>
          <RegionSelect value={regionSelection} onChange={setRegionSelection} />
        </div>
        {regionHasSubRegionPicker(regionSelection.region) && (
          <div className="form-group">
            <label htmlFor="sub-region-select">{subRegionFieldLabel(regionSelection.region)}</label>
            <SubRegionSelect value={regionSelection} onChange={setRegionSelection} />
          </div>
        )}

        <div className="form-group">
          <label htmlFor="bulk-default-campaign">Campaign name</label>
          <input
            id="bulk-default-campaign"
            value={campaignName}
            onChange={(e) => setCampaignName(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label htmlFor="bulk-default-slogan">Slogan</label>
          <input
            id="bulk-default-slogan"
            value={slogan}
            onChange={(e) => setSlogan(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label htmlFor="bulk-default-tags">Tags (comma-separated)</label>
          <input
            id="bulk-default-tags"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="superbowl, automotive, humor"
          />
        </div>
      </div>

      <div className="card" style={{ marginTop: "1rem" }}>
        {error && <p className="error">{error}</p>}
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!playlistUrl.trim() || busy}
            onClick={() => void handleCheck()}
          >
            {busy && !check ? "Checking…" : "Check duplicates"}
          </button>
          {check && (
            <button
              type="button"
              className="btn btn-secondary"
              disabled={
                importable < 1 ||
                busy ||
                (isBumperType(commercialType) && !bumperChannel.trim())
              }
              onClick={() => void handleImport()}
            >
              {busy && check
                ? "Starting…"
                : `Import ${importable} video${importable === 1 ? "" : "s"}`}
            </button>
          )}
        </div>
      </div>

      {check && (
        <div className="card" style={{ marginTop: "1rem" }}>
          <h2 style={{ marginTop: 0, fontSize: "1.1rem" }}>
            {check.playlist_title || "Playlist check"}
          </h2>
          <p className="muted" style={{ marginBottom: "0.75rem" }}>
            {check.counts.total} link{check.counts.total === 1 ? "" : "s"} found · {importable}{" "}
            importable
            {check.counts.catalog > 0 ? ` · ${check.counts.catalog} already in catalog` : ""}
            {check.counts.queue > 0 ? ` · ${check.counts.queue} already in queue` : ""}
            {check.counts.playlist_duplicate > 0
              ? ` · ${check.counts.playlist_duplicate} playlist duplicate${
                  check.counts.playlist_duplicate === 1 ? "" : "s"
                }`
              : ""}
            {` · stages ${check.staging_window ?? 10} at a time`}
          </p>
          {defaultsPreview && (
            <p className="muted" style={{ marginBottom: "0.75rem" }}>
              Shared defaults will be saved with this import
              {defaultsPreview.commercial_type
                ? ` (type: ${defaultsPreview.commercial_type})`
                : ""}
              .
            </p>
          )}
          {importable > 0 && (
            <p className="muted" style={{ marginBottom: "0.75rem" }}>
              Import stores all {importable} link{importable === 1 ? "" : "s"}, then hashes the first{" "}
              {Math.min(importable, check.staging_window ?? 10)} for review.
            </p>
          )}
          {importable < 1 && (
            <p className="error">Nothing new to import — every link is a duplicate.</p>
          )}
          {duplicates.length > 0 && (
            <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
              {duplicates.map((entry) => (
                <li key={`${entry.youtube_id}-${entry.position}`}>
                  {entry.title || entry.youtube_id}
                  <span className="muted"> — {duplicateReasonLabel(entry.reason)}</span>
                </li>
              ))}
            </ul>
          )}
          {duplicates.length === 0 && importable > 0 && (
            <p className="muted">No duplicate links. Ready to import.</p>
          )}
        </div>
      )}
    </div>
  );
}
