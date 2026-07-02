from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


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
    created_at: datetime


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
    agency_id: UUID | None = None
    agency_name: str | None = None
    year: int | None = Field(default=None, ge=1900, le=2100)
    decade: int | None = Field(default=None, ge=1900, le=2100)
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


class CommercialPublic(ORMModel):
    sbid: UUID
    title: str
    advertiser_id: UUID | None
    agency_id: UUID | None
    year: int | None
    decade: int | None
    campaign_name: str | None
    description: str | None
    external_ids: dict
    created_at: datetime


class VideoCreditSchema(BaseModel):
    role: str
    name: str


class VideoCreate(BaseModel):
    commercial_id: UUID | None = None
    commercial: CommercialCreate | None = None
    youtube_url: str
    youtube_id: str | None = None
    thumbnail_url: str | None = None
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
    agency: AgencyPublic | None = None
    videos: list[VideoPublic] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)


class AdvertiserDetail(AdvertiserPublic):
    commercials: list[CommercialPublic] = Field(default_factory=list)


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
    choice: str
    comment: str | None = None


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
    phash: str | None = None
    hamming_distance: int


class EditPublic(ORMModel):
    id: UUID
    edit_type: str
    status: str
    entity_type: str
    entity_id: UUID | None
    before_state: dict | None
    after_state: dict
    editor_id: UUID
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


class AdminUserActiveUpdate(BaseModel):
    is_active: bool


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


class ModStats(BaseModel):
    open_edits: int
    dmca_submitted: int
    dmca_under_review: int
    dmca_link_hidden: int
    pending_fingerprints: int
    failed_fingerprints: int


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
