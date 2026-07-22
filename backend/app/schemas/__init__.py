from datetime import date, datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


CommercialTypeValue = Literal["general_ad", "psa", "service", "store", "bumper"]


def _normalize_bumper_fields(
    commercial_type: CommercialTypeValue | None,
    bumper_channel: str | None,
) -> tuple[CommercialTypeValue | None, str | None]:
    channel = (bumper_channel or "").strip() or None
    if commercial_type == "bumper":
        if not channel:
            raise ValueError("Channel is required when type is Bumper")
        return commercial_type, channel
    return commercial_type, None


# --- Auth ---


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=8)
    invite_code: str | None = Field(default=None, max_length=64)


class RegistrationSettingsPublic(BaseModel):
    invite_only: bool


class RegistrationInviteCreate(BaseModel):
    label: str | None = Field(default=None, max_length=255)
    max_uses: int = Field(default=1, ge=1, le=1000)
    expires_in_days: int | None = Field(default=30, ge=1, le=365)


class RegistrationInvitePublic(ORMModel):
    id: UUID
    code: str
    label: str | None = None
    max_uses: int
    use_count: int
    revoked_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime
    remaining_uses: int
    is_active: bool


class RegistrationInviteOnlyUpdate(BaseModel):
    invite_only: bool


class UserLogin(BaseModel):
    username: str
    password: str
    remember_me: bool = True


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10)
    password: str = Field(min_length=8)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=10)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class ChangeEmailRequest(BaseModel):
    password: str
    new_email: EmailStr


class AccountDeletionRequestCreate(BaseModel):
    password: str
    recipient_username: str | None = Field(default=None, max_length=64)


class AccountDeletionReview(BaseModel):
    review_notes: str | None = Field(default=None, max_length=2000)


class AccountDeletionRequestPublic(ORMModel):
    id: UUID
    status: str
    points_to_transfer: float = 0
    username: str | None = None
    recipient_username: str | None = None
    review_notes: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime


class MessageResponse(BaseModel):
    message: str


class UserPublic(ORMModel):
    id: UUID
    username: str
    email: EmailStr
    role: str
    access_level: str
    can_submit: bool
    email_verified: bool
    reputation_points: float = 0
    submit_slots_max: int = 1
    submit_slots_used: int = 0
    submit_slots_available: int = 1
    is_auto_editor: bool
    accepted_edits_count: int
    submission_terms_version: int | None = None
    submission_terms_accepted_at: datetime | None = None
    bulk_submit_enabled: bool = False
    can_bulk_submit: bool = False
    power_user_terms_version: int | None = None
    power_user_terms_accepted_at: datetime | None = None
    created_at: datetime


class UserProfilePublic(ORMModel):
    id: UUID
    username: str
    role: str
    reputation_points: float = 0
    accepted_edits_count: int = 0
    submission_count: int = 0
    is_power_user: bool = False
    created_at: datetime


class UserEditSummary(ORMModel):
    id: UUID
    edit_type: str
    status: str
    title: str
    entity_type: str
    entity_id: UUID | None
    comment: str | None
    created_at: datetime
    closed_at: datetime | None
    vote_count: int = 0


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: UUID | None = None


class QuizAnswerSubmit(BaseModel):
    answers: dict[str, int] = Field(min_length=1)


class QuizGradeResult(BaseModel):
    passed: bool
    score: int
    total: int
    access_level: str
    can_submit: bool


class SubmissionTermsSubsection(BaseModel):
    heading: str
    bullets: list[str] = Field(default_factory=list)
    paragraphs: list[str] = Field(default_factory=list)


class SubmissionTermsSection(BaseModel):
    number: int | None = None
    heading: str
    paragraphs: list[str] = Field(default_factory=list)
    bullet_label: str | None = None
    bullets: list[str] = Field(default_factory=list)
    subsections: list[SubmissionTermsSubsection] = Field(default_factory=list)


class SubmissionTermsPublic(BaseModel):
    version: int
    title: str
    intro: str
    sections: list[SubmissionTermsSection]
    quiz_required: bool = True


