"""Independent Stage 1 validation tools that never feed canonical persistence."""

from data_pipeline.validation.second_source import compare_alpha_vantage

__all__ = ["compare_alpha_vantage"]
