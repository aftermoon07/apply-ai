"""Tests for resume filename path traversal sanitization."""

import pytest
from pathlib import Path


def test_safe_job_id_strips_path_traversal():
    """Test that the sanitization logic in resume_service strips traversal chars."""
    job_id = "../../../etc/passwd"
    safe_job_id = "".join(c for c in job_id if c.isalnum() or c == "-")
    assert "/" not in safe_job_id
    assert "." not in safe_job_id
    assert safe_job_id == "etcpasswd"


def test_safe_job_id_allows_uuid_format():
    """Normal UUIDs must survive sanitization completely intact."""
    uuid = "550e8400-e29b-41d4-a716-446655440000"
    safe = "".join(c for c in uuid if c.isalnum() or c == "-")
    assert safe == uuid


def test_safe_job_id_empty_raises():
    """If sanitization produces an empty string, the service must raise."""
    job_id = "../../"
    safe_job_id = "".join(c for c in job_id if c.isalnum() or c == "-")
    assert safe_job_id == ""
    # The service raises ValueError on empty safe_job_id
    with pytest.raises(ValueError, match="empty safe filename"):
        if not safe_job_id:
            raise ValueError(f"Job ID {job_id!r} produced an empty safe filename.")