class PowerUserTermsPublic(BaseModel):
    version: int
    title: str
    intro: str
    sections: list[SubmissionTermsSection]
    accepted: bool = False


class PowerUserTermsAccept(BaseModel):
    agreed: bool = False


class BulkPlaylistImportRequest(BaseModel):
    playlist_url: str = Field(min_length=8, max_length=1024)


class BulkPlaylistCheckCounts(BaseModel):
    total: int = 0
    ok: int = 0
    catalog: int = 0
    queue: int = 0
    playlist_duplicate: int = 0


class BulkPlaylistCheckEntry(BaseModel):
    youtube_id: str
    youtube_url: str
    title: str | None = None
    position: int = 0
    status: str
    reason: str | None = None
    existing_video_sbid: str | None = None


class BulkPlaylistCheckPublic(BaseModel):
    playlist_id: str | None = None
    playlist_title: str | None = None
    playlist_url: str
    counts: BulkPlaylistCheckCounts
    entries: list[BulkPlaylistCheckEntry] = Field(default_factory=list)


class BulkSubmissionBatchPublic(ORMModel):
    id: UUID
    playlist_url: str
    playlist_id: str | None = None
    playlist_title: str | None = None
    status: str
    item_count: int = 0
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class BulkSubmissionItemPublic(ORMModel):
    id: UUID
    batch_id: UUID
    youtube_id: str
    youtube_url: str
    position: int = 0
    status: str
    title: str | None = None
    metadata: dict = Field(default_factory=dict)
    fingerprint_id: UUID | None = None
    edit_id: UUID | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


# --- Entities ---


class AdvertiserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    website: str | None = Field(default=None, max_length=512)
    country: str | None = Field(default=None, max_length=64)
    founded_year: int | None = Field(default=None, ge=1800, le=2100)
    industry: str | None = Field(default=None, max_length=128)
    headquarters: str | None = Field(default=None, max_length=255)
    parent_company: str | None = Field(default=None, max_length=255)
    wikipedia_url: str | None = Field(default=None, max_length=512)
    aliases: list[str] = Field(default_factory=list)
    tagline: str | None = Field(default=None, max_length=512)
    social: dict[str, str] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=4000)
    external_ids: dict = Field(default_factory=dict)


class AdvertiserMetadataUpdate(BaseModel):
    description: str | None = None
    website: str | None = Field(default=None, max_length=512)
    country: str | None = Field(default=None, max_length=64)
    founded_year: int | None = Field(default=None, ge=1800, le=2100)
    industry: str | None = Field(default=None, max_length=128)
    headquarters: str | None = Field(default=None, max_length=255)
    parent_company: str | None = Field(default=None, max_length=255)
    wikipedia_url: str | None = Field(default=None, max_length=512)
    aliases: list[str] = Field(default_factory=list)
    tagline: str | None = Field(default=None, max_length=512)
    social: dict[str, str] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=4000)


class AdvertiserPublic(ORMModel):
    sbid: UUID
    name: str
    slug: str
    description: str | None
    logo_url: str | None = None
    main_logo_id: UUID | None = None
    website: str | None = None
    country: str | None = None
    founded_year: int | None = None
    industry: str | None = None
    headquarters: str | None = None
    parent_company: str | None = None
    wikipedia_url: str | None = None
    metadata: dict = Field(default_factory=dict)
    external_ids: dict
    status: str
    created_at: datetime


class AgencyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    external_ids: dict = Field(default_factory=dict)


class AgencyPublic(ORMModel):
    sbid: UUID
    name: str
    slug: str
    description: str | None
    external_ids: dict
    created_at: datetime


class CommercialCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    advertiser_id: UUID | None = None
    advertiser_name: str | None = None
    store_id: UUID | None = None
    store_name: str | None = None
    service_id: UUID | None = None
    service_name: str | None = None
    event_id: UUID | None = None
    event_name: str | None = None
    holiday_id: UUID | None = None
    holiday_name: str | None = None
    agency_id: UUID | None = None
    agency_name: str | None = None
    year: int | None = Field(default=None, ge=1900, le=2100)
    decade: int | None = Field(default=None, ge=1900, le=2100)
    commercial_type: CommercialTypeValue | None = None
    bumper_channel: str | None = Field(default=None, max_length=255)
    campaign_name: str | None = None
    description: str | None = None
    external_ids: dict = Field(default_factory=dict)
    products: list[str] = Field(default_factory=list)

    @field_validator("decade")
    @classmethod
    def validate_decade(cls, value: int | None) -> int | None:
        if value is not None and value % 10 != 0:
            raise ValueError("Decade must be a multiple of 10 (e.g. 1990 for the 1990s)")
        return value

    @model_validator(mode="after")
    def validate_bumper_channel(self) -> Self:
        commercial_type, bumper_channel = _normalize_bumper_fields(
            self.commercial_type, self.bumper_channel
        )
        self.commercial_type = commercial_type
        self.bumper_channel = bumper_channel
        return self


class BulkItemSubmitRequest(BaseModel):
    commercial_id: UUID | None = None
    commercial: CommercialCreate | None = None
    thumbnail_url: str | None = None
    version_label: str | None = Field(default=None, max_length=255)
    channel_name: str | None = None
    upload_date: str | None = None
    duration_ms: int | None = None
    aspect_ratio: str | None = None
    resolution: str | None = None
    language: str | None = None
    region: str | None = None
    sub_region: str | None = None
    market: str | None = None
    first_aired_date: str | None = None
    last_aired_date: str | None = None
    network: str | None = None
    transcript: str | None = None
    slogan: str | None = None
    cta_text: str | None = None
    metadata: dict = Field(default_factory=dict)
    credits: list[dict] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    genres: dict | None = None
    comment: str | None = None
    force_votable: bool = False
    terms_agreed: bool = False


class CommercialPublic(ORMModel):
    sbid: UUID
    title: str
    advertiser_id: UUID | None
    store_id: UUID | None = None
    service_id: UUID | None = None
    event_id: UUID | None = None
    holiday_id: UUID | None = None
    agency_id: UUID | None
    year: int | None
    decade: int | None
    commercial_type: str | None = None
    bumper_channel: str | None = None
    campaign_name: str | None
    description: str | None
    external_ids: dict
    was_bulk_imported: bool | None = None
    created_at: datetime


class CommercialListItem(CommercialPublic):
    advertiser_name: str | None = None
    public_video_count: int = 0


class CommercialMetadataUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=512)
    year: int | None = Field(default=None, ge=1900, le=2100)
    decade: int | None = Field(default=None, ge=1900, le=2100)
    commercial_type: CommercialTypeValue | None = None
    bumper_channel: str | None = Field(default=None, max_length=255)
    campaign_name: str | None = Field(default=None, max_length=512)
    description: str | None = None
    products: list[str] = Field(default_factory=list)
    store_id: UUID | None = None
    service_id: UUID | None = None
    event_id: UUID | None = None
    holiday_id: UUID | None = None

    @field_validator("decade")
    @classmethod
    def validate_decade(cls, value: int | None) -> int | None:
        if value is not None and value % 10 != 0:
            raise ValueError("Decade must be a multiple of 10 (e.g. 1990 for the 1990s)")
        return value

    @model_validator(mode="after")
    def validate_bumper_channel(self) -> Self:
        commercial_type, bumper_channel = _normalize_bumper_fields(
            self.commercial_type, self.bumper_channel
        )
        self.commercial_type = commercial_type
        self.bumper_channel = bumper_channel
        return self


class CommercialSplitSubmit(CommercialMetadataUpdate):
    """Propose moving one video link into its own standalone commercial."""

    title: str = Field(..., min_length=1, max_length=512)
    comment: str | None = None
    terms_agreed: bool = False


class VideoCreditSchema(BaseModel):
    role: str
    name: str


