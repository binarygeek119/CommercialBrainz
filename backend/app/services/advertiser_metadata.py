"""Brand/advertiser metadata helpers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Advertiser, AdvertiserStatus

ADVERTISER_SCALAR_FIELDS = (
    "description",
    "website",
    "country",
    "founded_year",
    "industry",
    "headquarters",
    "parent_company",
    "wikipedia_url",
    "logo_url",
)

METADATA_JSON_FIELDS = ("aliases", "tagline", "social", "notes")

BRAND_METADATA_EDIT_KEYS = (
    "description",
    "website",
    "country",
    "founded_year",
    "industry",
    "headquarters",
    "parent_company",
    "wikipedia_url",
    *METADATA_JSON_FIELDS,
)


def advertiser_to_state(advertiser: Advertiser) -> dict:
    meta = advertiser.extra_data or {}
    state: dict = {
        "advertiser_id": str(advertiser.sbid),
        "name": advertiser.name,
        "description": advertiser.description,
        "website": advertiser.website,
        "country": advertiser.country,
        "founded_year": advertiser.founded_year,
        "industry": advertiser.industry,
        "headquarters": advertiser.headquarters,
        "parent_company": advertiser.parent_company,
        "wikipedia_url": advertiser.wikipedia_url,
        "logo_url": advertiser.logo_url,
        "aliases": meta.get("aliases") or [],
        "tagline": meta.get("tagline"),
        "social": meta.get("social") or {},
        "notes": meta.get("notes"),
    }
    return {k: v for k, v in state.items() if v not in (None, "", [], {})}


def advertiser_public_dict(advertiser: Advertiser) -> dict:
    return {
        "sbid": advertiser.sbid,
        "name": advertiser.name,
        "slug": advertiser.slug,
        "description": advertiser.description,
        "logo_url": advertiser.logo_url,
        "main_logo_id": advertiser.main_logo_id,
        "website": advertiser.website,
        "country": advertiser.country,
        "founded_year": advertiser.founded_year,
        "industry": advertiser.industry,
        "headquarters": advertiser.headquarters,
        "parent_company": advertiser.parent_company,
        "wikipedia_url": advertiser.wikipedia_url,
        "metadata": advertiser.extra_data or {},
        "external_ids": advertiser.external_ids or {},
        "status": advertiser.status.value,
        "created_at": advertiser.created_at,
        "updated_at": advertiser.updated_at,
    }


def apply_advertiser_state(advertiser: Advertiser, state: dict) -> None:
    from datetime import datetime, timezone

    meta = dict(advertiser.extra_data or {})
    meta_changed = False

    for key in METADATA_JSON_FIELDS:
        if key in state:
            value = state[key]
            if key == "aliases" and isinstance(value, list):
                meta[key] = [str(v).strip() for v in value if str(v).strip()]
            elif key == "social" and isinstance(value, dict):
                meta[key] = {str(k): str(v).strip() for k, v in value.items() if str(v).strip()}
            else:
                meta[key] = value
            meta_changed = True

    if meta_changed:
        advertiser.extra_data = meta

    for field in ADVERTISER_SCALAR_FIELDS:
        if field in state:
            setattr(advertiser, field, state[field])

    advertiser.updated_at = datetime.now(timezone.utc)


def metadata_snapshot_changed(before: dict, after: dict) -> bool:
    for key in BRAND_METADATA_EDIT_KEYS:
        if before.get(key) != after.get(key):
            return True
    return False


async def resolve_alias_links(
    db: AsyncSession,
    aliases: list[str],
    *,
    exclude_sbid: UUID | None = None,
) -> list[dict[str, str | UUID | None]]:
    cleaned = [str(alias).strip() for alias in aliases if str(alias).strip()]
    if not cleaned:
        return []

    result = await db.execute(
        select(Advertiser.sbid, Advertiser.name, Advertiser.extra_data).where(
            Advertiser.status == AdvertiserStatus.APPROVED
        )
    )

    by_name: dict[str, UUID] = {}
    by_alias: dict[str, UUID] = {}
    for sbid, name, extra in result.all():
        if exclude_sbid and sbid == exclude_sbid:
            continue
        by_name[name.strip().lower()] = sbid
        for alias in (extra or {}).get("aliases") or []:
            if isinstance(alias, str) and alias.strip():
                by_alias[alias.strip().lower()] = sbid

    links: list[dict[str, str | UUID | None]] = []
    for alias in cleaned:
        key = alias.lower()
        sbid = by_name.get(key) or by_alias.get(key)
        links.append({"name": alias, "sbid": sbid})
    return links
