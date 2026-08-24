"""
Abstract base class for all job source adapters.

Architecture contract:
  - Each adapter is responsible for ONE source (Naukri, LinkedIn, manual paste, etc.)
  - The adapter's sole job is to convert source-specific data into RawJobInput objects.
  - The adapter does NOT normalize, deduplicate, or persist.
  - Normalization and persistence are always handled by the pipeline (JobService).
  - This separation ensures future sources can plug in without touching downstream logic.

Adapter requirements:
  - Must set `source_id` as a class-level constant (machine-readable, lowercase).
  - Must set `permitted_method` documenting how data is accessed.
  - Must implement `parse()` to yield RawJobInput instances from source-specific data.
  - Must NOT make undisclosed external HTTP calls.
  - Must NOT require an LLM API key.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator, Iterator

from applyai.schemas.job import RawJobInput


class JobSource(ABC):
    """
    Abstract base class for all job ingestion adapters.

    Each subclass represents one job source. The adapter produces RawJobInput
    objects; the pipeline (JobService) handles everything downstream.
    """

    #: Machine-readable source identifier. Must be lowercase, no spaces.
    #: Used as the `source` field in Job records. Must be globally unique.
    source_id: str

    #: How this source obtains data. Determines what is permissible.
    #: Allowed values:
    #:   "manual_paste"   — user copies and pastes text directly
    #:   "file_import"    — user provides a local file (txt/json/pdf)
    #:   "official_api"   — uses an officially documented public API
    #:   "rss"            — reads a publicly available RSS/Atom feed
    #:   "json_export"    — reads a JSON export from a platform
    #:
    #: NOT allowed: headless_browser, session_hijack, captcha_bypass
    permitted_method: str

    @abstractmethod
    def parse(self, data: object) -> Iterator[RawJobInput]:
        """
        Parse source-specific data into RawJobInput instances.

        Args:
            data: Source-specific input (str, dict, Path, etc.)

        Yields:
            RawJobInput for each discovered job.
        """
        ...

    @property
    def name(self) -> str:
        """Human-readable source name (defaults to source_id)."""
        return self.source_id


class AsyncJobSource(ABC):
    """
    Async variant for sources that require async I/O (e.g. official APIs).

    Same contract as JobSource but uses async generators.
    """

    source_id: str
    permitted_method: str

    @abstractmethod
    async def parse(self, data: object) -> AsyncIterator[RawJobInput]:
        """Async generator yielding RawJobInput instances."""
        ...
        yield  # type: ignore[misc]  # ensure it's a generator
