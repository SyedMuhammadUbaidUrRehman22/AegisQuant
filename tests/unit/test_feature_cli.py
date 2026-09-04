"""Network-free Stage 2 CLI contract tests."""

from datetime import UTC, datetime
from typing import Any

import pytest

from feature_engineering import cli


def test_cli_requires_explicit_timezone_aware_as_of() -> None:
    with pytest.raises(SystemExit):
        cli.main(["--as-of", "2026-09-04T21:00:00"])


def test_cli_materializes_with_explicit_cutoff(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    disposed = False

    class EngineStub:
        def dispose(self) -> None:
            nonlocal disposed
            disposed = True

    engine = EngineStub()
    observed: dict[str, object] = {}
    monkeypatch.setattr(cli, "load_settings", lambda: _SettingsStub())
    monkeypatch.setattr(cli, "create_engine", lambda *args, **kwargs: engine)

    def materialize(engine_argument: object, *, as_of: datetime) -> tuple[object, ...]:
        observed.update(engine=engine_argument, as_of=as_of)
        return ()

    monkeypatch.setattr(cli, "materialize_features", materialize)

    assert cli.main(["--as-of", "2026-09-04T21:00:00Z"]) == 0
    assert observed == {"engine": engine, "as_of": datetime(2026, 9, 4, 21, tzinfo=UTC)}
    assert disposed
    assert "materialized=0" in capsys.readouterr().out


class _DatabaseStub:
    def sqlalchemy_url(self) -> str:
        return "postgresql+psycopg://test"


class _SettingsStub:
    database = _DatabaseStub()
