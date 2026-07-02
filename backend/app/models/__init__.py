import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def pg_enum(enum_cls: type[enum.Enum], *, name: str) -> Enum:
    """Map Python enums to existing PostgreSQL ENUM types by value, not member name."""
    return Enum(enum_cls, name=name, values_callable=lambda x: [e.value for e in x])


class UserRole(str, enum.Enum):
    USER = "user"
    MOD = "mod"
    ADMIN = "admin"


class UserAccess(str, enum.Enum):
    VOTE_ONLY = "vote_only"
    SUBMIT_AND_VOTE = "submit_and_vote"


class VideoVisibility(str, enum.Enum):
    PUBLIC = "public"
    DMCA_HIDDEN = "dmca_hidden"
    REMOVED = "removed"


class EditType(str, enum.Enum):
    CREATE_VIDEO = "create_video"
    EDIT_VIDEO = "edit_video"
    CREATE_COMMERCIAL = "create_commercial"
    EDIT_COMMERCIAL = "edit_commercial"
    MERGE_COMMERCIAL = "merge_commercial"
    CREATE_ADVERTISER = "create_advertiser"
    EDIT_ADVERTISER = "edit_advertiser"
    ADD_ADVERTISER_LOGO = "add_advertiser_logo"
    EDIT_ADVERTISER_LOGO = "edit_advertiser_logo"
    REMOVE_VIDEO = "remove_video"
    ADD_CREDIT = "add_credit"
    ADD_TAG = "add_tag"


class AdvertiserStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class LogoPopularityChoice(str, enum.Enum):
    UP = "up"
    DOWN = "down"


class EditStatus(str, enum.Enum):
    OPEN = "open"
    APPLIED = "applied"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    FAILED = "failed"
    AUTOMATICALLY_APPLIED = "automatically_applied"


class VoteChoice(str, enum.Enum):
    YES = "yes"
    NO = "no"
    ABSTAIN = "abstain"


class DMCAStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    LINK_HIDDEN = "link_hidden"
    REJECTED = "rejected"
    RESTORED = "restored"
    PERMANENTLY_REMOVED = "permanently_removed"


class FingerprintPhase(str, enum.Enum):
    PREVIEW = "preview"
    FINAL = "final"


class FingerprintStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoHashStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ReputationCategory(str, enum.Enum):
    APPROVAL = "approval"
    LIKE = "like"
    QUALITY = "quality"
    VERSION = "version"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, name="userrole"), default=UserRole.USER)
    access_level: Mapped[UserAccess] = mapped_column(
        pg_enum(UserAccess, name="useraccess"), default=UserAccess.VOTE_ONLY
    )
    submission_terms_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_auto_editor: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_edits_count: Mapped[int] = mapped_column(Integer, default=0)
    reputation_points: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    edits: Mapped[list["Edit"]] = relationship(back_populates="editor")
    votes: Mapped[list["Vote"]] = relationship(back_populates="voter")
    reputation_events: Mapped[list["ReputationEvent"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    email_verification_tokens: Mapped[list["EmailVerificationToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    registration_invites_created: Mapped[list["RegistrationInvite"]] = relationship(
        back_populates="created_by", foreign_keys="RegistrationInvite.created_by_id"
    )


class SiteSetting(Base):
    __tablename__ = "site_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RegistrationInvite(Base):
    __tablename__ = "registration_invites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    created_by: Mapped["User | None"] = relationship(
        back_populates="registration_invites_created", foreign_keys=[created_by_id]
    )


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="email_verification_tokens")


class ReputationEvent(Base):
    __tablename__ = "reputation_events"
    __table_args__ = (UniqueConstraint("edit_id", "category", name="uq_reputation_events_edit_category"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    edit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("edits.id", ondelete="CASCADE"))
    category: Mapped[ReputationCategory] = mapped_column(
        pg_enum(ReputationCategory, name="reputationcategory")
    )
    points: Mapped[float] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="reputation_events")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="password_reset_tokens")


