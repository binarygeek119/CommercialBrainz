import logging
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.security import user_is_mod
from app.config import get_settings
from app.models import (
    Advertiser,
    AdvertiserLogo,
    AdvertiserStatus,
    Agency,
    AuditLog,
    Commercial,
    CommercialProduct,
    DMCAStatus,
    DMCATakedown,
    Edit,
    EditStatus,
    EditType,
    FingerprintPhase,
    FingerprintStatus,
    MediaFingerprint,
    User,
    UserRole,
    Video,
    VideoCredit,
    VideoHashStatus,
    VideoTag,
    VideoVisibility,
    Vote,
    VoteChoice,
)
from app.services.media_hash import copy_preview_to_video
from app.services.reputation import assert_can_submit, award_reputation_for_applied_edit
from app.utils import extract_youtube_id, make_unique_slug, youtube_thumbnail_url, youtube_watch_url

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
        is_auto = ( editor.role in (UserRole.MOD, UserRole.ADMIN)
                   or editor.is_auto_editor ) and not force_votable

        if not is_auto:
            await assert_can_submit(db, editor)

        expires_at = datetime.now(
            UTC) + timedelta(days=settings.edit_open_days)
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

        if edit_type == EditType.CREATE_ADVERTISER:
            from app.services.advertisers import prepare_create_advertiser_edit

            await prepare_create_advertiser_edit(db, edit)

        if is_auto:
            edit.status = EditStatus.AUTOMATICALLY_APPLIED
            edit.closed_at = datetime.now(UTC)
            pending_hash = await EditService.apply_edit(db, edit)
            editor.accepted_edits_count += 1
            if pending_hash is not None:
                edit._pending_hash_job = pending_hash  # noqa: SLF001

        return edit

    @staticmethod
    async def _complete_applied_edit(
    db: AsyncSession,
     edit: Edit) -> UUID | None:
        pending_hash = await EditService.apply_edit(db, edit)
        editor = await db.get(User, edit.editor_id)
        if editor:
            editor.accepted_edits_count += 1
        await award_reputation_for_applied_edit(db, edit)
        return pending_hash

    @staticmethod
    async def apply_edit(db: AsyncSession, edit: Edit) -> UUID | None:
        state = edit.after_state
        et = edit.edit_type
        pending_hash: UUID | None = None

        if et == EditType.CREATE_COMMERCIAL:
            await EditService._apply_create_commercial(db, edit, state)
        elif et == EditType.EDIT_COMMERCIAL:
            await EditService._apply_edit_commercial(db, edit, state)
        elif et == EditType.CREATE_VIDEO:
            pending_hash = await EditService._apply_create_video(db, edit, state)
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
        elif et == EditType.SPLIT_COMMERCIAL:
            await EditService._apply_split_commercial(db, edit, state)
        elif et == EditType.CREATE_ADVERTISER:
            await EditService._apply_create_advertiser(db, edit, state)
        elif et == EditType.EDIT_ADVERTISER:
            await EditService._apply_edit_advertiser(db, edit, state)
        elif et == EditType.ADD_ADVERTISER_LOGO:
            await EditService._apply_add_advertiser_logo(db, edit, state)
        elif et == EditType.EDIT_ADVERTISER_LOGO:
            await EditService._apply_edit_advertiser_logo(db, edit, state)

        if edit.status == EditStatus.OPEN:
            edit.status = EditStatus.APPLIED
            edit.closed_at = datetime.now(UTC)

        return pending_hash

    @staticmethod
    async def _apply_create_commercial(
    db: AsyncSession,
    edit: Edit,
     state: dict) -> None:
        advertiser_id = state.get("advertiser_id")
        if state.get("advertiser_name") and not advertiser_id:
            raise ValueError(
                "New brands must be approved before use — use advertiser_id")

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
            decade=state.get("decade"),
            campaign_name=state.get("campaign_name"),
            description=state.get("description"),
            external_ids=state.get("external_ids", {}),
        )
        db.add(commercial)
        await db.flush()
        edit.entity_id = commercial.sbid

        for product in state.get("products", []):
            db.add(
    CommercialProduct(
        commercial_id=commercial.sbid,
         name=product))

    @staticmethod
    async def _apply_edit_commercial(
    db: AsyncSession,
    edit: Edit,
     state: dict) -> None:
        result = await db.execute(
            select(Commercial)
            .options(selectinload(Commercial.products))
            .where(Commercial.sbid == edit.entity_id)
        )
        commercial = result.scalar_one_or_none()
        if not commercial:
            edit.status = EditStatus.FAILED
            return
        for field in (
    "title",
    "year",
    "decade",
    "campaign_name",
    "description",
    "advertiser_id",
     "agency_id"):
            if field in state:
                val = state[field]
                if field.endswith("_id"):
                    val = UUID(val) if isinstance(val, str) and val else None
                setattr(commercial, field, val)

        if "products" in state:
            desired = [str(p).strip()
                           for p in state["products"] if str(p).strip()]
            existing = {p.name: p for p in commercial.products}
            for name, product in list(existing.items()):
                if name not in desired:
                    await db.delete(product)
            for name in desired:
                if name not in existing:
                    db.add(
    CommercialProduct(
        commercial_id=commercial.sbid,
         name=name))

    @staticmethod
    def _video_metadata_from_state(state: dict) -> dict:
        from app.services.submission_genres import merge_genres_into_metadata

        return merge_genres_into_metadata(
    state.get("metadata"), state.get("genres"))

    @staticmethod
    async def _apply_create_video(
    db: AsyncSession,
    edit: Edit,
     state: dict) -> UUID | None:
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

        youtube_id = state.get("youtube_id") or extract_youtube_id(
            state["youtube_url"])
        video = Video(
    commercial_id=UUID(commercial_id) if isinstance(
        commercial_id,
        str) else commercial_id,
        youtube_id=youtube_id,
        youtube_url=youtube_watch_url(youtube_id),
        thumbnail_url=state.get("thumbnail_url") or youtube_thumbnail_url(youtube_id),
        channel_name=state.get("channel_name"),
        upload_date=date.fromisoformat(
            state["upload_date"]) if state.get("upload_date") else None,
            duration_ms=state.get("duration_ms"),
            aspect_ratio=state.get("aspect_ratio"),
            resolution=state.get("resolution"),
            language=state.get("language"),
            region=state.get("region"),
            sub_region=state.get("sub_region"),
            market=state.get("market"),
            first_aired_date=date.fromisoformat(
                state["first_aired_date"]) if state.get("first_aired_date") else None,
                last_aired_date=date.fromisoformat(
                    state["last_aired_date"]) if state.get("last_aired_date") else None,
                    network=state.get("network"),
                    transcript=state.get("transcript"),
                    slogan=state.get("slogan"),
                    cta_text=state.get("cta_text"),
                    version_label=state.get("version_label"),
                    extra_data=EditService._video_metadata_from_state(state),
                    submitted_by_id=edit.editor_id,
                     )
        db.add(video)
        await db.flush()
        edit.entity_id = video.sbid

        for credit in state.get("credits", []):
            db.add(
    VideoCredit(
        video_id=video.sbid,
        role=credit["role"],
         name=credit["name"]))
        for tag in state.get("tags", []):
            db.add(VideoTag(video_id=video.sbid, tag=tag.lower()))

        if await copy_preview_to_video(db, edit.id, video.sbid):
            from app.services.video_popularity import recompute_main_video

            await recompute_main_video(db, video.commercial_id)
            return None

        video.hash_status = VideoHashStatus.PENDING
        fp = MediaFingerprint(
            edit_id=edit.id,
            video_id=video.sbid,
            youtube_id=youtube_id,
            phase=FingerprintPhase.FINAL,
            status=FingerprintStatus.PENDING,
        )
        db.add(fp)
        await db.flush()
        from app.services.video_popularity import recompute_main_video

        await recompute_main_video(db, video.commercial_id)
        return fp.id

    @staticmethod
    async def _apply_edit_video(
    db: AsyncSession,
    edit: Edit,
     state: dict) -> None:
        result = await db.execute(select(Video).where(Video.sbid == edit.entity_id))
        video = result.scalar_one_or_none()
        if not video:
            edit.status = EditStatus.FAILED
            return

        state = dict(state)
        staging = state.pop("thumbnail_staging_file", None)
        if staging:
            from app.services.thumbnail_storage import finalize_staged_thumbnail

            try:
                state["thumbnail_url"] = finalize_staged_thumbnail(
                    staging, video.sbid)
            except (ValueError, FileNotFoundError) as exc:
                edit.status = EditStatus.FAILED
                logger.error(
    "Thumbnail finalize failed for edit %s: %s", edit.id, exc)
                return

        date_fields = {"upload_date", "first_aired_date", "last_aired_date"}
        for field, val in state.items():
            if field == "metadata":
                field = "extra_data"
            if field in date_fields and val:
                val = date.fromisoformat(val) if isinstance(val, str) else val
            if hasattr(video, field):
                setattr(video, field, val)

    @staticmethod
    async def _apply_remove_video(db: AsyncSession, edit: Edit) -> None:
        result = await db.execute(select(Video).where(Video.sbid == edit.entity_id))
        video = result.scalar_one_or_none()
        if video:
            commercial_id = video.commercial_id
            video.visibility = VideoVisibility.REMOVED
            from app.services.video_popularity import recompute_main_video

            await recompute_main_video(db, commercial_id)

    @staticmethod
    async def _apply_add_tag(
    db: AsyncSession,
    edit: Edit,
     state: dict) -> None:
        db.add(VideoTag(video_id=edit.entity_id, tag=state["tag"].lower()))

    @staticmethod
    async def _apply_add_credit(
    db: AsyncSession,
    edit: Edit,
     state: dict) -> None:
        db.add(
    VideoCredit(
        video_id=edit.entity_id,
        role=state["role"],
         name=state["name"]))

    @staticmethod
    async def _apply_create_advertiser(
    db: AsyncSession,
    edit: Edit,
     state: dict) -> None:
        advertiser_id = edit.entity_id
        if not advertiser_id:
            raw = state.get("advertiser_id")
            advertiser_id = UUID(raw) if isinstance(raw, str) else raw
        if not advertiser_id:
            edit.status = EditStatus.FAILED
            return

        advertiser = await db.get(Advertiser, advertiser_id)
        if not advertiser:
            edit.status = EditStatus.FAILED
            return

        advertiser.status = AdvertiserStatus.APPROVED
        from app.services.advertiser_metadata import apply_advertiser_state

        apply_advertiser_state(advertiser, state)
        if state.get("external_ids"):
            advertiser.external_ids = state.get("external_ids", {})
        edit.entity_id = advertiser.sbid

    @staticmethod
    async def _apply_edit_advertiser(
    db: AsyncSession,
    edit: Edit,
     state: dict) -> None:
        advertiser_id = edit.entity_id
        if not advertiser_id:
            raw = state.get("advertiser_id")
            advertiser_id = UUID(raw) if isinstance(raw, str) else raw
        if not advertiser_id:
            edit.status = EditStatus.FAILED
            return

        advertiser = await db.get(Advertiser, advertiser_id)
        if not advertiser:
            edit.status = EditStatus.FAILED
            return

        state = dict(state)
        staging = state.pop("logo_staging_file", None)
        if staging:
            from app.services.advertiser_logos import recompute_main_logo
            from app.services.logo_storage import finalize_staged_logo

            logo = AdvertiserLogo(
                advertiser_id=advertiser.sbid,
                image_url=state.get("logo_url") or "",
                label=state.get("label"),
                year=state.get("year"),
                month=state.get("month"),
                event=state.get("event"),
                notes=state.get("notes"),
                submitted_by=edit.editor_id,
                edit_id=edit.id,
            )
            db.add(logo)
            await db.flush()
            try:
                logo.image_url = finalize_staged_logo(
                    staging, advertiser.sbid, logo.id)
            except (ValueError, FileNotFoundError) as exc:
                edit.status = EditStatus.FAILED
                logger.error(
    "Logo finalize failed for edit %s: %s", edit.id, exc)
                return
            await recompute_main_logo(db, advertiser.sbid)
            state.pop("logo_url", None)

        from app.services.advertiser_metadata import apply_advertiser_state

        apply_advertiser_state(advertiser, state)

    @staticmethod
    async def _apply_add_advertiser_logo(
    db: AsyncSession,
    edit: Edit,
     state: dict) -> None:
        advertiser_id = edit.entity_id
        if not advertiser_id:
            raw = state.get("advertiser_id")
            advertiser_id = UUID(raw) if isinstance(raw, str) else raw
        if not advertiser_id:
            edit.status = EditStatus.FAILED
            return

        advertiser = await db.get(Advertiser, advertiser_id)
        if not advertiser:
            edit.status = EditStatus.FAILED
            return

        state = dict(state)
        staging = state.pop("logo_staging_file", None)
        if not staging:
            edit.status = EditStatus.FAILED
            return

        from app.services.advertiser_logos import create_logo_from_edit
        from app.services.logo_storage import finalize_staged_logo

        logo = await create_logo_from_edit(
            db,
            advertiser_id=advertiser.sbid,
            image_url=state.get("logo_url") or "",
            editor_id=edit.editor_id,
            edit_id=edit.id,
            label=state.get("label"),
            year=state.get("year"),
            month=state.get("month"),
            event=state.get("event"),
            notes=state.get("notes"),
        )
        try:
            logo.image_url = finalize_staged_logo(
                staging, advertiser.sbid, logo.id)
        except (ValueError, FileNotFoundError) as exc:
            edit.status = EditStatus.FAILED
            logger.error("Logo finalize failed for edit %s: %s", edit.id, exc)
            await db.delete(logo)
            return

        from app.services.advertiser_logos import recompute_main_logo

        await recompute_main_logo(db, advertiser.sbid)

    @staticmethod
    async def _apply_edit_advertiser_logo(
    db: AsyncSession,
    edit: Edit,
     state: dict) -> None:
        logo_id = edit.entity_id
        if not logo_id:
            raw = state.get("logo_id")
            logo_id = UUID(raw) if isinstance(raw, str) else raw
        if not logo_id:
            edit.status = EditStatus.FAILED
            return

        logo = await db.get(AdvertiserLogo, logo_id)
        if not logo:
            edit.status = EditStatus.FAILED
            return

        for field in ("label", "year", "month", "event", "notes"):
            if field in state:
                setattr(logo, field, state[field])

        await db.flush()

    @staticmethod
    async def _reject_create_advertiser(db: AsyncSession, edit: Edit) -> None:
        if not edit.entity_id:
            return
        advertiser = await db.get(Advertiser, edit.entity_id)
        if advertiser and advertiser.status == AdvertiserStatus.PENDING:
            advertiser.status = AdvertiserStatus.REJECTED

    @staticmethod
    async def reject_edit(db: AsyncSession, edit: Edit) -> None:
        if edit.status != EditStatus.OPEN:
            return
        edit.status = EditStatus.REJECTED
        edit.closed_at = datetime.now(UTC)
        if edit.edit_type == EditType.CREATE_ADVERTISER:
            await EditService._reject_create_advertiser(db, edit)
        elif edit.edit_type == EditType.EDIT_VIDEO:
            staging = (edit.after_state or {}).get("thumbnail_staging_file")
            if staging:
                from app.services.thumbnail_storage import discard_staged_thumbnail

                discard_staged_thumbnail(staging)
        elif edit.edit_type == EditType.EDIT_ADVERTISER:
            staging = (edit.after_state or {}).get("logo_staging_file")
            if staging:
                from app.services.logo_storage import discard_staged_logo

                discard_staged_logo(staging)
        elif edit.edit_type == EditType.ADD_ADVERTISER_LOGO:
            staging = (edit.after_state or {}).get("logo_staging_file")
            if staging:
                from app.services.logo_storage import discard_staged_logo

                discard_staged_logo(staging)

    @staticmethod
    def _vote_threshold(edit: Edit) -> int:
        if edit.edit_type in (
            EditType.CREATE_ADVERTISER,
            EditType.EDIT_ADVERTISER,
            EditType.ADD_ADVERTISER_LOGO,
            EditType.EDIT_ADVERTISER_LOGO,
        ):
            return settings.brand_early_close_votes
        return settings.edit_early_close_votes

    @staticmethod
    async def _apply_merge_commercial(
    db: AsyncSession,
    edit: Edit,
     state: dict) -> None:
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
    async def _apply_split_commercial(
    db: AsyncSession,
    edit: Edit,
     state: dict) -> None:
        source_id = UUID(state["source_commercial_id"])
        video_id = UUID(state["video_id"])
        commercial_data = state.get("commercial")
        if not commercial_data:
            edit.status = EditStatus.FAILED
            return

        video = await db.get(Video, video_id)
        if not video or video.commercial_id != source_id:
            edit.status = EditStatus.FAILED
            return

        public_count = await db.scalar(
            select(func.count())
            .select_from(Video)
            .where(Video.commercial_id == source_id, Video.visibility == VideoVisibility.PUBLIC)
        )
        if int(public_count or 0) < 2:
            edit.status = EditStatus.FAILED
            return

        sub_edit = Edit(
            edit_type=EditType.CREATE_COMMERCIAL,
            entity_type="commercial",
            after_state=commercial_data,
            editor_id=edit.editor_id,
            expires_at=edit.expires_at,
            status=EditStatus.APPLIED,
            closed_at=datetime.now(UTC),
        )
        db.add(sub_edit)
        await db.flush()
        await EditService._apply_create_commercial(db, sub_edit, commercial_data)
        new_commercial_id = sub_edit.entity_id
        if not new_commercial_id:
            edit.status = EditStatus.FAILED
            return

        video.commercial_id = new_commercial_id
        await db.flush()

        from app.services.video_popularity import recompute_main_video

        await recompute_main_video(db, source_id)
        await recompute_main_video(db, new_commercial_id)
        edit.entity_id = new_commercial_id

    @staticmethod
    def _mod_vote_decision(
        votes: list[Vote], voters_by_id: dict[UUID, User]) -> str | None:
        """Return apply/reject when a mod or admin has voted yes/no; None otherwise."""
        mod_yes = False
        mod_no = False
        for vote in votes:
            voter = voters_by_id.get(vote.voter_id)
            if not voter or not user_is_mod(voter):
                continue
            if vote.choice == VoteChoice.NO:
                mod_no = True
            elif vote.choice == VoteChoice.YES:
                mod_yes = True
        if mod_no:
            return "reject"
        if mod_yes:
            return "apply"
        return None

    @staticmethod
    async def _load_voters_for_votes(
        db: AsyncSession, votes: list[Vote]) -> dict[UUID, User]:
        voter_ids = {vote.voter_id for vote in votes}
        if not voter_ids:
            return {}
        result = await db.execute(select(User).where(User.id.in_(voter_ids)))
        return {user.id: user for user in result.scalars().all()}

    @staticmethod
    async def _apply_mod_decision(
    db: AsyncSession,
    edit: Edit,
     decision: str) -> UUID | None:
        if decision == "apply":
            edit.status = EditStatus.APPLIED
            edit.closed_at = datetime.now(UTC)
            pending_hash = await EditService._complete_applied_edit(db, edit)
            if pending_hash is not None:
                edit._pending_hash_job = pending_hash  # noqa: SLF001
            return pending_hash
        if decision == "reject":
            await EditService.reject_edit(db, edit)
        return None

    @staticmethod
    async def cast_vote(
    db: AsyncSession,
    edit: Edit,
    voter: User,
    choice: VoteChoice | None,
     comment: str | None = None ) -> Vote | None:
        result = await db.execute(
            select(Vote).where(Vote.edit_id == edit.id, Vote.voter_id == voter.id)
        )
        existing = result.scalar_one_or_none()

        if choice is None:
            if not existing:
                return None
            await db.delete(existing)
            await db.flush()
            await EditService._evaluate_votes(db, edit)
            return None

        if user_is_mod(voter) and choice == VoteChoice.ABSTAIN:
            raise ValueError("Moderator votes must be yes or no")

        if existing:
            existing.choice = choice
            if comment is not None:
                existing.comment = comment
            vote = existing
        else:
            vote = Vote(
    edit_id=edit.id,
    voter_id=voter.id,
    choice=choice,
     comment=comment)
            db.add(vote)

        await db.flush()

        if choice == VoteChoice.NO and not user_is_mod(voter):
            min_expiry = datetime.now(
                UTC) + timedelta(hours=settings.voting_no_vote_extension_hours)
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
        voters_by_id = await EditService._load_voters_for_votes(db, votes)
        decision = EditService._mod_vote_decision(votes, voters_by_id)
        if decision:
            await EditService._apply_mod_decision(db, edit, decision)
            return
        if edit.edit_type == EditType.SPLIT_COMMERCIAL and EditService._should_early_apply_split(
            votes):
            edit.status = EditStatus.APPLIED
            edit.closed_at = datetime.now(UTC)
            pending_hash = await EditService._complete_applied_edit(db, edit)
            if pending_hash is not None:
                edit._pending_hash_job = pending_hash  # noqa: SLF001

    @staticmethod
    def _split_yes_count(votes: list[Vote]) -> int:
        return sum(1 for vote in votes if vote.choice == VoteChoice.YES)

    @staticmethod
    def _split_no_count(votes: list[Vote]) -> int:
        return sum(1 for vote in votes if vote.choice == VoteChoice.NO)

    @staticmethod
    def _should_early_apply_split(votes: list[Vote]) -> bool:
        return EditService._split_yes_count(
            votes) >= settings.split_vote_threshold

    @staticmethod
    def _lapse_decision_split(votes: list[Vote]) -> str:
        """Split proposals after 3 months: yes wins if it has votes and beats no."""
        yes = EditService._split_yes_count(votes)
        no = EditService._split_no_count(votes)
        if yes == 0:
            return "reject"
        if yes > no:
            return "apply"
        if no > yes:
            return "reject"
        return "apply"

    @staticmethod
    def _lapse_decision(votes: list[Vote]) -> str:
        """Return apply/reject when an open edit reaches expires_at without a mod decision."""
        if not votes:
            return "apply"
        yes = sum(1 for v in votes if v.choice == VoteChoice.YES)
        no = sum(1 for v in votes if v.choice == VoteChoice.NO)
        if no >= yes and no > 0:
            return "reject"
        return "apply"

    @staticmethod
    async def expire_open_edits(db: AsyncSession) -> tuple[int, list[UUID]]:
        now = datetime.now(UTC)
        pending_jobs: list[UUID] = []
        result = await db.execute(
            select(Edit).where(Edit.status == EditStatus.OPEN, Edit.expires_at <= now)
        )
        edits = result.scalars().all()
        count = 0
        for edit in edits:
            vote_result = await db.execute(select(Vote).where(Vote.edit_id == edit.id))
            votes = vote_result.scalars().all()
            voters_by_id = await EditService._load_voters_for_votes(db, votes)
            decision = EditService._mod_vote_decision(votes, voters_by_id)
            if not decision:
                if edit.edit_type == EditType.SPLIT_COMMERCIAL:
                    decision = EditService._lapse_decision_split(votes)
                else:
                    decision = EditService._lapse_decision(votes)
            if decision == "reject":
                await EditService.reject_edit(db, edit)
            else:
                edit.status = EditStatus.APPLIED
                pending_hash = await EditService._complete_applied_edit(db, edit)
                if pending_hash is not None:
                    pending_jobs.append(pending_hash)

            edit.closed_at = now
            count += 1
        return count, pending_jobs


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
    async def search(
    db: AsyncSession,
    query: str,
    entity_type: str = "video",
     limit: int = 25) -> list:
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
                results.append({"type": "video",
    "sbid": video.sbid,
    "title": title,
     "subtitle": video.youtube_id})

        if entity_type in ("commercial", "all"):
            stmt = select(Commercial).where(func.lower(
                Commercial.title).like(q)).limit(limit)
            rows = await db.execute(stmt)
            for c in rows.scalars().all():
                results.append(
                    {"type": "commercial", "sbid": c.sbid, "title": c.title, "subtitle": None})

        if entity_type in ("advertiser", "all"):
            stmt = (
                select(Advertiser)
                .where(
                    func.lower(Advertiser.name).like(q),
                    Advertiser.status == AdvertiserStatus.APPROVED,
                )
                .limit(limit)
            )
            rows = await db.execute(stmt)
            for a in rows.scalars().all():
                results.append(
                    {"type": "advertiser", "sbid": a.sbid, "title": a.name, "subtitle": None})

        return results[:limit]

    @staticmethod
    async def get_video_detail(
    db: AsyncSession,
    sbid: UUID,
     include_hidden: bool = False) -> Video | None:
        stmt = (
    select(Video) .options(
        selectinload(
            Video.commercial).selectinload(
                Commercial.advertiser),
                selectinload(
                    Video.commercial).selectinload(
                        Commercial.agency),
                        selectinload(
                            Video.credits),
                            selectinload(
                                Video.tags),
                                ) .where(
                                    Video.sbid == sbid) )
        if not include_hidden:
            stmt = stmt.where(Video.visibility == VideoVisibility.PUBLIC)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
