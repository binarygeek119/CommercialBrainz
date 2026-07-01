from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth ---


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    username: str
    password: str


class UserPublic(ORMModel):
    id: UUID
    username: str
    email: EmailStr
    role: str
    access_level: str
    can_submit: bool
    is_auto_editor: bool
    accepted_edits_count: int
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


class SubmissionTermsPublic(BaseModel):
    title: str
    sections: list[dict]
    quiz_required: bool = True


# --- Entities ---


class AdvertiserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    external_ids: dict = Field(default_factory=dict)


class AdvertiserPublic(ORMModel):
    sbid: UUID
    name: str
    slug: str
    description: str | None
    external_ids: dict
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
    year: int | None = None
    campaign_name: str | None = None
    description: str | None = None
    external_ids: dict = Field(default_factory=dict)
    products: list[str] = Field(default_factory=list)


class CommercialPublic(ORMModel):
    sbid: UUID
    title: str
    advertiser_id: UUID | None
    agency_id: UUID | None
    year: int | None
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
    channel_name: str | None = None
    upload_date: str | None = None
    duration_ms: int | None = None
    aspect_ratio: str | None = None
    resolution: str | None = None
    language: str | None = None
    region: str | None = None
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


class VideoPublic(ORMModel):
    sbid: UUID
    commercial_id: UUID
    youtube_id: str | None = None
    youtube_url: str | None = None
    channel_name: str | None
    upload_date: str | None = None
    duration_ms: int | None
    aspect_ratio: str | None
    resolution: str | None
    language: str | None
    region: str | None
    market: str | None
    first_aired_date: str | None = None
    last_aired_date: str | None = None
    network: str | None
    transcript: str | None
    slogan: str | None
    cta_text: str | None
    metadata: dict
    visibility: str
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
