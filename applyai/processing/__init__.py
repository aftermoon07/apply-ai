"""applyai.processing package — deterministic, zero-LLM preprocessing."""

from applyai.processing.deduplicator import (
    DeduplicationKeys,
    build_content_fingerprint,
    compute_content_hash,
    compute_hash_from_string,
)
from applyai.processing.url_normalizer import normalize_url, urls_are_equivalent
from applyai.processing.date_parser import DateParseResult, ParseStatus, parse_date, parse_date_to_iso
from applyai.processing.salary_extractor import SalaryConfidence, SalaryResult, extract_salary
from applyai.processing.normalizer import JobNormalizer

__all__ = [
    # Deduplication
    "DeduplicationKeys",
    "build_content_fingerprint",
    "compute_content_hash",
    "compute_hash_from_string",
    # URL
    "normalize_url",
    "urls_are_equivalent",
    # Date
    "DateParseResult",
    "ParseStatus",
    "parse_date",
    "parse_date_to_iso",
    # Salary
    "SalaryConfidence",
    "SalaryResult",
    "extract_salary",
    # Normalizer
    "JobNormalizer",
]
