"""Regression tests for source-fallback provenance scope."""

from pathlib import Path

from data_pipeline.ingestion.service import _source_digest


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_source_digest_tracks_runtime_but_not_migrations(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", "project")
    _write(tmp_path / "constraints.lock", "constraints")
    _write(tmp_path / "config" / "settings.py", "settings")
    _write(tmp_path / "data_pipeline" / "service.py", "runtime-v1")
    _write(tmp_path / "infra" / "migrations" / "versions" / "revision.py", "migration-v1")
    baseline = _source_digest(tmp_path)

    _write(tmp_path / "infra" / "migrations" / "versions" / "revision.py", "migration-v2")
    assert _source_digest(tmp_path) == baseline

    _write(tmp_path / "data_pipeline" / "service.py", "runtime-v2")
    assert _source_digest(tmp_path) != baseline
