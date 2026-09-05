"""Quality audit catches incomplete, stale, and missing-input feature stores."""

from dataclasses import asdict, replace

from feature_engineering import compute_features
from feature_engineering.validation import validate_materialization
from tests.factories import feature_bars


def test_replay_audit_detects_missing_extra_and_changed_rows() -> None:
    bars = feature_bars()
    expected = compute_features(bars, as_of=bars.bar_end_at.max())
    stored = [asdict(row) for row in expected]
    report = validate_materialization(expected, stored)
    assert report.passed
    assert report.counts["1/rolling_correlation_spy_60d"] == {
        "insufficient_history": 60,
        "available": 5,
    }
    assert validate_materialization(expected, stored[:-1]).mismatched_rows == 1
    stored[-1]["value"] = -0.25
    assert validate_materialization(expected, stored).mismatched_rows == 1
    stored.append(asdict(replace(expected[-1], feature_version=100)))
    assert validate_materialization(expected, stored).mismatched_rows == 2


def test_empty_and_missing_input_cannot_pass_quality_audit() -> None:
    assert not validate_materialization((), ()).passed
    bars = feature_bars()
    bars.loc[5, "adjusted_close"] = None
    expected = compute_features(bars, as_of=bars.bar_end_at.max())
    assert not validate_materialization(expected, [asdict(row) for row in expected]).passed
