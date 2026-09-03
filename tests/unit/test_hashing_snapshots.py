"""Unit tests for stable canonical hashes and immutable source snapshots."""

import gzip
from datetime import date

from data_pipeline.ingestion.snapshots import SnapshotStore
from data_pipeline.schema.hashing import sha256_bytes
from tests.factories import source_batch, source_row


def test_snapshot_is_content_addressed_and_idempotent(tmp_path: object) -> None:
    from pathlib import Path

    root = Path(str(tmp_path))
    batch = source_batch((source_row(date(2024, 1, 2)),))
    store = SnapshotStore(root)

    first = store.write(batch)
    second = store.write(batch)
    payload = gzip.decompress((root / first.relative_path).read_bytes())

    assert first == second
    assert sha256_bytes(payload) == first.sha256
    assert store.read(first)["source_symbol"] == "SPY"
