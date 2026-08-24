"""
Deterministic salary extraction from text — zero LLM usage.

Uses conservative regex heuristics. Policy:
  - Never fabricate salary information.
  - Always preserve the original salary text alongside extracted values.
  - Return None for all numeric fields when extraction fails or is ambiguous.
  - Clearly indicate the confidence level of each extraction.

Supported formats:
  INR / ₹:
    ₹12–18 LPA
    ₹12 - 18 LPA
    12–18 LPA
    12 LPA
    ₹80,000–₹1,20,000 per month
    ₹80,000/month
    80000 - 120000 per month
    Rs. 12,00,000 – Rs. 18,00,000 per annum
    INR 12 LPA – INR 18 LPA

  USD / EUR / GBP:
    $120,000 – $160,000
    $120K - $160K per year

Notes:
  - LPA = Lakhs Per Annum (Indian convention). 1 LPA = 100,000 INR.
  - Numbers with commas (Indian notation: 1,00,000 or US notation: 100,000) are handled.
  - Ambiguous text is reported as ambiguous rather than guessed.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import StrEnum

logger = logging.getLogger(__name__)


# ── Data classes ──────────────────────────────────────────────────────────────


class SalaryConfidence(StrEnum):
    HIGH = "high"       # Clear numeric range with explicit currency and period
    MEDIUM = "medium"   # Numeric value found but period or currency inferred
    LOW = "low"         # Partial match; result may not be accurate
    FAILED = "failed"   # Could not extract; all numeric fields are None


@dataclass
class SalaryResult:
    """Result of a salary extraction attempt."""

    original: str | None         # Original text — always preserved
    salary_min: int | None       # In the base annual unit (INR per year)
    salary_max: int | None
    currency: str | None         # "INR" | "USD" | "EUR" | "GBP"
    period: str | None           # "annual" | "monthly" | "lpa"
    confidence: SalaryConfidence
    notes: str | None = None     # Human-readable extraction notes


# ── Currency symbols ──────────────────────────────────────────────────────────

_CURRENCY_SYMBOLS = {
    "₹": "INR", "Rs": "INR", "Rs.": "INR", "INR": "INR",
    "$": "USD", "USD": "USD",
    "€": "EUR", "EUR": "EUR",
    "£": "GBP", "GBP": "GBP",
}

_CURRENCY_PATTERN = r"(?:₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP)"

# ── Numeric patterns ───────────────────────────────────────────────────────────

# Matches: 12, 12.5, 12,00,000, 1,200,000
_NUM = r"[\d,]+(?:\.\d+)?"

# Period keywords
_PERIOD_ANNUAL = r"(?:per\s+ann?um|p\.?a\.?|annual(?:ly)?|per\s+year|yearly)"
_PERIOD_MONTHLY = r"(?:per\s+month|p\.?m\.?|monthly|/\s*month)"
_PERIOD_LPA = r"LPA|L\.P\.A\.|lakhs?\s+per\s+ann?um|lac(?:ks?)?\s+per\s+ann?um"

# ── Compiled patterns ──────────────────────────────────────────────────────────

# ₹12–18 LPA  |  12-18 LPA  |  INR 12 LPA - INR 18 LPA
_LPA_RANGE = re.compile(
    rf"(?:{_CURRENCY_PATTERN}\s*)?({_NUM})\s*[-–—to]+\s*(?:{_CURRENCY_PATTERN}\s*)?({_NUM})\s*(?:{_PERIOD_LPA})",
    re.IGNORECASE,
)

# ₹12 LPA  |  12 LPA
_LPA_SINGLE = re.compile(
    rf"(?:{_CURRENCY_PATTERN}\s*)?({_NUM})\s*(?:{_PERIOD_LPA})",
    re.IGNORECASE,
)

# ₹80,000–₹1,20,000 per month  |  80000 - 120000/month
_MONTHLY_RANGE = re.compile(
    rf"(?:{_CURRENCY_PATTERN})?\s*({_NUM})\s*[-–—to]+\s*(?:{_CURRENCY_PATTERN})?\s*({_NUM})\s*(?:{_PERIOD_MONTHLY})",
    re.IGNORECASE,
)

# ₹80,000 per month
_MONTHLY_SINGLE = re.compile(
    rf"(?:{_CURRENCY_PATTERN})?\s*({_NUM})\s*(?:{_PERIOD_MONTHLY})",
    re.IGNORECASE,
)

# $120,000–$160,000  |  $120K–$160K
_ANNUAL_RANGE = re.compile(
    rf"({_CURRENCY_PATTERN})\s*({_NUM}[Kk]?)\s*[-–—to]+\s*(?:{_CURRENCY_PATTERN})?\s*({_NUM}[Kk]?)\s*(?:{_PERIOD_ANNUAL})?",
    re.IGNORECASE,
)

# $120,000
_ANNUAL_SINGLE = re.compile(
    rf"({_CURRENCY_PATTERN})\s*({_NUM}[Kk]?)\s*(?:{_PERIOD_ANNUAL})?",
    re.IGNORECASE,
)


# ── Helper functions ───────────────────────────────────────────────────────────


def _parse_number(text: str) -> float:
    """Parse a number string, handling commas and K suffix."""
    text = text.strip().replace(",", "")
    if text.upper().endswith("K"):
        return float(text[:-1]) * 1000
    return float(text)


def _detect_currency(text: str) -> str:
    """Detect currency from text. Defaults to INR for LPA-style amounts."""
    for symbol, currency in _CURRENCY_SYMBOLS.items():
        if symbol in text:
            return currency
    return "INR"


# ── Main extractor ─────────────────────────────────────────────────────────────


def extract_salary(text: str | None) -> SalaryResult:
    """
    Extract salary information from a raw salary text string.

    Returns a SalaryResult with:
      - original: always preserved
      - salary_min, salary_max: annual amounts in the detected currency (None if failed)
      - currency: detected currency code
      - period: "lpa" | "monthly" | "annual" | None
      - confidence: HIGH | MEDIUM | LOW | FAILED

    All amounts are returned in the natural unit of the detected period —
    NOT converted. The scoring layer is responsible for unit normalization.
    """
    if not text or not text.strip():
        return SalaryResult(
            original=text, salary_min=None, salary_max=None,
            currency=None, period=None, confidence=SalaryConfidence.FAILED,
            notes="Empty input",
        )

    raw = text.strip()
    currency = _detect_currency(raw)

    # ── 1. LPA range (highest priority for Indian job market) ─────────────────
    m = _LPA_RANGE.search(raw)
    if m:
        try:
            lo = _parse_number(m.group(1))
            hi = _parse_number(m.group(2))
            return SalaryResult(
                original=raw,
                salary_min=int(lo * 100_000),
                salary_max=int(hi * 100_000),
                currency="INR",
                period="lpa",
                confidence=SalaryConfidence.HIGH,
                notes=f"LPA range: {lo}–{hi} LPA",
            )
        except (ValueError, IndexError):
            pass

    # ── 2. LPA single ────────────────────────────────────────────────────────
    m = _LPA_SINGLE.search(raw)
    if m:
        try:
            val = _parse_number(m.group(1))
            annual = int(val * 100_000)
            return SalaryResult(
                original=raw,
                salary_min=annual,
                salary_max=annual,
                currency="INR",
                period="lpa",
                confidence=SalaryConfidence.HIGH,
                notes=f"LPA single: {val} LPA",
            )
        except (ValueError, IndexError):
            pass

    # ── 3. Monthly range ──────────────────────────────────────────────────────
    m = _MONTHLY_RANGE.search(raw)
    if m:
        try:
            lo = _parse_number(m.group(1))
            hi = _parse_number(m.group(2))
            return SalaryResult(
                original=raw,
                salary_min=int(lo),
                salary_max=int(hi),
                currency=currency,
                period="monthly",
                confidence=SalaryConfidence.HIGH,
                notes=f"Monthly range: {int(lo):,}–{int(hi):,}/month",
            )
        except (ValueError, IndexError):
            pass

    # ── 4. Monthly single ─────────────────────────────────────────────────────
    m = _MONTHLY_SINGLE.search(raw)
    if m:
        try:
            val = _parse_number(m.group(1))
            return SalaryResult(
                original=raw,
                salary_min=int(val),
                salary_max=int(val),
                currency=currency,
                period="monthly",
                confidence=SalaryConfidence.MEDIUM,
                notes=f"Monthly single: {int(val):,}/month",
            )
        except (ValueError, IndexError):
            pass

    # ── 5. Annual range (USD/EUR/GBP or explicit per annum) ──────────────────
    m = _ANNUAL_RANGE.search(raw)
    if m:
        try:
            sym, lo_s, hi_s = m.group(1), m.group(2), m.group(3)
            currency = _CURRENCY_SYMBOLS.get(sym.strip(), "INR")
            lo = _parse_number(lo_s)
            hi = _parse_number(hi_s)
            return SalaryResult(
                original=raw,
                salary_min=int(lo),
                salary_max=int(hi),
                currency=currency,
                period="annual",
                confidence=SalaryConfidence.HIGH,
                notes=f"Annual range: {int(lo):,}–{int(hi):,}",
            )
        except (ValueError, IndexError):
            pass

    # ── 6. Annual single ──────────────────────────────────────────────────────
    m = _ANNUAL_SINGLE.search(raw)
    if m:
        try:
            sym, val_s = m.group(1), m.group(2)
            currency = _CURRENCY_SYMBOLS.get(sym.strip(), "INR")
            val = _parse_number(val_s)
            return SalaryResult(
                original=raw,
                salary_min=int(val),
                salary_max=int(val),
                currency=currency,
                period="annual",
                confidence=SalaryConfidence.LOW,
                notes=f"Annual single (low confidence): {int(val):,}",
            )
        except (ValueError, IndexError):
            pass

    # ── Nothing matched ───────────────────────────────────────────────────────
    return SalaryResult(
        original=raw,
        salary_min=None,
        salary_max=None,
        currency=None,
        period=None,
        confidence=SalaryConfidence.FAILED,
        notes="No salary pattern matched",
    )
