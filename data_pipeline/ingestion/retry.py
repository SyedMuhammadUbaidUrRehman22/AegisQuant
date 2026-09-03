"""Bounded exponential retry support for transient provider failures."""

from __future__ import annotations

import random
import time
from collections.abc import Callable

from data_pipeline.ingestion.errors import is_retryable


def retry_call[T](
    operation: Callable[[], T],
    *,
    max_attempts: int,
    base_seconds: float,
    cap_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
    random_value: Callable[[], float] = random.random,
) -> T:
    """Execute an operation with capped exponential full-jitter retry."""

    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except Exception as error:
            if attempt == max_attempts or not is_retryable(error):
                raise
            maximum_delay = min(cap_seconds, base_seconds * (2 ** (attempt - 1)))
            sleep(maximum_delay * random_value())
    raise AssertionError("retry loop terminated without returning or raising")
