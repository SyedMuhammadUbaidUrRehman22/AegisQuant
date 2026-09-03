"""Canonical market-data quality validation."""

from data_pipeline.quality_checks.reporting import write_batch_report
from data_pipeline.quality_checks.validation import validate_batch

__all__ = ["validate_batch", "write_batch_report"]
