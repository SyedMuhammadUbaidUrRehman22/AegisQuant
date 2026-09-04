# Stage 1 Canonical Market-Data Contract

Contract version: `1`

Stage 1 stores one completed daily economic bar per `(instrument_id, interval_code, bar_start_at)`.
The provider is not part of that identity. Timestamps are timezone-aware and stored in UTC. A
`session_date` is the exchange-local session label; `bar_start_at` and `bar_end_at` are the actual
calendar open and close, including early closes. Request ranges are start-inclusive/end-exclusive.

## Approved universe

The checked-in universe is exactly: SPY, QQQ, IWM, DIA, EFA, EEM, VNQ, TLT, IEF, SHY, LQD, HYG,
GLD, SLV, USO, XLE, XLF, XLK, XLP, and XLU. The pilot subset is SPY, QQQ, IWM, TLT, and GLD. All are
USD ETFs on the XNYS exchange calendar, with provider-specific symbols stored separately from their
canonical identity. `venue_mic` records the actual primary listing venue (`ARCX` or `XNAS`), while
`calendar_code` independently selects the shared `XNYS` session schedule. A MIC is an instrument
identity attribute; it is not a calendar identifier.

## Tables

### `instruments`

Stable canonical identity and research metadata: symbol, name, asset class, venue MIC, currency,
timezone, calendar, validity window, active state, and creation/update timestamps. Stage 1 supports
ETF instruments only.

### `instrument_source_symbols`

Maps an instrument to a provider symbol. Uniqueness prevents a provider symbol from ambiguously
resolving to multiple instruments and prevents multiple mappings for one instrument/provider pair.

### `ingestion_runs`

One durable audit record per instrument attempt. It contains a batch correlation UUID, requested and
actual date bounds, status, row counts, warning/critical counts, snapshot path and SHA-256,
normalized-data SHA-256, adapter/library/calendar/contract/Python versions, a Git revision (or
deterministic runtime-source SHA-256 when `.git` is unavailable), dirty state, explicit request
semantics, bounded failure details, and timestamps. Database URLs and
credentials are never recorded. A multi-symbol command deliberately has independent run records and
transactions so one failed symbol cannot corrupt successful peers.

### `ohlcv_bars`

The TimescaleDB hypertable containing canonical daily observations:

| Field | Meaning |
| --- | --- |
| `instrument_id` | Canonical instrument foreign key. |
| `interval_code` | `1d` in Stage 1. |
| `session_date` | Exchange-local trading-session label. |
| `bar_start_at` | Actual exchange open in UTC; part of the economic-bar primary key. |
| `bar_end_at` | Actual exchange close in UTC; incomplete sessions are prohibited. |
| `open`, `high`, `low`, `close` | Unadjusted provider prices, `NUMERIC(20,8)`. |
| `adjusted_close` | Provider adjusted close, `NUMERIC(20,8)`. |
| `volume` | Non-negative integer shares/units. |
| `source_name` | Source responsible for the current canonical value. |
| `ingestion_run_id` | Exact successful run and source snapshot that produced the current value. |
| `contract_version` | Canonical contract version (`1`). |
| `quality_flags` | Stable warning/correction codes attached to the observation. |
| `created_at`, `updated_at` | Database timestamps; unchanged replay does not modify either. |

Corrections change only rows whose canonical values differ, set `source_correction`, reference the
correcting ingestion run, and update `updated_at`. Prior ingestion runs and immutable raw snapshots remain available
for audit. Identical replays and overlapping ranges preserve canonical values and timestamps.

### `corporate_actions`

Positive dividends, stock-split ratios, and capital-gain distributions keyed by instrument,
effective date, and action type. Splits have no currency; cash events use instrument currency. The
row references the run/snapshot that produced its current value and follows the same idempotent
insert/update/no-op behavior. A provider correction that removes an action marks it inactive and
retains the row as an auditable tombstone. Completeness and tombstoning use the same
start-inclusive/end-exclusive request range as bars: an action exactly on `requested_end` is outside
the request and remains untouched.

## Quality policy

Critical findings prevent the entire instrument batch from reaching canonical tables: missing
columns; timestamp/numeric parsing errors; null, NaN, or infinite required values; non-positive
prices; inconsistent OHLC bounds; fractional or negative volume; non-session or incomplete-session
timestamps; observations outside the requested/validity range; unexpected completed-session gaps;
and conflicting duplicate observations. Database constraints remain the final invariant boundary.

Warnings retain the observation: identical provider duplicates (collapsed deterministically), price
precision rounding, zero volume, unusually large close movement, unusually high volume, repeated
OHLC, corporate actions, and source corrections. Statistical warnings never delete observations.

Exchange holidays, closures, early closes, and configured instrument validity windows are removed
from the expected-session set. Genuine completed-session gaps fail. The pipeline never forward-fills,
backward-fills, interpolates, invents prices, or synthesizes zero-volume bars.

## Source snapshots and hashes

Every successful provider response is serialized as deterministic JSON, SHA-256 hashed, gzip
compressed with a deterministic header, and atomically stored at a content-addressed path below
`data/raw/yahoo_finance/v1/`. The snapshot hash covers acquisition metadata and provider-shaped
values. A separate normalized hash covers sorted canonical bars and actions but excludes run and
ingestion timestamps. It also excludes mutable quality flags and the contract version so equal
economic content remains equal across quality-policy or schema-version changes; contract version is
recorded separately on every run and canonical bar. Snapshot files and reports are local/generated
data and are not committed.