class Advertiser(Base):
    __tablename__ = "advertisers"

    sbid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    logo_url: Mapped[str | None] = mapped_column(String(512))
    main_logo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("advertiser_logos.id", ondelete="SET NULL"), nullable=True
    )
    website: Mapped[str | None] = mapped_column(String(512))
    country: Mapped[str | None] = mapped_column(String(64))
    founded_year: Mapped[int | None] = mapped_column(Integer)
    industry: Mapped[str | None] = mapped_column(String(128))
    headquarters: Mapped[str | None] = mapped_column(String(255))
    parent_company: Mapped[str | None] = mapped_column(String(255))
    wikipedia_url: Mapped[str | None] = mapped_column(String(512))
    external_ids: Mapped[dict] = mapped_column(JSONB, default=dict)
    extra_data: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    status: Mapped[AdvertiserStatus] = mapped_column(
        pg_enum(AdvertiserStatus, name="advertiserstatus"),
        default=AdvertiserStatus.APPROVED,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    commercials: Mapped[list["Commercial"]] = relationship(back_populates="advertiser")
    logos: Mapped[list["AdvertiserLogo"]] = relationship(
        back_populates="advertiser",
        foreign_keys="AdvertiserLogo.advertiser_id",
        cascade="all, delete-orphan",
    )
    main_logo: Mapped["AdvertiserLogo | None"] = relationship(
        foreign_keys=[main_logo_id],
        post_update=True,
    )


class AdvertiserLogo(Base):
    __tablename__ = "advertiser_logos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    advertiser_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("advertisers.sbid", ondelete="CASCADE"), index=True
    )
    image_url: Mapped[str] = mapped_column(String(512))
    label: Mapped[str | None] = mapped_column(String(255))
    year: Mapped[int | None] = mapped_column(Integer)
    month: Mapped[int | None] = mapped_column(Integer)
    event: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    edit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("edits.id", ondelete="SET NULL"), nullable=True
    )
    popularity_score: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    advertiser: Mapped["Advertiser"] = relationship(
        back_populates="logos", foreign_keys=[advertiser_id]
    )
    submitter: Mapped["User | None"] = relationship(foreign_keys=[submitted_by])
    popularity_votes: Mapped[list["AdvertiserLogoVote"]] = relationship(
        back_populates="logo", cascade="all, delete-orphan"
    )


class AdvertiserLogoVote(Base):
    __tablename__ = "advertiser_logo_votes"
    __table_args__ = (UniqueConstraint("logo_id", "voter_id", name="uq_logo_voter"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    logo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("advertiser_logos.id", ondelete="CASCADE"), index=True
    )
    voter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    choice: Mapped[LogoPopularityChoice] = mapped_column(
        pg_enum(LogoPopularityChoice, name="logopopularitychoice")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    logo: Mapped["AdvertiserLogo"] = relationship(back_populates="popularity_votes")
    voter: Mapped["User"] = relationship()


class Agency(Base):
    __tablename__ = "agencies"

    sbid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    external_ids: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    commercials: Mapped[list["Commercial"]] = relationship(back_populates="agency")


class Commercial(Base):
    __tablename__ = "commercials"

    sbid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(512), index=True)
    advertiser_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("advertisers.sbid"), index=True
    )
    agency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agencies.sbid"), index=True
    )
    year: Mapped[int | None] = mapped_column(Integer)
    decade: Mapped[int | None] = mapped_column(Integer)
    campaign_name: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    external_ids: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    advertiser: Mapped["Advertiser | None"] = relationship(back_populates="commercials")
    agency: Mapped["Agency | None"] = relationship(back_populates="commercials")
    videos: Mapped[list["Video"]] = relationship(back_populates="commercial")
    products: Mapped[list["CommercialProduct"]] = relationship(back_populates="commercial")


class CommercialProduct(Base):
    __tablename__ = "commercial_products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    commercial_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commercials.sbid", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(512))

    commercial: Mapped["Commercial"] = relationship(back_populates="products")


