"""Immutable, content-addressed provider-response snapshots."""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from data_pipeline.schema import SnapshotReference, SourceBatch
from data_pipeline.schema.hashing import canonical_json_bytes, sha256_bytes

SNAPSHOT_FORMAT_VERSION = 1


def serialize_source_batch(batch: SourceBatch) -> bytes:
    """Serialize a source batch deterministically before compression."""

    payload = {
        "format_version": SNAPSHOT_FORMAT_VERSION,
        "source_name": batch.source_name,
        "source_symbol": batch.source_symbol,
        "interval_code": batch.interval_code.value,
        "requested_start": batch.requested_start.isoformat(),
        "requested_end": batch.requested_end.isoformat(),
        "fetched_at": batch.fetched_at.isoformat(),
        "columns": list(batch.columns),
        "rows": list(batch.rows),
        "metadata": batch.metadata,
    }
    return canonical_json_bytes(payload)


class SnapshotStore:
    """Write immutable response snapshots beneath the configured raw-data root."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def write(self, batch: SourceBatch) -> SnapshotReference:
        """Atomically persist one gzip snapshot and return its content identity."""

        serialized = serialize_source_batch(batch)
        digest = sha256_bytes(serialized)
        relative = Path(batch.source_name) / f"v{SNAPSHOT_FORMAT_VERSION}" / digest[:2]
        relative /= f"{digest}.json.gz"
        destination = self._root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        compressed = gzip.compress(serialized, compresslevel=9, mtime=0)

        if destination.exists():
            existing = gzip.decompress(destination.read_bytes())
            if sha256_bytes(existing) != digest:
                raise OSError(f"Snapshot digest collision at {destination}")
        else:
            with NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
                temporary.write(compressed)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            try:
                temporary_path.replace(destination)
            finally:
                temporary_path.unlink(missing_ok=True)

        return SnapshotReference(relative_path=relative.as_posix(), sha256=digest)

    def read(self, reference: SnapshotReference) -> dict[str, object]:
        """Read and verify a stored snapshot."""

        serialized = gzip.decompress((self._root / reference.relative_path).read_bytes())
        if sha256_bytes(serialized) != reference.sha256:
            raise OSError("Snapshot checksum verification failed")
        value: object = json.loads(serialized)
        if not isinstance(value, dict):
            raise ValueError("Snapshot payload must be a JSON object")
        return value
