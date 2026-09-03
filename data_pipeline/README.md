# Data Pipeline

Stage 1 owns historical provider access, exchange-session normalization, immutable source snapshots,
canonical OHLCV persistence, corporate actions, provenance, and deterministic quality reporting.

Package boundaries:

- `ingestion/`: provider, calendar, normalization, retry, snapshot, orchestration, and repository.
- `quality_checks/`: hard invariants, warnings, and report serialization.
- `schema/`: Pydantic contracts, stable hashing, and SQLAlchemy Core metadata.
- `validation/`: independent second-source spot checks that cannot write canonical observations.
- `universe.py`: the version-controlled 20-ETF universe and five-symbol pilot.
- `cli.py`: seed, full/incremental ingestion, integrity inspection, and validation commands.

All daily timestamps resolve through the instrument's exchange calendar. No missing observation is
filled or synthesized, and no statistically unusual observation is discarded automatically.
