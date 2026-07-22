"""Holiday date_text parsing (best-effort)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_MDY = re.compile(
    r"^\s*(?P<month>\d{1,2})[/-](?P<day>\d{1,2})(?:[/-](?P<year>\d{2,4}))?\s*$"
)
_NAME_YEAR = re.compile(
    r"^\s*(?P<name>.+?)\s*[-–—]\s*(?P<year>\d{4})\s*$"
)
_YEAR_ONLY = re.compile(r"^\s*(?P<year>\d{4})\s*$")


@dataclass
class ParsedHolidayDate:
    date_text: str
    year: int | None = None
    month: int | None = None
    day: int | None = None


def _normalize_year(raw: str | None) -> int | None:
    if not raw:
        return None
    year = int(raw)
    if year < 100:
        year += 1900 if year >= 70 else 2000
    if year < 1800 or year > 2200:
        return None
    return year


def parse_holiday_date_text(date_text: str | None) -> ParsedHolidayDate:
    """Parse free-text holiday dates into optional year/month/day.

    Accepted examples: 10/31/1999, 10/31, Halloween - 1999, Halloween, 2002.
    """
    text = (date_text or "").strip()
    result = ParsedHolidayDate(date_text=text or None)  # type: ignore[arg-type]
    if not text:
        result.date_text = None
        return result

    mdy = _MDY.match(text)
    if mdy:
        month = int(mdy.group("month"))
        day = int(mdy.group("day"))
        if 1 <= month <= 12 and 1 <= day <= 31:
            result.month = month
            result.day = day
            result.year = _normalize_year(mdy.group("year"))
        return result

    named = _NAME_YEAR.match(text)
    if named:
        result.year = _normalize_year(named.group("year"))
        return result

    year_only = _YEAR_ONLY.match(text)
    if year_only:
        result.year = _normalize_year(year_only.group("year"))
        return result

    return result
