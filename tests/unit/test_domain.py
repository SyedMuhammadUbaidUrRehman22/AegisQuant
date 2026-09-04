"""Defense-in-depth tests for canonical Stage 1 domain invariants."""

from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from data_pipeline.schema import CanonicalBar
from tests.factories import canonical_bar


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("open", Decimal("0")),
        ("high", Decimal("NaN")),
        ("low", Decimal("-1")),
        ("close", Decimal("Infinity")),
        ("adjusted_close", Decimal("0")),
        ("volume", -1),
    ],
)
def test_canonical_bar_rejects_nonpositive_nonfinite_prices_and_volume(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        CanonicalBar.model_validate(canonical_bar().model_dump() | {field: value})


@pytest.mark.parametrize(
    "updates",
    [
        {"high": Decimal("99")},
        {"low": Decimal("101.5")},
    ],
)
def test_canonical_bar_rejects_inconsistent_ohlc(updates: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CanonicalBar.model_validate(canonical_bar().model_dump() | updates)


def test_canonical_bar_rejects_nonpositive_duration() -> None:
    bar = canonical_bar()
    with pytest.raises(ValidationError):
        CanonicalBar.model_validate(
            bar.model_dump() | {"bar_end_at": bar.bar_start_at - timedelta(seconds=1)}
        )
