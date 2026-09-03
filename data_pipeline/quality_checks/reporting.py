"""Deterministic JSON quality-report artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from data_pipeline.schema import BatchIngestionResult


def write_batch_report(result: BatchIngestionResult, directory: Path) -> Path:
    """Write one batch result without credentials or database connection details."""

    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{result.batch_id}.json"
    destination.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination
