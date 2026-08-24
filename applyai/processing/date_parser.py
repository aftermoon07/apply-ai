"""
Deterministic date parsing — zero LLM usage.

Uses dateutil.parser to handle a wide range of date string formats.
All successfully parsed dates are normalized to timezone-aware UTC ISO 8601 strings.

Policy:
  - If a date cannot be confidently parsed, preserve the original string and
    return a clear ParseStatus (FAILED) rather than inventing a date.
  - Never return a "default" date (e.g. today's date) when parsing fails.
  - Relative dates ("3 days ago", "posted today") are handled for common patterns.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum

logger = logging.getLogger(__name__)

try:
    from dateutil import parser as dateutil_parser
    from dateutil.relativedelta import relativedelta

    _DATEUTIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _DATEUTIL_AVAILABLE = False
    logger.warning("python-dateutil not available; date parsing will be limited")


# ── Parse status ──────────────────────────────────────────────────────────────


class ParseStatus(StrEnum):
    OK = "ok"               # Successfully parsed to UTC datetime
    RELATIVE = "relative"   # Parsed from relative expression ("3 days ago")
    PRESERVED = "preserved" # Could not parse; original string returned as-is
    EMPTY = "empty"         # Input was None or empty string


@dataclass
class DateParseResult:
    """Result of a date parse attempt."""

    status: ParseStatus
    iso_utc: str | None        # ISO 8601 UTC string if parsed successfully
    original: str | None       # Original input string
    error: str | None = None   # Error message if status is PRESERVED

    @property
    def value(self) -> str | None:
        """Return iso_utc if available, otherwise the original string."""
        return self.iso_utc if self.iso_utc else self.original


# ── Relative date patterns ────────────────────────────────────────────────────

# Matches: "3 days ago", "1 week ago", "2 months ago", "just now", "today", "yesterday"
_RELATIVE_PATTERNS: list[tuple[re.Pattern, callable]] = [
    (
        re.compile(r"just now|moments? ago", re.IGNORECASE),
        lambda _m, now: now,
    ),
    (
        re.compile(r"today", re.IGNORECASE),
        lambda _m, now: now.replace(hour=0, minute=0, second=0, microsecond=0),
    ),
    (
        re.compile(r"yesterday", re.IGNORECASE),
        lambda _m, now: (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0),
    ),
    (
        re.compile(r"(\d+)\s+day[s]?\s+ago", re.IGNORECASE),
        lambda m, now: now - timedelta(days=int(m.group(1))),
    ),
    (
        re.compile(r"(\d+)\s+week[s]?\s+ago", re.IGNORECASE),
        lambda m, now: now - timedelta(weeks=int(m.group(1))),
    ),
    (
        re.compile(r"(\d+)\s+month[s]?\s+ago", re.IGNORECASE),
        lambda m, now: now - timedelta(days=int(m.group(1)) * 30),
    ),
    (
        re.compile(r"(\d+)\s+hour[s]?\s+ago", re.IGNORECASE),
        lambda m, now: now - timedelta(hours=int(m.group(1))),
    ),
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc_iso(dt: datetime) -> str:
    """Convert a datetime to UTC ISO 8601 string."""
    if dt.tzinfo is None:
        # Treat naive datetimes as UTC
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


def _try_relative(text: str) -> datetime | None:
    """Try to parse a relative date expression. Returns UTC datetime or None."""
    now = _utcnow()
    for pattern, handler in _RELATIVE_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                return handler(match, now)
            except Exception:
                pass
    return None


def parse_date(date_str: str | None) -> DateParseResult:
    """
    Parse a date string to a UTC ISO 8601 string.

    Tries in order:
      1. Relative expression patterns ("3 days ago", "yesterday")
      2. dateutil.parser.parse for absolute dates

    Returns a DateParseResult with status indicating confidence level.
    If parsing fails, returns status=PRESERVED with the original string.
    """
    if not date_str or not date_str.strip():
        return DateParseResult(status=ParseStatus.EMPTY, iso_utc=None, original=date_str)

    text = date_str.strip()

    # 1. Try relative patterns first
    relative_dt = _try_relative(text)
    if relative_dt is not None:
        return DateParseResult(
            status=ParseStatus.RELATIVE,
            iso_utc=_to_utc_iso(relative_dt),
            original=text,
        )

    # 2. Try dateutil absolute parsing
    if _DATEUTIL_AVAILABLE:
        try:
            dt = dateutil_parser.parse(text, default=None)
            return DateParseResult(
                status=ParseStatus.OK,
                iso_utc=_to_utc_iso(dt),
                original=text,
            )
        except (ValueError, OverflowError) as exc:
            return DateParseResult(
                status=ParseStatus.PRESERVED,
                iso_utc=None,
                original=text,
                error=str(exc),
            )

    # dateutil not available
    return DateParseResult(
        status=ParseStatus.PRESERVED,
        iso_utc=None,
        original=text,
        error="dateutil not available",
    )


def parse_date_to_iso(date_str: str | None) -> str | None:
    """
    Convenience wrapper. Returns:
      - ISO 8601 UTC string if parsed successfully
      - Original string if parsing failed (preserved for traceability)
      - None if input is empty
    """
    result = parse_date(date_str)
    return result.value
