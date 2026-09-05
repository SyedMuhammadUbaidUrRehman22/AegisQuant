# Feature Engineering

Stage 2 consumes only canonical daily rows from `ohlcv_bars`. `access.py` owns that read contract,
`features/` contains pure vectorized formulas, `computation.py` applies registry definitions,
`persistence.py` owns the versioned long-form `feature_values` table, and `service.py` orchestrates
one materialization run. No component downloads or fills data.

## Feature specification (version 2)

All windows count observed sessions, include the current completed bar, exclude future/target bars,
and have modeled availability at `bar_end_at`. Adjusted close is used to avoid split/dividend return
discontinuities. Outputs are float64 and are not rounded.

| Feature | Formula | Required prices/returns | Domain |
|---|---|---:|---|
| `adjusted_simple_return_1d` | `P[t]/P[t-1]-1` | 2 prices | `(-1,+inf)` |
| `adjusted_log_return_1d` | `ln(P[t]/P[t-1])` | 2 prices | finite real |
| `rolling_annualized_volatility_20d` | `sample_std(log returns[t-19:t])*sqrt(252)` | 21 prices | `[0,+inf)` |
| `momentum_20d` | `P[t]/P[t-20]-1` | 21 prices | `(-1,+inf)` |
| `rolling_correlation_spy_60d` | sample correlation with SPY simple returns | 61 prices, 60 aligned returns | `[-1,1]` |

There is no forward-fill. Legitimate closures have no row. Pre-listing and ordinary warm-up rows are
`insufficient_history`; absent canonical inputs are `missing_input`; mathematically indeterminate
results (such as constant correlation windows) are `undefined`. Correlation joins exact bar-end
timestamps and additionally requires the same preceding timestamp for both returns. A return
spanning a missing session cannot be paired with a one-session benchmark return. That pair and
affected rolling windows are `missing_input`. An absent benchmark yields explicit missing rows;
an ambiguous benchmark symbol fails. Warmup counts paired observations with preceding prices,
including for a benchmark that begins after the target instrument.

Simple/log returns require both endpoint prices. Volatility requires every price in its trailing
21-price window. Momentum uses just its two endpoints, while still requiring 21 observed rows.
Null inputs used by a formula take precedence over warmup. Missing intermediate prices do not
invalidate endpoint-only momentum. No canonical gaps are filled or repaired. Single-instrument
returns across absent rows span consecutive *observed* prices, which can cover multiple sessions;
Stage 1 gap-quality checks remain a prerequisite to interpreting those as one-session returns.

No normalization/scaling is materialized. A later model must fit scaling parameters only within
each time-ordered training window. Current Stage 1 storage represents the latest canonical truth,
not bitemporal vendor revisions; historical source corrections require rematerializing affected
feature identities.

The `--as-of` contract excludes later bar observations, including benchmark data, before validating
price/volume values. Canonical timestamps must always be non-null and timezone-aware. Invalid
numbers fail rather than being coerced into missing values. Cutoffs with equivalent UTC offsets
produce identical results. There are no labels or fitted normalization parameters in this module.
This is event-time replay of the current canonical snapshot, not proof that a vendor revision or
back-adjusted price was actually known at the historical cutoff. Run materialization and validation
against a stable canonical snapshot; historical vendor-vintage reconstruction is not implemented.

## Registry and numerical execution

Definitions expose every window, minimum, parameter, input, dependency, version, and SHA-256 hash.
The registry rejects unsupported frequencies/inputs, inconsistent windows/minimums, invalid
annualization, future-target semantics, duplicate names, and missing or wrong-kind dependencies.
Dependency names are resolved explicitly, so renamed return features and registration order work.
Each resolved dependency hash is included in the consuming definition hash, preventing a changed
return implementation from silently reusing a volatility or correlation identity.

Numerical functions support Series and DataFrame panels. Computation packs assets by observed-row
ordinal, runs vectorized operations across asset columns, then emits only canonical rows. Panel
padding is never emitted. Only output serialization loops over observations. Hashes are computed
once per feature. Log differences avoid intermediate price-ratio overflow; nonfinite outputs are
null/undefined. Constant correlation windows remain undefined before clipping numerical roundoff.

## Storage and validation

The primary key is `(instrument_id, feature_name, feature_version, definition_hash, bar_end_at)`.
Writes use one transaction with 1,000-row batches by default (maximum 8,000 to respect PostgreSQL's
parameter limit). Duplicate identities in a single call fail before SQL. Identical rematerialization
does not update timestamps; corrections retain `created_at` and update changed rows only.
Reads filter the complete registered identity and both bar/information cutoffs.

Revision `20260905_04` adds database checks rejecting nonfinite values and empty feature names.
It does not rewrite legacy rows. If invalid existing rows prevent migration, diagnose those rows
before rerunning; do not erase them silently. Version 1 feature rows coexist with version 2, and
default reads select version 2. Materialize version 2 after upgrading:

```bash
python -m alembic upgrade head
python -m feature_engineering --as-of 2026-09-04T21:00:00Z
python -m feature_engineering --as-of 2026-09-04T21:00:00Z --validate
```

`--validate` is read-only. It reports JSON counts by instrument/feature/missing reason and compares
stored rows exactly against canonical replay, including full identity, values, reasons, and as-of
metadata. Missing/extra/stale rows, missing required inputs, and an empty canonical input return
exit code 1. Warmup and mathematical undefined states remain visible without being treated as
corrupt data. Coverage is relative to canonical rows; proving the approved universe/history was
fully ingested remains Stage 1's responsibility.

See [the Stage 2 completion audit](../docs/stage_2_completion_audit.md) for validation evidence and
the remaining online database and independent-review gates.
