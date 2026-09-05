"""Deterministic coverage and point-in-time replay checks for materialized features."""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from feature_engineering.computation import FeatureObservation


@dataclass(frozen=True, slots=True)
class FeatureValidation:
    """Reviewable quality counts and exact replay differences at one explicit cutoff."""

    expected_rows: int
    stored_rows: int
    mismatched_rows: int
    counts: dict[str, dict[str, int]]
    issues: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """Return whether coverage, input quality, and replay checks passed."""

        return not self.issues


def validate_materialization(
    expected: Sequence[FeatureObservation], stored: Sequence[Mapping[str, object]]
) -> FeatureValidation:
    """Compare full registered identities, values, reasons, and information timestamps."""

    counts: dict[str, dict[str, int]] = {}
    for observation in expected:
        key = f"{observation.instrument_id}/{observation.feature_name}"
        reasons = counts.setdefault(key, {})
        reasons[observation.missing_reason] = reasons.get(observation.missing_reason, 0) + 1
    expected_values: dict[tuple[object, ...], tuple[object, ...]] = {
        (
            row.instrument_id,
            row.feature_name,
            row.feature_version,
            row.definition_hash,
            row.bar_end_at,
        ): (row.value, row.missing_reason, row.feature_as_of)
        for row in expected
    }
    stored_values: dict[tuple[object, ...], tuple[object, ...]] = {
        (
            row["instrument_id"],
            row["feature_name"],
            row["feature_version"],
            row["definition_hash"],
            row["bar_end_at"],
        ): (row["value"], row["missing_reason"], row["feature_as_of"])
        for row in stored
    }
    mismatches = sum(
        expected_values.get(key) != stored_values.get(key)
        for key in expected_values.keys() | stored_values.keys()
    )
    issues: list[str] = []
    if not expected:
        issues.append("no canonical feature observations at the cutoff")
    if mismatches:
        issues.append("stored features differ from canonical replay; rematerialization required")
    if len(stored_values) != len(stored):
        issues.append("duplicate stored feature identities")
    reasons_total = Counter(row.missing_reason for row in expected)
    if reasons_total["missing_input"]:
        issues.append("required canonical or benchmark inputs are missing")
    return FeatureValidation(len(expected), len(stored), mismatches, counts, tuple(issues))
