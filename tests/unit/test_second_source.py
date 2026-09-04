"""Deterministic unit tests for read-only Alpha Vantage validation."""

from __future__ import annotations

import io
import json
from datetime import date
from decimal import Decimal
from urllib.error import HTTPError

import pytest

from data_pipeline.validation import second_source


class RepositoryStub:
    def __init__(self, closes: dict[date, Decimal]) -> None:
        self._closes = closes

    def bars_for_symbol(
        self, canonical_symbol: str, start_date: date, end_date: date
    ) -> tuple[dict[str, object], ...]:
        del canonical_symbol, start_date, end_date
        return tuple(
            {"session_date": session, "close": close} for session, close in self._closes.items()
        )


def _payload(closes: dict[str, object]) -> io.BytesIO:
    rows = {session: {"4. close": close} for session, close in closes.items()}
    return io.BytesIO(json.dumps({"Time Series (Daily)": rows}).encode())


def _five_closes(value: str = "100") -> dict[str, object]:
    return {f"2024-01-0{day}": value for day in range(2, 7)}


def _canonical(value: str = "100") -> dict[date, Decimal]:
    return {date(2024, 1, day): Decimal(value) for day in range(2, 7)}


def test_successful_comparison_and_tolerance_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(second_source, "urlopen", lambda *args, **kwargs: _payload(_five_closes()))
    result = second_source.compare_alpha_vantage(
        RepositoryStub(_canonical("100.01")),  # type: ignore[arg-type]
        ("SPY",),
        api_key="test-key",
        as_of=date(2024, 1, 6),
        relative_tolerance=Decimal("0.0001"),
    )

    assert result["passed"] is True
    assert result["matches"] == 5
    assert result["mismatches"] == 0


def test_tolerance_rejects_larger_difference(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(second_source, "urlopen", lambda *args, **kwargs: _payload(_five_closes()))
    result = second_source.compare_alpha_vantage(
        RepositoryStub(_canonical("100.02")),  # type: ignore[arg-type]
        ("SPY",),
        api_key="test-key",
        as_of=date(2024, 1, 6),
        relative_tolerance=Decimal("0.0001"),
    )
    assert result["passed"] is False
    assert result["mismatches"] == 5


@pytest.mark.parametrize("secondary", [{}, {"2024-01-02": "100"}])
def test_empty_or_insufficient_overlap_fails(
    monkeypatch: pytest.MonkeyPatch, secondary: dict[str, object]
) -> None:
    monkeypatch.setattr(second_source, "urlopen", lambda *args, **kwargs: _payload(secondary))
    result = second_source.compare_alpha_vantage(
        RepositoryStub(_canonical()),  # type: ignore[arg-type]
        ("SPY",),
        api_key="test-key",
        as_of=date(2024, 1, 6),
    )
    assert result["passed"] is False
    assert result["insufficient_symbols"] == ["SPY"]


@pytest.mark.parametrize("close", ["0", "-1", "NaN", "Infinity", "bad"])
def test_malformed_or_nonpositive_numeric_fields_fail(
    monkeypatch: pytest.MonkeyPatch, close: str
) -> None:
    monkeypatch.setattr(
        second_source, "urlopen", lambda *args, **kwargs: _payload({"2024-01-02": close})
    )
    with pytest.raises(ValueError, match="close value"):
        second_source._fetch_alpha_vantage("SPY", "key", 1)


def test_malformed_json_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(second_source, "urlopen", lambda *args, **kwargs: io.BytesIO(b"{"))
    with pytest.raises(ValueError, match="not valid JSON"):
        second_source._fetch_alpha_vantage("SPY", "key", 1)


def test_invalid_date_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(second_source, "urlopen", lambda *args, **kwargs: _payload({"bad": "100"}))
    with pytest.raises(ValueError, match="session date"):
        second_source._fetch_alpha_vantage("SPY", "key", 1)


@pytest.mark.parametrize("key", ["Note", "Information"])
def test_rate_limiting_or_entitlement_fails(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    response = io.BytesIO(json.dumps({key: "limit"}).encode())
    monkeypatch.setattr(second_source, "urlopen", lambda *args, **kwargs: response)
    with pytest.raises(RuntimeError, match="limit or entitlement"):
        second_source._fetch_alpha_vantage("SPY", "key", 1)


def test_http_failure_is_classified_as_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        raise HTTPError("url", 503, "unavailable", None, None)

    monkeypatch.setattr(second_source, "urlopen", fail)
    with pytest.raises(RuntimeError, match="transport failed: HTTPError"):
        second_source._fetch_alpha_vantage("SPY", "key", 1)


@pytest.mark.parametrize("tolerance", [Decimal("-0.1"), Decimal("NaN")])
def test_invalid_tolerance_fails(tolerance: Decimal) -> None:
    with pytest.raises(ValueError, match="relative_tolerance"):
        second_source.compare_alpha_vantage(
            RepositoryStub({}),  # type: ignore[arg-type]
            ("SPY",),
            api_key="test-key",
            relative_tolerance=tolerance,
        )