class Video(Base):
    __tablename__ = "videos"

    sbid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    commercial_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commercials.sbid"), index=True
    )
    youtube_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    youtube_url: Mapped[str] = mapped_column(String(512))
    thumbnail_url: Mapped[str | None] = mapped_column(String(512))
    channel_name: Mapped[str | None] = mapped_column(String(255))
    upload_date: Mapped[date | None] = mapped_column(Date)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    aspect_ratio: Mapped[str | None] = mapped_column(String(16))
    resolution: Mapped[str | None] = mapped_column(String(32))
    language: Mapped[str | None] = mapped_column(String(16))
    region: Mapped[str | None] = mapped_column(String(64))
    sub_region: Mapped[str | None] = mapped_column(String(64))
    market: Mapped[str | None] = mapped_column(String(64))
    first_aired_date: Mapped[date | None] = mapped_column(Date)
    last_aired_date: Mapped[date | None] = mapped_column(Date)
    network: Mapped[str | None] = mapped_column(String(128))
    transcript: Mapped[str | None] = mapped_column(Text)
    slogan: Mapped[str | None] = mapped_column(String(512))
    cta_text: Mapped[str | None] = mapped_column(String(512))
    extra_data: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    visibility: Mapped[VideoVisibility] = mapped_column(
        pg_enum(VideoVisibility, name="videovisibility"), default=VideoVisibility.PUBLIC
    )
    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    phash: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    audio_fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)
    hash_status: Mapped[VideoHashStatus] = mapped_column(
        pg_enum(VideoHashStatus, name="videohashstatus"), default=VideoHashStatus.PENDING
    )
    hashed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    commercial: Mapped["Commercial"] = relationship(back_populates="videos")
    submitted_by: Mapped["User | None"] = relationship()
    credits: Mapped[list["VideoCredit"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    tags: Mapped[list["VideoTag"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    airings: Mapped[list["Airing"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    dmca_takedowns: Mapped[list["DMCATakedown"]] = relationship(back_populates="video")


class VideoCredit(Base):
    __tablename__ = "video_credits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.sbid", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(255))

    video: Mapped["Video"] = relationship(back_populates="credits")


class VideoTag(Base):
    __tablename__ = "video_tags"
    __table_args__ = (UniqueConstraint("video_id", "tag", name="uq_video_tag"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.sbid", ondelete="CASCADE"), index=True
    )
    tag: Mapped[str] = mapped_column(String(128), index=True)

    video: Mapped["Video"] = relationship(back_populates="tags")


class Airing(Base):
    __tablename__ = "airings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.sbid", ondelete="CASCADE"), index=True
    )
    aired_date: Mapped[date | None] = mapped_column(Date)
    network: Mapped[str | None] = mapped_column(String(128))
    market: Mapped[str | None] = mapped_column(String(64))
    region: Mapped[str | None] = mapped_column(String(64))

    video: Mapped["Video"] = relationship(back_populates="airings")


class Edit(Base):
    __tablename__ = "edits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    edit_type: Mapped[EditType] = mapped_column(pg_enum(EditType, name="edittype"))
    status: Mapped[EditStatus] = mapped_column(
        pg_enum(EditStatus, name="editstatus"), default=EditStatus.OPEN
    )
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    before_state: Mapped[dict | None] = mapped_column(JSONB)
    after_state: Mapped[dict] = mapped_column(JSONB)
    editor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    comment: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    editor: Mapped["User"] = relationship(back_populates="edits")
    votes: Mapped[list["Vote"]] = relationship(back_populates="edit", cascade="all, delete-orphan")


class Vote(Base):
    __tablename__ = "votes"
    __table_args__ = (UniqueConstraint("edit_id", "voter_id", name="uq_edit_voter"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    edit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("edits.id", ondelete="CASCADE"), index=True
    )
    voter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    choice: Mapped[VoteChoice] = mapped_column(pg_enum(VoteChoice, name="votechoice"))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    edit: Mapped["Edit"] = relationship(back_populates="votes")
    voter: Mapped["User"] = relationship(back_populates="votes")


class DMCATakedown(Base):
    __tablename__ = "dmca_takedowns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.sbid"), index=True
    )
    status: Mapped[DMCAStatus] = mapped_column(
        pg_enum(DMCAStatus, name="dmcstatus"), default=DMCAStatus.SUBMITTED
    )
    claimant_name: Mapped[str] = mapped_column(String(255))
    claimant_email: Mapped[str] = mapped_column(String(255))
    claimant_address: Mapped[str | None] = mapped_column(Text)
    claim_text: Mapped[str] = mapped_column(Text)
    signature: Mapped[str] = mapped_column(String(255))
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    review_notes: Mapped[str | None] = mapped_column(Text)
    counter_claim_text: Mapped[str | None] = mapped_column(Text)
    counter_claimant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    video: Mapped["Video"] = relationship(back_populates="dmca_takedowns")
    reviewed_by: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by_id])


class MediaFingerprint(Base):
    __tablename__ = "media_fingerprints"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    edit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("edits.id"), nullable=True, index=True
    )
    video_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.sbid"), nullable=True
    )
    youtube_id: Mapped[str] = mapped_column(String(32), index=True)
    phase: Mapped[FingerprintPhase] = mapped_column(pg_enum(FingerprintPhase, name="fingerprintphase"))
    status: Mapped[FingerprintStatus] = mapped_column(
        pg_enum(FingerprintStatus, name="fingerprintstatus"), default=FingerprintStatus.PENDING
    )
    phash: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    audio_fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    probe_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action: Mapped[str] = mapped_column(String(128), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SubmissionTermsDocument(Base):
    __tablename__ = "submission_terms_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    intro: Mapped[str] = mapped_column(Text)
    sections: Mapped[list] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
