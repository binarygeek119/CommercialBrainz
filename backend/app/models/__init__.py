import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
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
    REMOVE_VIDEO = "remove_video"
    ADD_CREDIT = "add_credit"
    ADD_TAG = "add_tag"


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


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, name="userrole"), default=UserRole.USER)
    is_auto_editor: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    accepted_edits_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    edits: Mapped[list["Edit"]] = relationship(back_populates="editor")
    votes: Mapped[list["Vote"]] = relationship(back_populates="voter")


class Advertiser(Base):
    __tablename__ = "advertisers"

    sbid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    external_ids: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    commercials: Mapped[list["Commercial"]] = relationship(back_populates="advertiser")


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
    channel_name: Mapped[str | None] = mapped_column(String(255))
    upload_date: Mapped[date | None] = mapped_column(Date)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    aspect_ratio: Mapped[str | None] = mapped_column(String(16))
    resolution: Mapped[str | None] = mapped_column(String(32))
    language: Mapped[str | None] = mapped_column(String(16))
    region: Mapped[str | None] = mapped_column(String(64))
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


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action: Mapped[str] = mapped_column(String(128), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
