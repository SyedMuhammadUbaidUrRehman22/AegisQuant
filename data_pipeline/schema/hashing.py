"""Deterministic hashes for source and normalized market-data batches."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel

from data_pipeline.schema.domain import CanonicalBar, CorporateAction


def sha256_bytes(payload: bytes) -> str:
    """Return a lowercase SHA-256 digest."""

    return hashlib.sha256(payload).hexdigest()


def canonical_json_bytes(payload: Any) -> bytes:
    """Serialize JSON-compatible data with stable ordering and separators."""

    if isinstance(payload, BaseModel):
        payload = payload.model_dump(mode="json")
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def normalized_batch_sha256(
    bars: Iterable[CanonicalBar],
    actions: Iterable[CorporateAction],
) -> str:
    """Hash canonical values independently of ingestion timestamps and run IDs."""

    bar_payload = sorted(
        (bar.model_dump(mode="json") for bar in bars),
        key=lambda row: (row["instrument_id"], row["interval_code"], row["bar_start_at"]),
    )
    action_payload = sorted(
        (action.model_dump(mode="json") for action in actions),
        key=lambda row: (row["instrument_id"], row["effective_date"], row["action_type"]),
    )
    return sha256_bytes(canonical_json_bytes({"bars": bar_payload, "actions": action_payload}))
