"""applyai.ingestion package — job source adapters."""

from applyai.ingestion.base import AsyncJobSource, JobSource
from applyai.ingestion.manual import ManualSource, read_text_from_file, read_text_from_stdin
from applyai.ingestion.json_file import JsonFileSource

__all__ = [
    "JobSource",
    "AsyncJobSource",
    "ManualSource",
    "JsonFileSource",
    "read_text_from_file",
    "read_text_from_stdin",
]
