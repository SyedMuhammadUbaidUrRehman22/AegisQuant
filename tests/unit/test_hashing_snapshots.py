"""Unit tests for stable canonical hashes and immutable source snapshots."""

import gzip
from datetime import date
from decimal import Decimal

import pytest

from data_pipeline.ingestion.snapshots import SnapshotStore
from data_pipeline.schema import SnapshotReference
from data_pipeline.schema.hashing import normalized_batch_sha256, sha256_bytes
from tests.factories import canonical_bar, source_batch, source_row


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


def test_snapshot_read_rejects_corrupted_content(tmp_path: object) -> None:
    from pathlib import Path

    root = Path(str(tmp_path))
    reference = SnapshotReference(relative_path="bad.json.gz", sha256="0" * 64)
    (root / reference.relative_path).write_bytes(gzip.compress(b"[]", mtime=0))

    with pytest.raises(OSError, match="checksum verification failed"):
        SnapshotStore(root).read(reference)


def test_normalized_hash_tracks_economic_content_not_quality_metadata() -> None:
    baseline = canonical_bar()
    baseline_hash = normalized_batch_sha256((baseline,), ())

    assert normalized_batch_sha256((baseline,), ()) == baseline_hash
    assert normalized_batch_sha256((canonical_bar(close="100"),), ()) != baseline_hash
    assert (
        normalized_batch_sha256((canonical_bar(quality_flags=("price_jump",)),), ())
        == baseline_hash
    )
    assert normalized_batch_sha256((canonical_bar(contract_version=2),), ()) == baseline_hash
    assert (
        normalized_batch_sha256(
            (canonical_bar().model_copy(update={"open": Decimal("100.0000")}),), ()
        )
        == baseline_hash
    )
