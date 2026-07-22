const API_BASE = "/api/v1";

export interface User {
  id: string;
  username: string;
  email: string;
  role: string;
  access_level: string;
  can_submit: boolean;
  email_verified: boolean;
  reputation_points: number;
  submit_slots_max: number;
  submit_slots_used: number;
  submit_slots_available: number;
  is_auto_editor: boolean;
  accepted_edits_count: number;
  submission_terms_version: number | null;
  submission_terms_accepted_at: string | null;
  bulk_submit_enabled?: boolean;
  can_bulk_submit?: boolean;
  power_user_terms_version?: number | null;
  power_user_terms_accepted_at?: string | null;
  created_at: string;
}

export interface ApiToken {
  id: string;
  token_prefix: string;
  label: string | null;
  scope: string;
  created_at: string;
  last_used_at: string | null;
}

export interface ApiTokenCreated extends ApiToken {
  token: string;
}

export interface SubmissionTermsSubsection {
  heading: string;
  bullets?: string[];
  paragraphs?: string[];
}

export interface SubmissionTermsSection {
  number?: number;
  heading: string;
  paragraphs?: string[];
  bullet_label?: string;
  bullets?: string[];
  subsections?: SubmissionTermsSubsection[];
}

export interface SubmissionTerms {
  version: number;
  title: string;
  intro: string;
  sections: SubmissionTermsSection[];
}

export interface PowerUserTerms {
  version: number;
  title: string;
  intro: string;
  sections: SubmissionTermsSection[];
  accepted: boolean;
}

