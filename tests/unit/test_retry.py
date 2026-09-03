"""Unit tests for bounded retry and error classification."""

import pytest

from data_pipeline.ingestion.errors import (
    DataQualityError,
    FailureCategory,
    RetryableProviderError,
    classify_error,
    is_retryable,
)
from data_pipeline.ingestion.retry import retry_call


def test_retry_uses_capped_exponential_full_jitter() -> None:
    calls = 0
    delays: list[float] = []

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RetryableProviderError("temporary")
        return "ok"

    result = retry_call(
        operation,
        max_attempts=3,
        base_seconds=2,
        cap_seconds=30,
        sleep=delays.append,
        random_value=lambda: 0.5,
    )

    assert result == "ok"
    assert calls == 3
    assert delays == [1.0, 2.0]


def test_nonretryable_error_is_not_retried() -> None:
    calls = 0

    def operation() -> None:
        nonlocal calls
        calls += 1
        raise DataQualityError("bad bar")

    with pytest.raises(DataQualityError):
        retry_call(operation, max_attempts=3, base_seconds=1, cap_seconds=3)

    assert calls == 1
    assert not is_retryable(DataQualityError("bad bar"))
    assert classify_error(DataQualityError("bad bar")) is FailureCategory.DATA_QUALITY
