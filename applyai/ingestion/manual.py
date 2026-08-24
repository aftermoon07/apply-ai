"""
Manual ingestion adapter.

Handles jobs provided directly by the user as plain text (paste or file).

Source ID: "manual"
Permitted method: manual_paste | file_import

The user provides raw job posting text. This adapter wraps it in a RawJobInput
and sets sensible defaults. No parsing of the JD is done here — that is Phase 3
(LLM Job Normalizer agent).

For Phase 2, the text is stored as-is in job_description, and company/role are
extracted only if explicitly provided by the caller.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from applyai.ingestion.base import JobSource
from applyai.schemas.job import RawJobInput


class ManualSource(JobSource):
    """
    Ingests a single job from plain text (paste or file).

    Usage:
        source = ManualSource()
        for raw in source.parse(text):
            ...
    """

    source_id = "manual"
    permitted_method = "manual_paste"

    def parse(
        self,
        data: str,
        *,
        company: str | None = None,
        role: str | None = None,
        location: str | None = None,
        job_url: str | None = None,
        source_url: str | None = None,
        metadata: dict | None = None,
    ) -> Iterator[RawJobInput]:
        """
        Parse a plain-text job description into a RawJobInput.

        Args:
            data: The raw job description text.
            company: Optional company name (if known upfront).
            role: Optional job title (if known upfront).
            location: Optional location.
            job_url: Optional URL of the job posting.
            source_url: Optional URL where the text was found.
            metadata: Optional extra key-value pairs.

        Yields:
            A single RawJobInput.
        """
        text = data.strip() if isinstance(data, str) else ""

        if not text:
            # Yield nothing — empty input is logged by the caller
            return

        yield RawJobInput(
            source=self.source_id,
            company=company,
            role=role,
            location=location,
            job_description=text,
            raw_text=text,
            job_url=job_url,
            source_url=source_url,
            date_discovered=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )


def read_text_from_file(path: Path | str) -> str:
    """
    Read text from a file path. Supports .txt and other plain-text formats.

    Returns the file contents as a string.
    Raises FileNotFoundError if the file does not exist.
    Raises ValueError if the file is empty.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"File is empty: {p}")
    return text


def read_text_from_stdin() -> str:
    """
    Read job description text from stdin.

    Returns the stdin content as a string.
    Raises ValueError if stdin is empty or a TTY.
    """
    if sys.stdin.isatty():
        raise ValueError(
            "No text provided via stdin. "
            "Pipe text with: cat job.txt | applyai ingest --text --source manual"
        )
    text = sys.stdin.read().strip()
    if not text:
        raise ValueError("Stdin was empty.")
    return text