export interface BulkSubmissionBatch {
  id: string;
  playlist_url: string;
  playlist_id?: string | null;
  playlist_title?: string | null;
  status: string;
  item_count: number;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface BulkSubmissionItem {
  id: string;
  batch_id: string;
  youtube_id: string;
  youtube_url: string;
  position: number;
  status: string;
  title?: string | null;
  metadata?: Record<string, unknown>;
  fingerprint_id?: string | null;
  edit_id?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface BulkPlaylistCheckCounts {
  total: number;
  ok: number;
  catalog: number;
  queue: number;
  playlist_duplicate: number;
}

export interface BulkPlaylistCheckEntry {
  youtube_id: string;
  youtube_url: string;
  title?: string | null;
  position: number;
  status: string;
  reason?: string | null;
  existing_video_sbid?: string | null;
}

export interface BulkPlaylistCheck {
  playlist_id?: string | null;
  playlist_title?: string | null;
  playlist_url: string;
  counts: BulkPlaylistCheckCounts;
  entries: BulkPlaylistCheckEntry[];
}

export interface QuizQuestion {
  id: string;
  prompt: string;
  options: string[];
}

export interface Video {
  sbid: string;
  commercial_id: string;
  youtube_id: string | null;
  youtube_url: string | null;
  thumbnail_url?: string | null;
  channel_name: string | null;
  duration_ms: number | null;
  language: string | null;
  region: string | null;
  sub_region: string | null;
  transcript: string | null;
  slogan: string | null;
  version_label?: string | null;
  link_label?: string | null;
  popularity_score?: number;
  is_main?: boolean;
  viewer_vote?: "up" | "down" | null;
  commercial_title?: string | null;
  commercial_type?: "general_ad" | "psa" | "service" | "store" | "bumper" | null;
  bumper_channel?: string | null;
  visibility: string;
  phash?: string | null;
  file_sha256?: string | null;
  audio_fingerprint?: string | null;
  hash_status?: string | null;
  hashed_at?: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
  commercial?: { sbid: string; title: string };
  advertiser?: { sbid: string; name: string };
  tags?: string[];
  credits?: { role: string; name: string }[];
}

export interface BrowseSection {
  id: string;
  title: string;
  kind: "videos" | "edits";
  total: number;
  items: Video[] | Edit[];
  see_all_path?: string | null;
}

export interface BrowseHome {
  sections: BrowseSection[];
}

export interface FingerprintPreview {
  status: string;
  phash?: string | null;
  file_sha256?: string | null;
  audio_fingerprint?: string | null;
  duration_sec?: number | null;
  error_message?: string | null;
  probe?: Record<string, unknown>;
}

export interface DuplicateMatch {
  video_sbid: string;
  youtube_id: string;
  commercial_id?: string | null;
  match_type?: string;
  phash?: string | null;
  file_sha256?: string | null;
  audio_fingerprint?: string | null;
  hamming_distance?: number | null;
  visibility?: string | null;
}

export interface HashTypesInfo {
  hash_types: string[];
  phash_duplicate_threshold: number;
  notes: Record<string, string>;
}

export interface HashLookupParams {
  phash?: string;
  file_sha256?: string;
  audio_fingerprint?: string;
  threshold?: number;
}

export interface VideoHashes {
  sbid: string;
  youtube_id: string;
  commercial_id: string;
  phash?: string | null;
  file_sha256?: string | null;
  audio_fingerprint?: string | null;
  hash_status?: string | null;
  hashed_at?: string | null;
  visibility: string;
}

export interface ModStats {
  open_edits: number;
  dmca_submitted: number;
  dmca_under_review: number;
  dmca_link_hidden: number;
  pending_fingerprints: number;
  failed_fingerprints: number;
  pending_deletion_requests: number;
  dead_links: number;
  open_content_reports?: number;
  open_commercial_reports?: number;
}

export interface ContentReport {
  id: string;
  target_type: string;
  commercial_id?: string | null;
  advertiser_id?: string | null;
  commercial_title?: string | null;
  advertiser_name?: string | null;
  target_title?: string | null;
  reporter_id: string;
  reporter_username?: string | null;
  reason: string;
  details?: string | null;
  status: string;
  review_notes?: string | null;
  reviewed_by_id?: string | null;
  reviewed_by_username?: string | null;
  reviewed_at?: string | null;
  created_at: string;
  updated_at: string;
  outcome_hint?: string | null;
}

/** @deprecated Prefer ContentReport */
export type CommercialReport = ContentReport;

export interface DeadLink {
  sbid: string;
  youtube_id: string;
  youtube_url: string;
  commercial_id: string;
  commercial_title?: string | null;
  commercial_sbid?: string | null;
  link_check_status?: string | null;
  link_checked_at?: string | null;
  link_check_detail?: string | null;
  link_flagged_at?: string | null;
  visibility: string;
}

export interface LinkCheckRunResult {
  checked: number;
  ok: number;
  unavailable: number;
  private: number;
  age_restricted: number;
  error: number;
  flagged: number;
  queued: boolean;
  message?: string | null;
}

export interface AccountDeletionRequest {
  id: string;
  status: string;
  points_to_transfer: number;
  username?: string | null;
  recipient_username?: string | null;
  review_notes?: string | null;
  reviewed_at?: string | null;
  created_at: string;
}

export interface DmcaItem {
  id: string;
  video_id: string;
  status: string;
  claimant_name: string;
  claimant_email: string;
  claim_text: string;
  review_notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminStats {
  users: number;
  videos: number;
  open_edits: number;
  pending_fingerprints: number;
  failed_fingerprints: number;
  pending_video_hashes: number;
  open_dmca: number;
}

export interface AdminUser extends User {
  is_active: boolean;
  bulk_submit_revoked_at?: string | null;
  bulk_submit_revoke_reason?: string | null;
}

export interface AdminFingerprint {
  id: string;
  edit_id: string | null;
  video_id: string | null;
  youtube_id: string;
  phase: string;
  status: string;
  phash?: string | null;
  file_sha256?: string | null;
  error_message?: string | null;
  created_at: string;
  completed_at?: string | null;
}

export interface FingerprintQueueItem {
  id: string;
  youtube_id: string;
  phase: string;
  status: string;
  edit_id?: string | null;
  video_id?: string | null;
  created_at: string;
  started_at?: string | null;
  error_message?: string | null;
  queue_position?: number | null;
}

export interface FingerprintQueueStatus {
  pending_count: number;
  processing_count: number;
  redis_queue_depth: number;
  processing: FingerprintQueueItem[];
  pending: FingerprintQueueItem[];
}

export interface RegistrationSettings {
  invite_only: boolean;
}

export interface RegistrationInvite {
  id: string;
  code: string;
  label?: string | null;
  max_uses: number;
  use_count: number;
  revoked_at?: string | null;
  expires_at?: string | null;
  created_at: string;
  remaining_uses: number;
  is_active: boolean;
}

export interface ArchiveExportStatus {
  status: string;
  configured: boolean;
  started_at?: string | null;
  finished_at?: string | null;
  triggered_by?: string | null;
  stage?: string | null;
  export_id?: string | null;
  identifier?: string | null;
  item_url?: string | null;
  bundle_path?: string | null;
  video_count?: number | null;
  brand_count?: number | null;
  thumbnail_files?: number | null;
  logo_files?: number | null;
  youtube_thumbnails_fetched?: number | null;
  error?: string | null;
}

export interface Edit {
  id: string;
  edit_type: string;
  status: string;
  entity_type: string;
  entity_id: string | null;
  before_state?: Record<string, unknown> | null;
  after_state: Record<string, unknown>;
  editor_id: string;
  editor_username?: string | null;
  comment: string | null;
  expires_at: string;
  created_at: string;
  votes: { id: string; voter_id: string; choice: string; comment: string | null }[];
  fingerprint_preview?: FingerprintPreview | null;
}

export interface UserProfile {
  id: string;
  username: string;
  role: string;
  reputation_points: number;
  accepted_edits_count: number;
  submission_count: number;
  is_power_user?: boolean;
  created_at: string;
}

export interface UserEditSummary {
  id: string;
  edit_type: string;
  status: string;
  title: string;
  entity_type: string;
  entity_id: string | null;
  comment: string | null;
  created_at: string;
  closed_at: string | null;
  vote_count: number;
}

export interface SearchResult {
  type: string;
  sbid: string;
  title: string;
  subtitle: string | null;
}

export interface AdvertiserMetadataUpdate {
  description?: string | null;
  website?: string | null;
  country?: string | null;
  founded_year?: number | null;
  industry?: string | null;
  headquarters?: string | null;
  parent_company?: string | null;
  wikipedia_url?: string | null;
  aliases?: string[];
  tagline?: string | null;
  social?: Record<string, string>;
  notes?: string | null;
}

export interface CommercialListItem {
  sbid: string;
  title: string;
  advertiser_id: string | null;
  agency_id: string | null;
  year: number | null;
  decade: number | null;
  commercial_type?: "general_ad" | "psa" | "service" | "store" | "bumper" | null;
  bumper_channel?: string | null;
  campaign_name: string | null;
  description: string | null;
  created_at: string;
  advertiser_name?: string | null;
  public_video_count?: number;
  was_bulk_imported?: boolean | null;
}

export interface CatalogRef {
  sbid: string;
  name: string;
}

export interface CommercialDetail {
  sbid: string;
  title: string;
  description?: string | null;
  year?: number | null;
  decade?: number | null;
  commercial_type?: "general_ad" | "psa" | "service" | "store" | "bumper" | null;
  bumper_channel?: string | null;
  campaign_name?: string | null;
  advertiser_id?: string | null;
  store_id?: string | null;
  service_id?: string | null;
  event_id?: string | null;
  holiday_id?: string | null;
  agency_id?: string | null;
  external_ids?: Record<string, unknown>;
  created_at?: string;
  products?: string[];
  advertiser?: CatalogRef | null;
  store?: CatalogRef | null;
  service?: CatalogRef | null;
  event?: CatalogRef | null;
  holiday?: CatalogRef | null;
  agency?: { sbid: string; name: string; slug?: string } | null;
  videos?: Video[];
  was_bulk_imported?: boolean | null;
}

export interface CatalogEntity {
  sbid: string;
  name: string;
  slug: string;
  description: string | null;
  logo_url?: string | null;
  main_logo_id?: string | null;
  website?: string | null;
  country?: string | null;
  wikipedia_url?: string | null;
  metadata?: {
    aliases?: string[];
    tagline?: string | null;
    social?: Record<string, string>;
    notes?: string | null;
  };
  external_ids?: Record<string, unknown>;
  status?: string;
  created_at: string;
  founded_year?: number | null;
  store_type?: string | null;
  service_type?: string | null;
  headquarters?: string | null;
  parent_company?: string | null;
  location?: string | null;
  start_year?: number | null;
  end_year?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  date_text?: string | null;
  year?: number | null;
  month?: number | null;
  day?: number | null;
  commercials?: { sbid: string; title: string }[];
  alias_links?: BrandAliasLink[];
}

export type CatalogMetadataUpdate = Record<string, unknown>;

export interface CatalogLogo {
  id: string;
  image_url: string;
  label: string | null;
  year: number | null;
  month: number | null;
  event: string | null;
  notes: string | null;
  popularity_score: number;
  is_main: boolean;
  context_label: string;
  created_at: string;
  viewer_vote: "up" | "down" | null;
  store_id?: string | null;
  service_id?: string | null;
  event_id?: string | null;
  holiday_id?: string | null;
}

export interface CatalogLogoSubmit {
  label?: string;
  year?: number;
  month?: number;
  event?: string;
  notes?: string;
  comment?: string;
}

export type CatalogLogoMetadataUpdate = Omit<CatalogLogoSubmit, "comment">;

export interface BrandAliasLink {
  name: string;
  sbid: string | null;
}

export interface Advertiser {
  sbid: string;
  name: string;
  slug: string;
  description: string | null;
  logo_url?: string | null;
  main_logo_id?: string | null;
  website?: string | null;
  country?: string | null;
  founded_year?: number | null;
  industry?: string | null;
  headquarters?: string | null;
  parent_company?: string | null;
  wikipedia_url?: string | null;
  metadata?: {
    aliases?: string[];
    tagline?: string | null;
    social?: Record<string, string>;
    notes?: string | null;
  };
  external_ids: Record<string, unknown>;
  status?: string;
  created_at: string;
  commercials?: { sbid: string; title: string }[];
  alias_links?: BrandAliasLink[];
}

export interface AdvertiserLogo {
  id: string;
  advertiser_id: string;
  image_url: string;
  label: string | null;
  year: number | null;
  month: number | null;
  event: string | null;
  notes: string | null;
  popularity_score: number;
  is_main: boolean;
  context_label: string;
  created_at: string;
  viewer_vote: "up" | "down" | null;
}

export interface AdvertiserLogoSubmit {
  label?: string;
  year?: number;
  month?: number;
  event?: string;
  notes?: string;
  comment?: string;
}

export type AdvertiserLogoMetadataUpdate = Omit<AdvertiserLogoSubmit, "comment">;

export interface Paginated<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}

export interface YouTubeMetadataPreview {
  youtube_id: string;
  youtube_url: string;
  title: string | null;
  channel_name: string | null;
  upload_date: string | null;
  duration_ms: number | null;
  aspect_ratio: string | null;
  resolution: string | null;
  language: string | null;
  tags: string[];
  transcript: string | null;
  is_short: boolean;
  suggested_comment: string | null;
  thumbnail_url: string | null;
  metadata: Record<string, unknown>;
  existing_video_sbid: string | null;
}

const TOKEN_KEY = "commercialbrainz_token";

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY) ?? localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null, persist = true) {
  sessionStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(TOKEN_KEY);
  if (!token) return;
  if (persist) localStorage.setItem(TOKEN_KEY, token);
  else sessionStorage.setItem(TOKEN_KEY, token);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "User-Agent": "CommercialBrainz-Web/0.1.0 (https://commercialbrainz.org)",
    ...(options.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  registrationSettings: () => request<RegistrationSettings>("/auth/registration-settings"),

  register: (data: { username: string; email: string; password: string; invite_code?: string }) =>
    request<User>("/auth/register", { method: "POST", body: JSON.stringify(data) }),

  login: (data: { username: string; password: string; remember_me?: boolean }) =>
    request<{ access_token: string }>("/auth/login", { method: "POST", body: JSON.stringify(data) }),

  forgotPassword: (email: string) =>
    request<{ message: string }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  resetPassword: (token: string, password: string) =>
    request<{ message: string }>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    }),

  verifyEmail: (token: string) =>
    request<{ message: string }>("/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),

  resendVerification: () =>
    request<{ message: string }>("/auth/resend-verification", { method: "POST" }),

  me: () => request<User>("/auth/me"),

  listApiTokens: () => request<ApiToken[]>("/auth/api-tokens"),

  createApiToken: (label?: string) =>
    request<ApiTokenCreated>("/auth/api-tokens", {
      method: "POST",
      body: JSON.stringify({ label: label ?? null }),
    }),

  revokeApiToken: (tokenId: string) =>
    request<{ message: string }>(`/auth/api-tokens/${tokenId}`, { method: "DELETE" }),

  changePassword: (data: { current_password: string; new_password: string }) =>
    request<{ message: string }>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  changeEmail: (data: { password: string; new_email: string }) =>
    request<User>("/auth/change-email", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getDeletionRequest: () => request<AccountDeletionRequest | null>("/auth/deletion-request"),

  requestAccountDeletion: (data: { password: string; recipient_username?: string }) =>
    request<AccountDeletionRequest>("/auth/deletion-request", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  cancelDeletionRequest: () =>
    request<{ message: string }>("/auth/deletion-request/cancel", { method: "POST" }),

  getSubmissionTerms: () => request<SubmissionTerms>("/auth/submission-terms"),

  acceptSubmissionTerms: () => request<User>("/auth/submission-terms/accept", { method: "POST" }),

  getSubmissionQuiz: () =>
    request<{ questions: QuizQuestion[]; pass_score: number }>("/auth/submission-quiz"),

  submitSubmissionQuiz: (answers: Record<string, number>) =>
    request<{ passed: boolean; score: number; total: number; can_submit: boolean }>(
      "/auth/submission-upgrade",
      { method: "POST", body: JSON.stringify({ answers }) }
    ),

  search: (query: string, type = "all") =>
    request<SearchResult[]>(`/search?query=${encodeURIComponent(query)}&type=${type}`),

  searchAdvertisers: (query: string) => api.search(query, "advertiser"),

  listAdvertisers: (q = "", offset = 0, limit = 50) =>
    request<Paginated<Advertiser>>(
      `/advertisers?q=${encodeURIComponent(q)}&offset=${offset}&limit=${limit}`
    ),

  listCommercials: (q = "", offset = 0, limit = 50) =>
    request<Paginated<CommercialListItem>>(
      `/commercials?q=${encodeURIComponent(q)}&offset=${offset}&limit=${limit}`
    ),

  browseSections: (perSection = 16) =>
    request<BrowseHome>(`/browse/sections?per_section=${perSection}`),

  browseVideos: (
    offset = 0,
    limit = 25,
    opts: {
      commercial_type?: string;
      channel_commercials?: boolean;
      sort?: "created_at" | "updated_at";
      updated_only?: boolean;
      main_only?: boolean;
      advertiser?: string;
      tag?: string;
    } = {}
  ) => {
    const qs = new URLSearchParams({
      offset: String(offset),
      limit: String(limit),
    });
    if (opts.commercial_type) qs.set("commercial_type", opts.commercial_type);
    if (opts.channel_commercials) qs.set("channel_commercials", "true");
    if (opts.sort) qs.set("sort", opts.sort);
    if (opts.updated_only) qs.set("updated_only", "true");
    if (opts.main_only) qs.set("main_only", "true");
    if (opts.advertiser) qs.set("advertiser", opts.advertiser);
    if (opts.tag) qs.set("tag", opts.tag);
    return request<Paginated<Video>>(`/browse/videos?${qs.toString()}`);
  },

  getVideo: (sbid: string) => request<Video>(`/videos/${sbid}`),

  getCommercial: (sbid: string) => request<CommercialDetail>(`/commercials/${sbid}`),

  reportCommercial: (sbid: string, data: { reason: string; details?: string }) =>
    request<ContentReport>(`/commercials/${sbid}/report`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  reportBrand: (sbid: string, data: { reason: string; details?: string }) =>
    request<ContentReport>(`/advertisers/${sbid}/report`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getCommercialVideos: (sbid: string) => request<Video[]>(`/commercials/${sbid}/videos`),

  voteCommercialVideoPopularity: (
    commercialSbid: string,
    videoSbid: string,
    choice: "up" | "down" | null
  ) =>
    request<Video>(`/commercials/${commercialSbid}/videos/${videoSbid}/popularity-vote`, {
      method: "POST",
      body: JSON.stringify({ choice }),
    }),

  getAdvertiser: (sbid: string) => request<Advertiser>(`/advertisers/${sbid}`),

  submitVideo: (data: Record<string, unknown> & { terms_agreed?: boolean }) =>
    request<Edit>("/edits/submit-video", { method: "POST", body: JSON.stringify(data) }),

  submitVideoThumbnail: (sbid: string, file: File, comment?: string) => {
    const body = new FormData();
    body.append("file", file);
    if (comment?.trim()) body.append("comment", comment.trim());
    return request<Edit>(`/videos/${sbid}/submit-thumbnail`, { method: "POST", body });
  },

  submitAdvertiserLogo: (sbid: string, file: File, meta: AdvertiserLogoSubmit = {}) => {
    const body = new FormData();
    body.append("file", file);
    if (meta.label) body.append("label", meta.label);
    if (meta.year != null) body.append("year", String(meta.year));
    if (meta.month != null) body.append("month", String(meta.month));
    if (meta.event) body.append("event", meta.event);
    if (meta.notes) body.append("notes", meta.notes);
    if (meta.comment?.trim()) body.append("comment", meta.comment.trim());
    return request<Edit>(`/advertisers/${sbid}/submit-logo`, { method: "POST", body });
  },

  getAdvertiserLogos: (sbid: string) =>
    request<AdvertiserLogo[]>(`/advertisers/${sbid}/logos`),

  voteAdvertiserLogoPopularity: (
    sbid: string,
    logoId: string,
    choice: "up" | "down" | null
  ) =>
    request<AdvertiserLogo>(`/advertisers/${sbid}/logos/${logoId}/popularity-vote`, {
      method: "POST",
      body: JSON.stringify({ choice }),
    }),

  submitAdvertiserLogoMetadata: (
    sbid: string,
    logoId: string,
    data: AdvertiserLogoMetadataUpdate
  ) =>
    request<Edit>(`/advertisers/${sbid}/logos/${logoId}/submit-metadata`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  submitAdvertiserMetadata: (sbid: string, data: AdvertiserMetadataUpdate) =>
    request<Edit>(`/advertisers/${sbid}/submit-metadata`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  searchCatalog: (kind: "store" | "service" | "event" | "holiday", query: string) =>
    api.search(query, kind),

  listCatalog: (
    kind: "store" | "service" | "event" | "holiday",
    q = "",
    offset = 0,
    limit = 50
  ) => {
    const plural =
      kind === "store"
        ? "stores"
        : kind === "service"
          ? "services"
          : kind === "event"
            ? "events"
            : "holidays";
    return request<Paginated<CatalogEntity>>(
      `/${plural}?q=${encodeURIComponent(q)}&offset=${offset}&limit=${limit}`
    );
  },

  getCatalog: (kind: "store" | "service" | "event" | "holiday", sbid: string) => {
    const plural =
      kind === "store"
        ? "stores"
        : kind === "service"
          ? "services"
          : kind === "event"
            ? "events"
            : "holidays";
    return request<CatalogEntity>(`/${plural}/${sbid}`);
  },

  submitCatalogMetadata: (
    kind: "store" | "service" | "event" | "holiday",
    sbid: string,
    data: CatalogMetadataUpdate
  ) => {
    const plural =
      kind === "store"
        ? "stores"
        : kind === "service"
          ? "services"
          : kind === "event"
            ? "events"
            : "holidays";
    return request<Edit>(`/${plural}/${sbid}/submit-metadata`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  submitCatalogLogo: (
    kind: "store" | "service" | "event" | "holiday",
    sbid: string,
    file: File,
    meta: CatalogLogoSubmit = {}
  ) => {
    const plural =
      kind === "store"
        ? "stores"
        : kind === "service"
          ? "services"
          : kind === "event"
            ? "events"
            : "holidays";
    const body = new FormData();
    body.append("file", file);
    if (meta.label) body.append("label", meta.label);
    if (meta.year != null) body.append("year", String(meta.year));
    if (meta.month != null) body.append("month", String(meta.month));
    if (meta.event) body.append("event", meta.event);
    if (meta.notes) body.append("notes", meta.notes);
    if (meta.comment?.trim()) body.append("comment", meta.comment.trim());
    return request<Edit>(`/${plural}/${sbid}/submit-logo`, { method: "POST", body });
  },

  getCatalogLogos: (kind: "store" | "service" | "event" | "holiday", sbid: string) => {
    const plural =
      kind === "store"
        ? "stores"
        : kind === "service"
          ? "services"
          : kind === "event"
            ? "events"
            : "holidays";
    return request<CatalogLogo[]>(`/${plural}/${sbid}/logos`);
  },

  voteCatalogLogoPopularity: (
    kind: "store" | "service" | "event" | "holiday",
    sbid: string,
    logoId: string,
    choice: "up" | "down" | null
  ) => {
    const plural =
      kind === "store"
        ? "stores"
        : kind === "service"
          ? "services"
          : kind === "event"
            ? "events"
            : "holidays";
    return request<CatalogLogo>(`/${plural}/${sbid}/logos/${logoId}/popularity-vote`, {
      method: "POST",
      body: JSON.stringify({ choice }),
    });
  },

  submitCatalogLogoMetadata: (
    kind: "store" | "service" | "event" | "holiday",
    sbid: string,
    logoId: string,
    data: CatalogLogoMetadataUpdate
  ) => {
    const plural =
      kind === "store"
        ? "stores"
        : kind === "service"
          ? "services"
          : kind === "event"
            ? "events"
            : "holidays";
    return request<Edit>(`/${plural}/${sbid}/logos/${logoId}/submit-metadata`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  submitCommercialMetadata: (
    sbid: string,
    data: {
      title?: string | null;
      year?: number | null;
      decade?: number | null;
      commercial_type?: "general_ad" | "psa" | "service" | "store" | "bumper" | null;
      bumper_channel?: string | null;
      campaign_name?: string | null;
      description?: string | null;
      products?: string[];
      store_id?: string | null;
      service_id?: string | null;
      event_id?: string | null;
      holiday_id?: string | null;
    }
  ) =>
    request<Edit>(`/commercials/${sbid}/submit-metadata`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  submitCommercialSplit: (
    commercialSbid: string,
    videoSbid: string,
    data: {
      title: string;
      year?: number | null;
      decade?: number | null;
      commercial_type?: "general_ad" | "psa" | "service" | "store" | "bumper" | null;
      bumper_channel?: string | null;
      campaign_name?: string | null;
      description?: string | null;
      products?: string[];
      comment?: string;
      terms_agreed?: boolean;
    }
  ) =>
    request<Edit>(`/commercials/${commercialSbid}/videos/${videoSbid}/submit-split`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  fetchYouTubeMetadata: (url: string) =>
    request<YouTubeMetadataPreview>(
      `/edits/youtube-metadata?url=${encodeURIComponent(url)}`
    ),

  openEdits: (offset = 0, limit = 25) =>
    request<Paginated<Edit>>(`/edits/open?offset=${offset}&limit=${limit}`),

  getUserProfile: (username: string) =>
    request<UserProfile>(`/users/${encodeURIComponent(username)}`),

  getUserEdits: (username: string, offset = 0, limit = 25) =>
    request<Paginated<UserEditSummary>>(
      `/users/${encodeURIComponent(username)}/edits?offset=${offset}&limit=${limit}`
    ),

  getEdit: (id: string) => request<Edit>(`/edits/${id}`),

  getEditDuplicates: (id: string) => request<DuplicateMatch[]>(`/edits/${id}/duplicates`),

  hashTypes: () => request<HashTypesInfo>("/hashes/types"),

  listHashes: (offset = 0, limit = 50, hashedOnly = false) =>
    request<Paginated<VideoHashes>>(
      `/hashes?offset=${offset}&limit=${limit}${hashedOnly ? "&hashed_only=true" : ""}`
    ),

  getVideoHashes: (sbid: string) => request<VideoHashes>(`/hashes/videos/${sbid}`),

  getHashesByYoutubeId: (youtubeId: string) =>
    request<VideoHashes>(`/hashes/youtube/${encodeURIComponent(youtubeId)}`),

  lookupHash: (params: HashLookupParams) => {
    const qs = new URLSearchParams();
    if (params.phash) qs.set("phash", params.phash);
    if (params.file_sha256) qs.set("file_sha256", params.file_sha256);
    if (params.audio_fingerprint) qs.set("audio_fingerprint", params.audio_fingerprint);
    if (params.threshold != null) qs.set("threshold", String(params.threshold));
    // Long Chromaprint strings should use POST.
    if (params.audio_fingerprint && params.audio_fingerprint.length > 2000) {
      return request<DuplicateMatch[]>("/hashes/lookup", {
        method: "POST",
        body: JSON.stringify(params),
      });
    }
    return request<DuplicateMatch[]>(`/hashes/lookup?${qs.toString()}`);
  },

  lookupHashPost: (params: HashLookupParams) =>
    request<DuplicateMatch[]>("/hashes/lookup", {
      method: "POST",
      body: JSON.stringify(params),
    }),

  vote: (editId: string, choice: string | null, comment?: string) =>
    request<unknown>(`/edits/${editId}/vote`, {
      method: "POST",
      body: JSON.stringify({ choice, comment }),
    }),

  submitDmca: (data: Record<string, unknown>) =>
    request<unknown>("/dmca", { method: "POST", body: JSON.stringify(data) }),

  dmcaQueue: (status?: string) =>
    request<Paginated<DmcaItem>>(
      `/dmca/queue${status ? `?status=${status}` : ""}`
    ),

  reviewDmca: (id: string, status: string, review_notes?: string) =>
    request<unknown>(`/dmca/${id}/review`, {
      method: "POST",
      body: JSON.stringify({ status, review_notes }),
    }),

  setUserRole: (userId: string, role: string) =>
    request<User>(`/admin/users/${userId}/role/${role}`, { method: "POST" }),

  adminStats: () =>
    request<AdminStats>("/admin/stats"),

  adminUsers: (q?: string, offset = 0) =>
    request<Paginated<AdminUser>>(
      `/admin/users?offset=${offset}${q ? `&q=${encodeURIComponent(q)}` : ""}`
    ),

  adminSetUserRole: (userId: string, role: string) =>
    request<AdminUser>(`/admin/users/${userId}/role/${role}`, { method: "POST" }),

  adminSetUserAccess: (userId: string, access: string) =>
    request<AdminUser>(`/admin/users/${userId}/access/${access}`, { method: "POST" }),

  adminSetUserActive: (userId: string, isActive: boolean) =>
    request<AdminUser>(`/admin/users/${userId}/active`, {
      method: "POST",
      body: JSON.stringify({ is_active: isActive }),
    }),

  adminSetUserBulkSubmit: (userId: string, enabled: boolean, revokeReason?: string) =>
    request<AdminUser>(`/admin/users/${userId}/bulk-submit`, {
      method: "POST",
      body: JSON.stringify({
        enabled,
        revoke_reason: revokeReason ?? null,
      }),
    }),

  adminFingerprints: (status?: string, offset = 0) =>
    request<Paginated<AdminFingerprint>>(
      `/admin/fingerprints?offset=${offset}${status ? `&status=${status}` : ""}`
    ),

  adminFingerprintQueue: () => request<FingerprintQueueStatus>("/admin/fingerprint-queue"),

  adminRetryFingerprint: (id: string) =>
    request<{ status: string }>(`/admin/fingerprints/${id}/retry`, { method: "POST" }),

  adminArchiveExportStatus: () =>
    request<ArchiveExportStatus>("/admin/exports/archive-org/status"),

  adminTriggerArchiveExport: () =>
    request<{ status: string }>("/admin/exports/archive-org/trigger", { method: "POST" }),

  adminRegistrationSettings: () =>
    request<RegistrationSettings>("/admin/registration-settings"),

  adminSetRegistrationSettings: (inviteOnly: boolean) =>
    request<RegistrationSettings>("/admin/registration-settings", {
      method: "POST",
      body: JSON.stringify({ invite_only: inviteOnly }),
    }),

  adminInvites: () => request<Paginated<RegistrationInvite>>("/admin/invites"),

  adminCreateInvite: (data: { label?: string; max_uses?: number; expires_in_days?: number | null }) =>
    request<RegistrationInvite>("/admin/invites", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  adminRevokeInvite: (inviteId: string) =>
    request<RegistrationInvite>(`/admin/invites/${inviteId}/revoke`, { method: "POST" }),

  modStats: () => request<ModStats>("/mod/stats"),

  modFingerprintQueue: () => request<FingerprintQueueStatus>("/mod/fingerprint-queue"),

  modApplyEdit: (editId: string) =>
    request<Edit>(`/mod/edits/${editId}/apply`, { method: "POST" }),

  modRejectEdit: (editId: string) =>
    request<Edit>(`/mod/edits/${editId}/reject`, { method: "POST" }),

  modDeletionRequests: () => request<AccountDeletionRequest[]>("/mod/deletion-requests"),

  modApproveDeletion: (requestId: string, reviewNotes?: string) =>
    request<AccountDeletionRequest>(`/mod/deletion-requests/${requestId}/approve`, {
      method: "POST",
      body: JSON.stringify({ review_notes: reviewNotes ?? null }),
    }),

  modRejectDeletion: (requestId: string, reviewNotes?: string) =>
    request<AccountDeletionRequest>(`/mod/deletion-requests/${requestId}/reject`, {
      method: "POST",
      body: JSON.stringify({ review_notes: reviewNotes ?? null }),
    }),

  modDeadLinks: (offset = 0, limit = 50) =>
    request<DeadLink[]>(`/mod/dead-links?offset=${offset}&limit=${limit}`),

  modTriggerDeadLinkCheck: (limit?: number) =>
    request<LinkCheckRunResult>(
      `/mod/dead-links/check${limit != null ? `?limit=${limit}` : ""}`,
      { method: "POST" }
    ),

  modDismissDeadLink: (videoId: string) =>
    request<DeadLink>(`/mod/dead-links/${videoId}/dismiss`, { method: "POST" }),

  modRecheckDeadLink: (videoId: string) =>
    request<DeadLink>(`/mod/dead-links/${videoId}/recheck`, { method: "POST" }),

  bulkSubmitTerms: () => request<PowerUserTerms>("/bulk-submit/terms"),

  bulkSubmitAcceptTerms: (agreed: boolean) =>
    request<PowerUserTerms>("/bulk-submit/terms/accept", {
      method: "POST",
      body: JSON.stringify({ agreed }),
    }),

  bulkSubmitCheckPlaylist: (playlistUrl: string) =>
    request<BulkPlaylistCheck>("/bulk-submit/playlists/check", {
      method: "POST",
      body: JSON.stringify({ playlist_url: playlistUrl }),
    }),

  bulkSubmitPlaylist: (playlistUrl: string) =>
    request<BulkSubmissionBatch>("/bulk-submit/playlists", {
      method: "POST",
      body: JSON.stringify({ playlist_url: playlistUrl }),
    }),

  bulkSubmitBatches: () => request<BulkSubmissionBatch[]>("/bulk-submit/batches"),

  bulkSubmitItems: (status?: string) =>
    request<BulkSubmissionItem[]>(
      `/bulk-submit/items${status ? `?status=${encodeURIComponent(status)}` : ""}`
    ),

  bulkSubmitItem: (itemId: string) =>
    request<BulkSubmissionItem>(`/bulk-submit/items/${itemId}`),

  bulkSubmitItemSubmit: (itemId: string, data: Record<string, unknown>) =>
    request<Edit>(`/bulk-submit/items/${itemId}/submit`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  bulkSubmitItemSkip: (itemId: string) =>
    request<BulkSubmissionItem>(`/bulk-submit/items/${itemId}/skip`, { method: "POST" }),

  bulkSubmitItemRehash: (itemId: string) =>
    request<BulkSubmissionItem>(`/bulk-submit/items/${itemId}/rehash`, { method: "POST" }),

  modContentReports: () => request<ContentReport[]>("/mod/content-reports"),

  modCommercialReports: () => request<ContentReport[]>("/mod/content-reports"),

  modReviewContentReport: (reportId: string, status: string, reviewNotes?: string) =>
    request<ContentReport>(`/mod/content-reports/${reportId}/review`, {
      method: "POST",
      body: JSON.stringify({ status, review_notes: reviewNotes ?? null }),
    }),

  modReviewCommercialReport: (reportId: string, status: string, reviewNotes?: string) =>
    request<ContentReport>(`/mod/content-reports/${reportId}/review`, {
      method: "POST",
      body: JSON.stringify({ status, review_notes: reviewNotes ?? null }),
    }),
};
