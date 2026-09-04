"""Approved universe semantics tests."""

from data_pipeline.universe import STAGE_1_UNIVERSE


def test_venue_identity_is_distinct_from_shared_session_calendar() -> None:
    assert {seed.calendar_code for seed in STAGE_1_UNIVERSE} == {"XNYS"}
    assert {seed.venue_mic for seed in STAGE_1_UNIVERSE} == {"ARCX", "XNAS"}
    assert len({seed.canonical_symbol for seed in STAGE_1_UNIVERSE}) == 20
