"""Deterministic hashes for source and normalized market-data batches."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from data_pipeline.schema.domain import CanonicalBar, CorporateAction


def _decimal_text(value: Decimal) -> str:
    """Return one exponent-independent representation for equal decimal values."""

    return format(value.normalize(), "f")


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
    """Hash normalized economic content independently of mutable quality metadata."""

    bar_payload = sorted(
        (
            {
                "instrument_id": bar.instrument_id,
                "interval_code": bar.interval_code.value,
                "session_date": bar.session_date.isoformat(),
                "bar_start_at": bar.bar_start_at.isoformat(),
                "bar_end_at": bar.bar_end_at.isoformat(),
                "open": _decimal_text(bar.open),
                "high": _decimal_text(bar.high),
                "low": _decimal_text(bar.low),
                "close": _decimal_text(bar.close),
                "adjusted_close": _decimal_text(bar.adjusted_close),
                "volume": bar.volume,
                "source_name": bar.source_name,
            }
            for bar in bars
        ),
        key=lambda row: (row["instrument_id"], row["interval_code"], row["bar_start_at"]),
    )
    action_payload = sorted(
        (
            {
                "instrument_id": action.instrument_id,
                "effective_date": action.effective_date.isoformat(),
                "action_type": action.action_type.value,
                "action_value": _decimal_text(action.action_value),
                "currency": action.currency,
                "source_name": action.source_name,
                "active": action.active,
            }
            for action in actions
        ),
        key=lambda row: (row["instrument_id"], row["effective_date"], row["action_type"]),
    )
    return sha256_bytes(canonical_json_bytes({"bars": bar_payload, "actions": action_payload}))
