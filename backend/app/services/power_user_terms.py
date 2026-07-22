"""Power User Terms documents and acceptance."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.power_user_terms_v1 import POWER_USER_TERMS_V1
from app.models import PowerUserTermsDocument, User


async def get_active_power_user_terms(db: AsyncSession) -> PowerUserTermsDocument | None:
    result = await db.execute(
        select(PowerUserTermsDocument)
        .where(PowerUserTermsDocument.is_active.is_(True))
        .order_by(PowerUserTermsDocument.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def power_user_terms_to_dict(doc: PowerUserTermsDocument) -> dict:
    return {
        "version": doc.version,
        "title": doc.title,
        "intro": doc.intro,
        "sections": doc.sections,
        "accepted": False,
    }


async def ensure_power_user_terms_seeded(db: AsyncSession) -> PowerUserTermsDocument:
    doc = await get_active_power_user_terms(db)
    if doc:
        return doc

    seed = POWER_USER_TERMS_V1
    doc = PowerUserTermsDocument(
        version=seed["version"],
        title=seed["title"],
        intro=seed["intro"],
        sections=seed["sections"],
        is_active=True,
    )
    db.add(doc)
    await db.flush()
    return doc


async def record_power_user_terms_acceptance(
    db: AsyncSession, user: User
) -> PowerUserTermsDocument:
    doc = await get_active_power_user_terms(db)
    if not doc:
        doc = await ensure_power_user_terms_seeded(db)

    user.power_user_terms_version = doc.version
    user.power_user_terms_accepted_at = datetime.now(UTC)
    return doc


async def validate_and_record_power_user_terms(
    db: AsyncSession, user: User, agreed: bool
) -> PowerUserTermsDocument:
    if not agreed:
        raise ValueError("You must agree to the Power User Terms")
    return await record_power_user_terms_acceptance(db, user)


async def active_power_user_terms_version(db: AsyncSession) -> int | None:
    doc = await get_active_power_user_terms(db)
    if not doc:
        doc = await ensure_power_user_terms_seeded(db)
    return doc.version if doc else None
