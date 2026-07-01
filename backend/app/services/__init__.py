import logging
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import (
    Advertiser,
    Agency,
    AuditLog,
    Commercial,
    CommercialProduct,
    DMCATakedown,
    DMCAStatus,
    Edit,
    EditStatus,
    EditType,
    User,
    UserRole,
    Video,
    VideoCredit,
    VideoTag,
    VideoVisibility,
    Vote,
    VoteChoice,
)
from app.utils import extract_youtube_id, make_unique_slug, youtube_watch_url

logger = logging.getLogger(__name__)
settings = get_settings()


class EditService:
    @staticmethod
    async def create_edit(
        db: AsyncSession,
        editor: User,
        edit_type: EditType,
        entity_type: str,
        after_state: dict,
        before_state: dict | None = None,
        entity_id: UUID | None = None,
        comment: str | None = None,
        force_votable: bool = False,
    ) -> Edit:
        is_auto = (
            editor.role in (UserRole.MOD, UserRole.ADMIN) or editor.is_auto_editor
        ) and not force_votable

        expires_at = datetime.now(UTC) + timedelta(days=settings.edit_open_days)
        edit = Edit(
            edit_type=edit_type,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=before_state,
            after_state=after_state,
            editor_id=editor.id,
            comment=comment,
            expires_at=expires_at,
            status=EditStatus.OPEN,
        )
        db.add(edit)
        await db.flush()

        if is_auto:
            edit.status = EditStatus.AUTOMATICALLY_APPLIED
            edit.closed_at = datetime.now(UTC)
            await EditService.apply_edit(db, edit)
            editor.accepted_edits_count += 1

        return edit

    @staticmethod
    async def apply_edit(db: AsyncSession, edit: Edit) -> None:
        state = edit.after_state
        et = edit.edit_type

        if et == EditType.CREATE_COMMERCIAL:
            await EditService._apply_create_commercial(db, edit, state)
        elif et == EditType.EDIT_COMMERCIAL:
            await EditService._apply_edit_commercial(db, edit, state)
        elif et == EditType.CREATE_VIDEO:
            await EditService._apply_create_video(db, edit, state)
        elif et == EditType.EDIT_VIDEO:
            await EditService._apply_edit_video(db, edit, state)
        elif et == EditType.REMOVE_VIDEO:
            await EditService._apply_remove_video(db, edit)
        elif et == EditType.ADD_TAG:
            await EditService._apply_add_tag(db, edit, state)
        elif et == EditType.ADD_CREDIT:
            await EditService._apply_add_credit(db, edit, state)
        elif et == EditType.MERGE_COMMERCIAL:
            await EditService._apply_merge_commercial(db, edit, state)

        if edit.status == EditStatus.OPEN:
            edit.status = EditStatus.APPLIED
            edit.closed_at = datetime.now(UTC)

    @staticmethod
    async def _apply_create_commercial(db: AsyncSession, edit: Edit, state: dict) -> None:
        slug_result = await db.execute(select(Advertiser.slug))
        existing_slugs = {r[0] for r in slug_result.all()}

        advertiser_id = state.get("advertiser_id")
        if state.get("advertiser_name") and not advertiser_id:
            slug = make_unique_slug(state["advertiser_name"], existing_slugs)
            adv = Advertiser(name=state["advertiser_name"], slug=slug)
            db.add(adv)
            await db.flush()
            advertiser_id = str(adv.sbid)

        agency_id = state.get("agency_id")
        if state.get("agency_name") and not agency_id:
            agency_result = await db.execute(select(Agency.slug))
            agency_slugs = {r[0] for r in agency_result.all()}
            slug = make_unique_slug(state["agency_name"], agency_slugs)
            ag = Agency(name=state["agency_name"], slug=slug)
            db.add(ag)
            await db.flush()
            agency_id = str(ag.sbid)

        commercial = Commercial(
            title=state["title"],
            advertiser_id=UUID(advertiser_id) if advertiser_id else None,
            agency_id=UUID(agency_id) if agency_id else None,
            year=state.get("year"),
            campaign_name=state.get("campaign_name"),
            description=state.get("description"),
            external_ids=state.get("external_ids", {}),
        )
        db.add(commercial)
        await db.flush()
        edit.entity_id = commercial.sbid

        for product in state.get("products", []):
            db.add(CommercialProduct(commercial_id=commercial.sbid, name=product))

    @staticmethod
    async def _apply_edit_commercial(db: AsyncSession, edit: Edit, state: dict) -> None:
        result = await db.execute(select(Commercial).where(Commercial.sbid == edit.entity_id))
        commercial = result.scalar_one_or_none()
        if not commercial:
            edit.status = EditStatus.FAILED
            return
        for field in ("title", "year", "campaign_name", "description", "advertiser_id", "agency_id"):
            if field in state:
                val = state[field]
                if field.endswith("_id") and val:
                    val = UUID(val) if isinstance(val, str) else val
                setattr(commercial, field, val)

    @staticmethod
    async def _apply_create_video(db: AsyncSession, edit: Edit, state: dict) -> None:
        commercial_id = state.get("commercial_id")
        if not commercial_id and state.get("commercial"):
            sub_edit = Edit(
                edit_type=EditType.CREATE_COMMERCIAL,
                entity_type="commercial",
                after_state=state["commercial"],
                editor_id=edit.editor_id,
                expires_at=edit.expires_at,
                status=EditStatus.APPLIED,
                closed_at=datetime.now(UTC),
            )
            db.add(sub_edit)
            await db.flush()
            await EditService._apply_create_commercial(db, sub_edit, state["commercial"])
            commercial_id = str(sub_edit.entity_id)

        youtube_id = state.get("youtube_id") or extract_youtube_id(state["youtube_url"])
        video = Video(
            commercial_id=UUID(commercial_id) if isinstance(commercial_id, str) else commercial_id,
            youtube_id=youtube_id,
            youtube_url=youtube_watch_url(youtube_id),
            channel_name=state.get("channel_name"),
            upload_date=date.fromisoformat(state["upload_date"]) if state.get("upload_date") else None,
            duration_ms=state.get("duration_ms"),
            aspect_ratio=state.get("aspect_ratio"),
            resolution=state.get("resolution"),
            language=state.get("language"),
            region=state.get("region"),
            market=state.get("market"),
            first_aired_date=date.fromisoformat(state["first_aired_date"])
            if state.get("first_aired_date")
            else None,
            last_aired_date=date.fromisoformat(state["last_aired_date"])
            if state.get("last_aired_date")
            else None,
            network=state.get("network"),
            transcript=state.get("transcript"),
            slogan=state.get("slogan"),
            cta_text=state.get("cta_text"),
            metadata=state.get("metadata", {}),
            submitted_by_id=edit.editor_id,
        )
        db.add(video)
        await db.flush()
        edit.entity_id = video.sbid

        for credit in state.get("credits", []):
            db.add(VideoCredit(video_id=video.sbid, role=credit["role"], name=credit["name"]))
        for tag in state.get("tags", []):
            db.add(VideoTag(video_id=video.sbid, tag=tag.lower()))

    @staticmethod
    async def _apply_edit_video(db: AsyncSession, edit: Edit, state: dict) -> None:
        result = await db.execute(select(Video).where(Video.sbid == edit.entity_id))
        video = result.scalar_one_or_none()
        if not video:
            edit.status = EditStatus.FAILED
            return
        date_fields = {"upload_date", "first_aired_date", "last_aired_date"}
        for field, val in state.items():
            if field in date_fields and val:
                val = date.fromisoformat(val) if isinstance(val, str) else val
            if hasattr(video, field):
                setattr(video, field, val)

    @staticmethod
    async def _apply_remove_video(db: AsyncSession, edit: Edit) -> None:
        result = await db.execute(select(Video).where(Video.sbid == edit.entity_id))
        video = result.scalar_one_or_none()
        if video:
            video.visibility = VideoVisibility.REMOVED

    @staticmethod
    async def _apply_add_tag(db: AsyncSession, edit: Edit, state: dict) -> None:
        db.add(VideoTag(video_id=edit.entity_id, tag=state["tag"].lower()))

    @staticmethod
    async def _apply_add_credit(db: AsyncSession, edit: Edit, state: dict) -> None:
        db.add(VideoCredit(video_id=edit.entity_id, role=state["role"], name=state["name"]))

    @staticmethod
    async def _apply_merge_commercial(db: AsyncSession, edit: Edit, state: dict) -> None:
        source_id = UUID(state["source_id"])
        target_id = UUID(state["target_id"])
        result = await db.execute(select(Video).where(Video.commercial_id == source_id))
        for video in result.scalars().all():
            video.commercial_id = target_id
        result = await db.execute(select(Commercial).where(Commercial.sbid == source_id))
        source = result.scalar_one_or_none()
        if source:
            await db.delete(source)

    @staticmethod
    async def cast_vote(
        db: AsyncSession, edit: Edit, voter: User, choice: VoteChoice, comment: str | None = None
    ) -> Vote:
        existing = await db.execute(
            select(Vote).where(Vote.edit_id == edit.id, Vote.voter_id == voter.id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Already voted on this edit")

        vote = Vote(edit_id=edit.id, voter_id=voter.id, choice=choice, comment=comment)
        db.add(vote)
        await db.flush()

        if choice == VoteChoice.NO:
            min_expiry = datetime.now(UTC) + timedelta(hours=settings.voting_no_vote_extension_hours)
            if edit.expires_at < min_expiry:
                edit.expires_at = min_expiry

        await EditService._evaluate_votes(db, edit)
        return vote

    @staticmethod
    async def _evaluate_votes(db: AsyncSession, edit: Edit) -> None:
        if edit.status != EditStatus.OPEN:
            return

        result = await db.execute(select(Vote).where(Vote.edit_id == edit.id))
        votes = result.scalars().all()
        yes = sum(1 for v in votes if v.choice == VoteChoice.YES)
        no = sum(1 for v in votes if v.choice == VoteChoice.NO)
        threshold = settings.edit_early_close_votes

        if yes >= threshold and no == 0:
            edit.status = EditStatus.APPLIED
            edit.closed_at = datetime.now(UTC)
            await EditService.apply_edit(db, edit)
            editor = await db.get(User, edit.editor_id)
            if editor:
                editor.accepted_edits_count += 1
        elif no >= threshold and yes == 0:
            edit.status = EditStatus.REJECTED
            edit.closed_at = datetime.now(UTC)

    @staticmethod
    async def expire_open_edits(db: AsyncSession) -> int:
        now = datetime.now(UTC)
        result = await db.execute(
            select(Edit).where(Edit.status == EditStatus.OPEN, Edit.expires_at <= now)
        )
        edits = result.scalars().all()
        count = 0
        for edit in edits:
            vote_result = await db.execute(select(Vote).where(Vote.edit_id == edit.id))
            votes = vote_result.scalars().all()
            yes = sum(1 for v in votes if v.choice == VoteChoice.YES)
            no = sum(1 for v in votes if v.choice == VoteChoice.NO)

            if no >= yes and no > 0:
                edit.status = EditStatus.REJECTED
            else:
                edit.status = EditStatus.APPLIED
                await EditService.apply_edit(db, edit)
                editor = await db.get(User, edit.editor_id)
                if editor:
                    editor.accepted_edits_count += 1

            edit.closed_at = now
            count += 1
        return count


class DMCAService:
    @staticmethod
    async def submit(db: AsyncSession, data: dict) -> DMCATakedown:
        takedown = DMCATakedown(
            video_id=data["video_id"],
            claimant_name=data["claimant_name"],
            claimant_email=data["claimant_email"],
            claimant_address=data.get("claimant_address"),
            claim_text=data["claim_text"],
            signature=data["signature"],
        )
        db.add(takedown)
        await db.flush()
        db.add(
            AuditLog(
                action="dmca_submitted",
                entity_type="dmca_takedown",
                entity_id=takedown.id,
                details={"video_id": str(data["video_id"])},
            )
        )
        return takedown

    @staticmethod
    async def review(
        db: AsyncSession,
        takedown: DMCATakedown,
        reviewer: User,
        new_status: DMCAStatus,
        notes: str | None = None,
    ) -> DMCATakedown:
        takedown.status = new_status
        takedown.reviewed_by_id = reviewer.id
        takedown.review_notes = notes

        result = await db.execute(select(Video).where(Video.sbid == takedown.video_id))
        video = result.scalar_one_or_none()

        if new_status == DMCAStatus.LINK_HIDDEN and video:
            video.visibility = VideoVisibility.DMCA_HIDDEN
        elif new_status == DMCAStatus.RESTORED and video:
            video.visibility = VideoVisibility.PUBLIC
        elif new_status == DMCAStatus.PERMANENTLY_REMOVED and video:
            video.visibility = VideoVisibility.REMOVED

        db.add(
            AuditLog(
                action=f"dmca_{new_status.value}",
                entity_type="dmca_takedown",
                entity_id=takedown.id,
                actor_id=reviewer.id,
                details={"notes": notes, "video_id": str(takedown.video_id)},
            )
        )
        return takedown


class SearchService:
    @staticmethod
    async def search(db: AsyncSession, query: str, entity_type: str = "video", limit: int = 25) -> list:
        q = f"%{query.lower()}%"
        results = []

        if entity_type in ("video", "all"):
            stmt = (
                select(Video, Commercial.title)
                .join(Commercial, Video.commercial_id == Commercial.sbid)
                .where(
                    Video.visibility == VideoVisibility.PUBLIC,
                    or_(
                        func.lower(Commercial.title).like(q),
                        func.lower(Video.transcript).like(q),
                        func.lower(Video.slogan).like(q),
                    ),
                )
                .limit(limit)
            )
            rows = await db.execute(stmt)
            for video, title in rows.all():
                results.append({"type": "video", "sbid": video.sbid, "title": title, "subtitle": video.youtube_id})

        if entity_type in ("commercial", "all"):
            stmt = select(Commercial).where(func.lower(Commercial.title).like(q)).limit(limit)
            rows = await db.execute(stmt)
            for c in rows.scalars().all():
                results.append({"type": "commercial", "sbid": c.sbid, "title": c.title, "subtitle": None})

        if entity_type in ("advertiser", "all"):
            stmt = select(Advertiser).where(func.lower(Advertiser.name).like(q)).limit(limit)
            rows = await db.execute(stmt)
            for a in rows.scalars().all():
                results.append({"type": "advertiser", "sbid": a.sbid, "title": a.name, "subtitle": None})

        return results[:limit]

    @staticmethod
    async def get_video_detail(db: AsyncSession, sbid: UUID, include_hidden: bool = False) -> Video | None:
        stmt = (
            select(Video)
            .options(
                selectinload(Video.commercial).selectinload(Commercial.advertiser),
                selectinload(Video.commercial).selectinload(Commercial.agency),
                selectinload(Video.credits),
                selectinload(Video.tags),
            )
            .where(Video.sbid == sbid)
        )
        if not include_hidden:
            stmt = stmt.where(Video.visibility == VideoVisibility.PUBLIC)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
