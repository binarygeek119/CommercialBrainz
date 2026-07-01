from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.submission_terms_v1 import SUBMISSION_TERMS_V1
from app.models import SubmissionTermsDocument


async def get_active_submission_terms(db: AsyncSession) -> SubmissionTermsDocument | None:
    result = await db.execute(
        select(SubmissionTermsDocument)
        .where(SubmissionTermsDocument.is_active.is_(True))
        .order_by(SubmissionTermsDocument.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def terms_document_to_dict(doc: SubmissionTermsDocument) -> dict:
    return {
        "version": doc.version,
        "title": doc.title,
        "intro": doc.intro,
        "sections": doc.sections,
        "quiz_required": True,
    }


def fallback_terms_dict() -> dict:
    return {
        "version": SUBMISSION_TERMS_V1["version"],
        "title": SUBMISSION_TERMS_V1["title"],
        "intro": SUBMISSION_TERMS_V1["intro"],
        "sections": SUBMISSION_TERMS_V1["sections"],
        "quiz_required": True,
    }


async def ensure_submission_terms_seeded(db: AsyncSession) -> SubmissionTermsDocument:
    doc = await get_active_submission_terms(db)
    if doc:
        return doc

    seed = SUBMISSION_TERMS_V1
    doc = SubmissionTermsDocument(
        version=seed["version"],
        title=seed["title"],
        intro=seed["intro"],
        sections=seed["sections"],
        is_active=True,
    )
    db.add(doc)
    await db.flush()
    return doc


async def validate_and_record_terms_acceptance(
    db: AsyncSession, user: User, terms_agreed: bool
) -> SubmissionTermsDocument:
    if not terms_agreed:
        raise ValueError("You must agree to the Terms of Submission")

    doc = await get_active_submission_terms(db)
    if not doc:
        doc = await ensure_submission_terms_seeded(db)

    user.submission_terms_version = doc.version
    return doc