class SubmissionGenres(BaseModel):
    age_range: str | None = Field(default=None, max_length=128)
    target_channel: str | None = Field(default=None, max_length=255)
    banned: bool = False
    adult_rated: bool = False
    late_night: bool = False
    spoof: bool = False
    fake: bool = False
    real: bool = False
    ai_enhanced: bool = False
    holiday: str | None = Field(default=None, max_length=255)
    event: str | None = Field(default=None, max_length=255)
    store: str | None = Field(default=None, max_length=255)
    service: str | None = Field(default=None, max_length=255)


class VideoCreate(BaseModel):
    commercial_id: UUID | None = None
    commercial: CommercialCreate | None = None
    youtube_url: str
    youtube_id: str | None = None
    thumbnail_url: str | None = None
    version_label: str | None = Field(default=None, max_length=255)
    channel_name: str | None = None
    upload_date: str | None = None
    duration_ms: int | None = None
    aspect_ratio: str | None = None
    resolution: str | None = None
    language: str | None = None
    region: str | None = None
    sub_region: str | None = None
    market: str | None = None
    first_aired_date: str | None = None
    last_aired_date: str | None = None
    network: str | None = None
    transcript: str | None = None
    slogan: str | None = None
    cta_text: str | None = None
    metadata: dict = Field(default_factory=dict)
    credits: list[VideoCreditSchema] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    genres: SubmissionGenres | None = None
    comment: str | None = None
    force_votable: bool = False
    terms_agreed: bool = False


class VideoPublic(ORMModel):
    sbid: UUID
    commercial_id: UUID
    youtube_id: str | None = None
    youtube_url: str | None = None
    thumbnail_url: str | None = None
    channel_name: str | None
    upload_date: str | None = None
    duration_ms: int | None
    aspect_ratio: str | None
    resolution: str | None
    language: str | None
    region: str | None
    sub_region: str | None
    market: str | None
    first_aired_date: str | None = None
    last_aired_date: str | None = None
    network: str | None
    transcript: str | None
    slogan: str | None
    cta_text: str | None
    version_label: str | None = None
    popularity_score: int = 0
    is_main: bool = False
    link_label: str | None = None
    viewer_vote: str | None = None
    metadata: dict
    visibility: str
    phash: str | None = None
    file_sha256: str | None = None
    audio_fingerprint: str | None = None
    hash_status: str | None = None
    hashed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class VideoDetail(VideoPublic):
    commercial: CommercialPublic | None = None
    advertiser: AdvertiserPublic | None = None
    agency: AgencyPublic | None = None
    credits: list[VideoCreditSchema] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class CommercialDetail(CommercialPublic):
    advertiser: AdvertiserPublic | None = None
    store: dict | None = None
    service: dict | None = None
    event: dict | None = None
    holiday: dict | None = None
    agency: AgencyPublic | None = None
    videos: list[VideoPublic] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)


class BrandAliasLink(BaseModel):
    name: str
    sbid: UUID | None = None


class AdvertiserDetail(AdvertiserPublic):
    commercials: list[CommercialPublic] = Field(default_factory=list)
    alias_links: list[BrandAliasLink] = Field(default_factory=list)


class AdvertiserLogoPublic(BaseModel):
    id: UUID
    advertiser_id: UUID
    image_url: str
    label: str | None = None
    year: int | None = None
    month: int | None = None
    event: str | None = None
    notes: str | None = None
    popularity_score: int = 0
    is_main: bool = False
    context_label: str
    created_at: datetime
    viewer_vote: str | None = None


