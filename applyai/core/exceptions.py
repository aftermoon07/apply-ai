"""Custom exception hierarchy for ApplyAI."""


class ApplyAIError(Exception):
    """Base exception for all ApplyAI errors."""


class ConfigError(ApplyAIError):
    """Raised when configuration is missing, invalid, or inconsistent."""


class ProviderError(ApplyAIError):
    """Raised when an AI provider call fails after retries."""


class ProviderNotConfiguredError(ProviderError):
    """Raised when an AI provider is referenced but not configured."""


class ModelValidationError(ProviderError):
    """Raised when a configured model identifier is rejected by the provider."""


class CandidateProfileError(ApplyAIError):
    """Raised when the candidate profile is missing or fails validation."""


class CandidateProfileIncompleteError(CandidateProfileError):
    """Raised when required profile fields are absent."""


class JobIngestionError(ApplyAIError):
    """Raised when a job cannot be ingested or parsed."""


class DuplicateJobError(JobIngestionError):
    """Raised when a job with the same content hash already exists."""


class StorageError(ApplyAIError):
    """Raised on database access failures."""


class PipelineError(ApplyAIError):
    """Raised when the analysis/scoring pipeline encounters an unrecoverable error."""
