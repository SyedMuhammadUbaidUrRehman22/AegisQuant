"""Stage 1 ingestion failure taxonomy and retry decisions."""

from __future__ import annotations

from enum import StrEnum


class FailureCategory(StrEnum):
    """Stable categories recorded by ingestion runs."""

    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"
    DATA_QUALITY = "data_quality"
    DATABASE_INTEGRITY = "database_integrity"
    OPERATIONAL = "operational"


class IngestionError(Exception):
    """Base exception carrying a stable failure category."""

    category = FailureCategory.OPERATIONAL


class RetryableProviderError(IngestionError):
    """A transient provider or transport failure eligible for bounded retry."""

    category = FailureCategory.RETRYABLE


class NonRetryableProviderError(IngestionError):
    """A permanent provider request or response failure."""

    category = FailureCategory.NON_RETRYABLE


class DataQualityError(IngestionError):
    """Canonical input failed a release-blocking quality rule."""

    category = FailureCategory.DATA_QUALITY


class DatabaseIntegrityError(IngestionError):
    """The database rejected data that violated a canonical invariant."""

    category = FailureCategory.DATABASE_INTEGRITY


class OperationalError(IngestionError):
    """Local configuration, filesystem, or runtime operation failed."""

    category = FailureCategory.OPERATIONAL


def is_retryable(error: BaseException) -> bool:
    """Return whether an exception is safe to retry at the provider boundary."""

    if isinstance(error, RetryableProviderError):
        return True
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True
    return False


def classify_error(error: BaseException) -> FailureCategory:
    """Classify known errors without exposing provider-specific exception text."""

    if isinstance(error, IngestionError):
        return error.category
    if isinstance(error, (TimeoutError, ConnectionError)):
        return FailureCategory.RETRYABLE
    return FailureCategory.OPERATIONAL