class AdvertiserLogoPopularityVoteCreate(BaseModel):
    choice: str | None = Field(
        default=None,
        description='Use "up", "down", or null to clear your vote.',
    )

    @field_validator("choice")
    @classmethod
    def validate_choice(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in ("up", "down"):
            raise ValueError('choice must be "up", "down", or null')
        return normalized


class AdvertiserLogoMetadataUpdate(BaseModel):
    label: str | None = None
    year: int | None = Field(default=None, ge=1800, le=2100)
    month: int | None = Field(default=None, ge=1, le=12)
    event: str | None = None
    notes: str | None = None


class ApiTokenPublic(BaseModel):
    id: UUID
    token_prefix: str
    label: str | None
    scope: str
    created_at: datetime
    last_used_at: datetime | None


class ApiTokenCreate(BaseModel):
    label: str | None = Field(default=None, max_length=255)


class ApiTokenCreated(ApiTokenPublic):
    token: str


# --- Edits ---


class EditCreate(BaseModel):
    edit_type: str
    entity_type: str
    entity_id: UUID | None = None
    after_state: dict
    before_state: dict | None = None
    comment: str | None = None
    force_votable: bool = False


class VoteCreate(BaseModel):
    choice: str | None = Field(
        default=None,
        description='Use "yes", "no", "abstain", or null to remove your vote.',
    )
    comment: str | None = None

    @field_validator("choice")
    @classmethod
    def validate_choice(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in ("yes", "no", "abstain"):
            raise ValueError('choice must be "yes", "no", "abstain", or null')
        return normalized


class VotePublic(ORMModel):
    id: UUID
    voter_id: UUID
    choice: str
    comment: str | None
    created_at: datetime


class FingerprintPreviewPublic(BaseModel):
    status: str
    phash: str | None = None
    file_sha256: str | None = None
    audio_fingerprint: str | None = None
    duration_sec: float | None = None
    error_message: str | None = None
    probe: dict = Field(default_factory=dict)


class DuplicateMatchPublic(BaseModel):
    video_sbid: str
    youtube_id: str
    commercial_id: str | None = None
    match_type: str = "phash"
    phash: str | None = None
    file_sha256: str | None = None
    audio_fingerprint: str | None = None
    hamming_distance: int | None = None
    visibility: str | None = None


class HashLookupRequest(BaseModel):
    phash: str | None = Field(default=None, max_length=32)
    file_sha256: str | None = Field(default=None, max_length=128)
    audio_fingerprint: str | None = Field(default=None, max_length=200_000)
    threshold: int | None = Field(default=None, ge=0, le=64)


class HashTypesPublic(BaseModel):
    hash_types: list[str]
    phash_duplicate_threshold: int
    notes: dict[str, str] = Field(default_factory=dict)


class VideoHashesPublic(BaseModel):
    """All stored media hashes for a catalog video."""

    sbid: UUID
    youtube_id: str
    commercial_id: UUID
    phash: str | None = None
    file_sha256: str | None = None
    audio_fingerprint: str | None = None
    hash_status: str | None = None
    hashed_at: datetime | None = None
    visibility: str



class EditPublic(ORMModel):
    id: UUID
    edit_type: str
    status: str
    entity_type: str
    entity_id: UUID | None
    before_state: dict | None
    after_state: dict
    editor_id: UUID
    editor_username: str | None = None
    comment: str | None
    expires_at: datetime
    closed_at: datetime | None
    created_at: datetime
    votes: list[VotePublic] = Field(default_factory=list)
    fingerprint_preview: FingerprintPreviewPublic | None = None


# --- DMCA ---


class DMCASubmit(BaseModel):
    video_sbid: UUID
    claimant_name: str = Field(min_length=1, max_length=255)
    claimant_email: EmailStr
    claimant_address: str | None = None
    claim_text: str = Field(min_length=20)
    signature: str = Field(min_length=1, max_length=255)


class DMCACounterSubmit(BaseModel):
    counter_claim_text: str = Field(min_length=20)


class DMCAReview(BaseModel):
    status: str
    review_notes: str | None = None


class DMCAPublic(ORMModel):
    id: UUID
    video_id: UUID
    status: str
    claimant_name: str
    claimant_email: EmailStr
    claim_text: str
    review_notes: str | None
    created_at: datetime
    updated_at: datetime


# --- Search ---


class SearchResult(BaseModel):
    type: str
    sbid: UUID
    title: str
    subtitle: str | None = None


class PaginatedResponse(BaseModel):
    items: list
    total: int
    offset: int
    limit: int


# --- Admin ---


class AdminStats(BaseModel):
    users: int
    videos: int
    open_edits: int
    pending_fingerprints: int
    failed_fingerprints: int
    pending_video_hashes: int
    open_dmca: int


class AdminUserPublic(UserPublic):
    is_active: bool
    bulk_submit_revoked_at: datetime | None = None
    bulk_submit_revoke_reason: str | None = None


class AdminUserActiveUpdate(BaseModel):
    is_active: bool


class AdminBulkSubmitUpdate(BaseModel):
    enabled: bool
    revoke_reason: str | None = None


class ArchiveExportStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str = "idle"
    configured: bool = False
    started_at: str | None = None
    finished_at: str | None = None
    triggered_by: str | None = None
    stage: str | None = None
    export_id: str | None = None
    identifier: str | None = None
    item_url: str | None = None
    bundle_path: str | None = None
    video_count: int | None = None
    brand_count: int | None = None
    thumbnail_files: int | None = None
    logo_files: int | None = None
    youtube_thumbnails_fetched: int | None = None
    error: str | None = None


class YtdlpCookiesStatus(BaseModel):
    """Status of the admin-managed yt-dlp cookies file (never includes contents)."""

    present: bool = False
    path: str
    size_bytes: int = 0
    updated_at: str | None = None
    active: bool = False
    active_path: str | None = None
    env_override: bool = False
    browser_fallback: bool = False


class YtdlpCookiesUpdate(BaseModel):
    cookies: str = Field(..., min_length=1, max_length=2 * 1024 * 1024)


class ModStats(BaseModel):
    open_edits: int
    dmca_submitted: int
    dmca_under_review: int
    dmca_link_hidden: int
    pending_fingerprints: int
    failed_fingerprints: int
    pending_deletion_requests: int = 0
    dead_links: int = 0
    open_content_reports: int = 0
    # Alias kept for earlier commercial-report clients.
    open_commercial_reports: int = 0


class ContentReportSubmit(BaseModel):
    reason: str = Field(min_length=1, max_length=64)
    details: str | None = Field(default=None, max_length=2000)


class ContentReportReview(BaseModel):
    status: str = Field(min_length=1, max_length=32)
    review_notes: str | None = Field(default=None, max_length=2000)


class ContentReportPublic(ORMModel):
    id: UUID
    target_type: str
    commercial_id: UUID | None = None
    advertiser_id: UUID | None = None
    commercial_title: str | None = None
    advertiser_name: str | None = None
    target_title: str | None = None
    reporter_id: UUID
    reporter_username: str | None = None
    reason: str
    details: str | None = None
    status: str
    review_notes: str | None = None
    reviewed_by_id: UUID | None = None
    reviewed_by_username: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    outcome_hint: str | None = None


CommercialReportSubmit = ContentReportSubmit
CommercialReportReview = ContentReportReview
CommercialReportPublic = ContentReportPublic


class DeadLinkPublic(ORMModel):
    sbid: UUID
    youtube_id: str
    youtube_url: str
    commercial_id: UUID
    commercial_title: str | None = None
    commercial_sbid: UUID | None = None
    link_check_status: str | None = None
    link_checked_at: datetime | None = None
    link_check_detail: str | None = None
    link_flagged_at: datetime | None = None
    visibility: str


class LinkCheckRunResult(BaseModel):
    checked: int = 0
    ok: int = 0
    unavailable: int = 0
    private: int = 0
    age_restricted: int = 0
    error: int = 0
    flagged: int = 0
    queued: bool = False
    message: str | None = None


class YouTubeMetadataPreview(BaseModel):
    youtube_id: str
    youtube_url: str
    title: str | None = None
    channel_name: str | None = None
    upload_date: str | None = None
    duration_ms: int | None = None
    aspect_ratio: str | None = None
    resolution: str | None = None
    language: str | None = None
    tags: list[str] = Field(default_factory=list)
    transcript: str | None = None
    is_short: bool = False
    suggested_comment: str | None = None
    thumbnail_url: str | None = None
    metadata: dict = Field(default_factory=dict)
    existing_video_sbid: UUID | None = None


class FingerprintQueueItem(BaseModel):
    id: UUID
    youtube_id: str
    phase: str
    status: str
    edit_id: UUID | None = None
    video_id: UUID | None = None
    created_at: datetime
    started_at: datetime | None = None
    error_message: str | None = None
    queue_position: int | None = None


class FingerprintQueueStatus(BaseModel):
    pending_count: int
    processing_count: int
    redis_queue_depth: int
    processing: list[FingerprintQueueItem]
    pending: list[FingerprintQueueItem]


class AdminFingerprintPublic(BaseModel):
    id: UUID
    edit_id: UUID | None
    video_id: UUID | None
    youtube_id: str
    phase: str
    status: str
    phash: str | None = None
    file_sha256: str | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    @classmethod
    def from_row(cls, row) -> "AdminFingerprintPublic":
        from app.services.fingerprint_queries import format_phash_hex

        return cls(
            id=row.id,
            edit_id=row.edit_id,
            video_id=row.video_id,
            youtube_id=row.youtube_id,
            phase=row.phase.value,
            status=row.status.value,
            phash=format_phash_hex(row.phash),
            file_sha256=row.file_sha256,
            error_message=row.error_message,
            created_at=row.created_at,
            completed_at=row.completed_at,
        )


# --- Catalog entities (Store / Service / Event / Holiday) ---


class CatalogEntityPublic(ORMModel):
    sbid: UUID
    name: str
    slug: str
    description: str | None = None
    logo_url: str | None = None
    main_logo_id: UUID | None = None
    website: str | None = None
    country: str | None = None
    wikipedia_url: str | None = None
    metadata: dict = Field(default_factory=dict)
    external_ids: dict = Field(default_factory=dict)
    status: str
    created_at: datetime
    # Store / Service
    founded_year: int | None = None
    store_type: str | None = None
    service_type: str | None = None
    headquarters: str | None = None
    parent_company: str | None = None
    # Event
    location: str | None = None
    start_year: int | None = None
    end_year: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    # Holiday
    date_text: str | None = None
    year: int | None = None
    month: int | None = None
    day: int | None = None


class CatalogEntityDetail(CatalogEntityPublic):
    commercials: list[CommercialPublic] = Field(default_factory=list)
    alias_links: list[BrandAliasLink] = Field(default_factory=list)


class CatalogMetadataUpdate(BaseModel):
    description: str | None = None
    website: str | None = Field(default=None, max_length=512)
    country: str | None = Field(default=None, max_length=64)
    founded_year: int | None = Field(default=None, ge=1800, le=2100)
    store_type: str | None = Field(default=None, max_length=128)
    service_type: str | None = Field(default=None, max_length=128)
    headquarters: str | None = Field(default=None, max_length=255)
    parent_company: str | None = Field(default=None, max_length=255)
    wikipedia_url: str | None = Field(default=None, max_length=512)
    location: str | None = Field(default=None, max_length=255)
    start_year: int | None = Field(default=None, ge=1800, le=2200)
    end_year: int | None = Field(default=None, ge=1800, le=2200)
    start_date: date | None = None
    end_date: date | None = None
    date_text: str | None = Field(default=None, max_length=255)
    year: int | None = Field(default=None, ge=1800, le=2200)
    month: int | None = Field(default=None, ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=31)
    aliases: list[str] = Field(default_factory=list)
    tagline: str | None = Field(default=None, max_length=512)
    social: dict[str, str] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=4000)


class CatalogLogoPublic(BaseModel):
    id: UUID
    image_url: str
    label: str | None = None
    year: int | None = None
    month: int | None = None
    event: str | None = None
    notes: str | None = None
    popularity_score: int = 0
    is_main: bool = False
    context_label: str
    created_at: datetime
    viewer_vote: str | None = None
    store_id: UUID | None = None
    service_id: UUID | None = None
    event_id: UUID | None = None
    holiday_id: UUID | None = None


class CatalogLogoMetadataUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=255)
    year: int | None = Field(default=None, ge=1800, le=2100)
    month: int | None = Field(default=None, ge=1, le=12)
    event: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=4000)
