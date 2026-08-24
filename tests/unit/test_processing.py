import pytest
from applyai.processing.url_normalizer import normalize_url, urls_are_equivalent
from applyai.processing.date_parser import parse_date, parse_date_to_iso, ParseStatus
from applyai.processing.salary_extractor import extract_salary, SalaryConfidence
from applyai.schemas.job import NormalizedJob
from applyai.processing.deduplicator import build_content_fingerprint, compute_content_hash

def test_url_normalizer_trailing_slash():
    assert normalize_url("https://example.com/job/") == "https://example.com/job"
    assert normalize_url("https://example.com/") == "https://example.com/"

def test_url_normalizer_fragments():
    assert normalize_url("https://example.com/job#section1") == "https://example.com/job"

def test_url_normalizer_tracking_parameters():
    url = "https://example.com/job?utm_source=linkedin&utm_campaign=xyz&ref=123&fbclid=abc"
    # ref is safe to remove in some contexts but we only remove known tracking ones
    # let's check what TRACKING_PARAMS has: utm_*, fbclid, etc.
    res = normalize_url(url)
    # wait, ref is in TRACKING_PARAMS? We can check.
    assert "utm_" not in res
    assert "fbclid" not in res

def test_url_normalizer_preserves_query():
    url = "https://example.com/job?id=123&v=2"
    assert normalize_url(url) == "https://example.com/job?id=123&v=2"

def test_url_normalizer_equivalent():
    assert urls_are_equivalent("https://test.com/a?utm_source=b", "https://test.com/a#hash")

def test_date_parser_formats():
    res = parse_date("2024-01-01T12:00:00Z")
    assert res.status == ParseStatus.OK
    assert res.iso_utc == "2024-01-01T12:00:00+00:00"

def test_date_parser_relative():
    res = parse_date("3 days ago")
    assert res.status == ParseStatus.RELATIVE
    assert res.iso_utc is not None

def test_date_parser_invalid():
    res = parse_date("some unknown date")
    assert res.status == ParseStatus.PRESERVED
    assert res.original == "some unknown date"

def test_salary_extractor_inr_range():
    res = extract_salary("₹12–18 LPA")
    assert res.confidence == SalaryConfidence.HIGH
    assert res.salary_min == 1200000
    assert res.salary_max == 1800000
    assert res.currency == "INR"
    assert res.period == "lpa"

def test_salary_extractor_monthly():
    res = extract_salary("₹80,000 per month")
    assert res.confidence == SalaryConfidence.MEDIUM
    assert res.salary_min == 80000
    assert res.salary_max == 80000
    assert res.currency == "INR"
    assert res.period == "monthly"

def test_salary_extractor_usd_range():
    res = extract_salary("$120K - $160K per year")
    assert res.confidence == SalaryConfidence.HIGH
    assert res.salary_min == 120000
    assert res.salary_max == 160000
    assert res.currency == "USD"
    assert res.period == "annual"

def test_salary_extractor_missing():
    res = extract_salary("Competitive salary")
    assert res.confidence == SalaryConfidence.FAILED
    assert res.salary_min is None
    assert res.original == "Competitive salary"

def test_deduplicator():
    job1 = NormalizedJob(
        source="test",
        job_url="https://test.com/job/1",
        content_hash="dummy",
        date_discovered="2024-01-01T00:00:00Z"
    )
    job2 = NormalizedJob(
        source="test",
        job_url="https://test.com/job/1",
        content_hash="dummy2",
        date_discovered="2024-01-02T00:00:00Z"
    )
    assert build_content_fingerprint(job1) == build_content_fingerprint(job2)
    assert compute_content_hash(job1) == compute_content_hash(job2)

def test_deduplicator_source_id():
    job1 = NormalizedJob(
        source="test",
        source_job_id="123",
        content_hash="dummy",
        date_discovered="2024-01-01T00:00:00Z"
    )
    job2 = NormalizedJob(
        source="test",
        source_job_id="123",
        content_hash="dummy2",
        date_discovered="2024-01-02T00:00:00Z"
    )
    assert compute_content_hash(job1) == compute_content_hash(job2)

def test_deduplicator_content_fallback():
    job1 = NormalizedJob(
        source="test",
        company="Acme",
        role="SWE",
        location="Remote",
        job_description="Description here...",
        content_hash="dummy",
        date_discovered="2024-01-01T00:00:00Z"
    )
    job2 = NormalizedJob(
        source="test",
        company="Acme",
        role="SWE",
        location="Remote",
        job_description="Description here...",
        content_hash="dummy2",
        date_discovered="2024-01-02T00:00:00Z"
    )
    assert compute_content_hash(job1) == compute_content_hash(job2)

def test_deduplicator_different_jobs():
    job1 = NormalizedJob(
        source="test",
        company="Acme",
        role="SWE",
        content_hash="dummy",
        date_discovered="2024-01-01T00:00:00Z"
    )
    job2 = NormalizedJob(
        source="test",
        company="Other",
        role="SWE",
        content_hash="dummy2",
        date_discovered="2024-01-02T00:00:00Z"
    )
    assert compute_content_hash(job1) != compute_content_hash(job2)
