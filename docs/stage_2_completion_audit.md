# Stage 2 completion audit — Blueprint v1.1

Date: 2026-09-05. Scope: Stage 2 feature engineering and the reported yfinance import problem.

Status: **INCOMPLETE / blocked from exit declaration**. The implemented source requirements have
local evidence below. Database execution, actual full-history coverage, and the required independent
Antigravity review have not been established for this revision. Stage 3 is not authorized here.

## Requirement mapping

| Blueprint requirement | Implementation and evidence | Status |
|---|---|---|
| §3 Stage 2, §5.2 adjusted returns | Simple/log adjusted-close returns; hand-calculated fixtures and extreme log-ratio test | Local pass |
| §3 Stage 2, §5.2 daily volatility | Sample standard deviation of 20 daily log returns, ddof=1, sqrt(252); configurable validated annualization | Local pass |
| §5.2 momentum | 20-observation endpoint ratio; 21 observed rows required; intervening nulls do not affect endpoint-only formula | Local pass |
| §5.2 rolling correlation | 60 paired simple returns to SPY; matching start and end times; no mismatched return horizons | Local pass |
| §3 Stage 2, §5.2 conditional macro joins | No canonical macro source exists, so no macro feature is added | Correctly conditional |
| §3 Stage 2 registry; §16 item 7 | Explicit immutable version 2 definitions, parameter-aware hashes, validated dependencies/windows/frequency | Local pass |
| §2, §5.2, §14 vectorization | Asset-column panels indexed by observed-row ordinal; batched formulas; only serialization iterates output rows | Local pass |
| §3 exit, §11 golden values | Return, momentum, volatility, nontrivial correlation, constant-window and panel-equivalence tests | Local pass |
| §3 exit, §16 items 3/8/14 temporal correctness | Past cutoff equals a full-run prefix; future invalid prices cannot alter history; shuffled inputs and equivalent offsets reproduce output | Local pass |
| §16 items 4/11/12 timezones, closures, listings/gaps | Canonical timezone checks, July 4 closure/early-close fixture, sparse-history windows, late benchmark warmup, mismatched-period correlation tests | Local pass |
| §5.2 missing-state consistency; §16 item 5 quality visibility | Required-input masks, warmup/undefined separation, JSON replay audit with per-instrument/feature reason counts | Local pass |
| §3 versioned feature store; §12 migrations | Full identity upsert, preserved created_at, conditional updated_at, parameter-bounded transactions; revision 20260905_04 | Offline/static pass; online pending |
| §3 persisted point-in-time replay; §11 Stage 1 integration | Tests cover future canonical mutation, exact historical reads, correction/rematerialization, timestamp stability and rollback | Authored; database execution pending |
| §3 complete feature table; §17 weeks 5–6 full universe/history | Read-only --validate checks all current canonical rows against storage; does not prove Stage 1 loaded all expected bars | Real-data coverage pending |
| §18 research corrections | Daily sample estimators retain correct terminology; no models, labels, global scaling, mechanical embargo, or unsupported research claims added | Source compliant |
| User-required independent Antigravity review | Pre-commit review found missing transitive dependency hashing and the absent log entry; both were resolved. Exact-commit review follows the handoff commit. | In progress |

## Corrections beyond the earlier audit

The earlier Iteration 4 statement that the source audit was complete was too strong. Its missing
mask did not handle correlation, and it could classify momentum using unused intermediate inputs.
The continuation also found that price validation preceded cutoff filtering; registry parameters
could describe behavior the calculator did not implement; and correlation matched only end times.
These are corrected with adversarial coverage. Absent benchmarks now produce explicit missing
observations; ambiguous benchmark identities fail rather than choosing an arbitrary instrument.
Resolved dependency hashes are included transitively in dependent definitions, so revising a return
identity necessarily changes the volatility or correlation identity that consumes it.

All five default identities move to version 2 with revised hashes. Migration 20260905_04 adds
nonfinite-value and nonempty-name checks; previous migrations and version 1 rows are preserved.
Default reads will need a version 2 materialization before returning the new feature set.

## Reproducibility and research limits

The cutoff contract is **event-time replay on the current canonical snapshot**. Stage 1 stores the
latest vendor-adjusted values, not a bitemporal price history. A correction to a pre-cutoff price
can change recomputed history; adjusted prices may incorporate later vendor revisions. The
implementation does not establish what was actually known to a trader at that earlier time.
Historical-vintage reconstruction needs an upstream source/version policy before such a claim can
be made. Existing raw ingestion snapshots are not automatically selected by this feature accessor.

Per-asset windows count observations. A missing whole canonical row can make a close-to-close
return span multiple exchange sessions; it is not filled or relabelled as a synthesized daily row.
Stage 1 gap checks must pass before downstream modeling. Correlation rejects mismatched horizons.
Realized covariance from intraday returns, scaling, label purging, embargo, multiple-testing
statistics, baseline models and HMM evaluation remain outside this implementation's scope.

Run materialization/replay validation against a stable canonical snapshot: the accessor and feature
reader use separate connections, so an ingestion correction concurrent with validation can produce
a discrepancy. The command reports failure rather than claiming reproducibility in that case.

## Validation evidence

Final commands and exact suite totals are recorded in DEVELOPMENT_LOG.md, Stage 2 Iteration 5.
Offline tests render both upgrade and downgrade of the new revision and assert constraint names.
The database tests are explicitly marked and remain skipped without a database URL. No new CI run
has been observed, and no local Docker recovery is claimed. Docker was not restarted because the
known host socket failure had no new recovery evidence; a process check found no Docker process.

A synthetic performance check used 20 assets × 4,500 observations (90,000 canonical-shaped rows)
and produced exactly 450,000 feature observations in **6.397 seconds** on this machine. It measures
computation/serialization only, not PostgreSQL writes or actual universe/history coverage.

## yfinance import resolution

The repository interpreter successfully imports yfinance **1.7.0** and `pip check` reports no
broken requirements. Bare `python` was unavailable in the tool shell. The existing editor settings
selected the system environment manager; the local workspace default now points to
`.venv/Scripts/python.exe`. Tracked `pyrightconfig.json` also declares the repository `.venv`.
No dependency pin was changed, no dummy import was introduced, and import diagnostics were not
suppressed. The precise user-visible error was requested but has not yet been supplied, so the
live editor's cached interpreter/diagnostic state remains unverified.

If an interpreter was already selected, use **Python: Select Interpreter** once to select `.venv`;
changing the default does not override a cached selection. This behavior is documented in the
[VS Code Python settings reference](https://code.visualstudio.com/docs/python/settings-reference).

## Antigravity handoff

Review the commit that adds this audit (`git log -1 --format=%H`) and DEVELOPMENT_LOG.md,
**Stage 2 Iteration 5 — Vectorized completion hardening and import environment**.

Expected behavior: only completed canonical bars feed the five version 2 features; formulas use
observed rows and complete required inputs; paired returns share both endpoints; missing values
retain their reason; exact registry identities coexist; unchanged rematerialization retains both
timestamps; later-batch failure rolls back the entire transaction; --validate is read-only and
detects missing/extra/stale persisted values.

Challenge formulas, panel packing and sparse alignment, availability assumptions, missing-state
precedence, definition hashes and dependency semantics, SQL conflict updates and migration
constraints, full-universe coverage, and the distinction between event-time and vendor-vintage
replay. Run the database tests only against a disposable TimescaleDB test database: their fixture
downgrades/recreates the schema and truncates tables. Record actual online results and findings,
resolve valid findings, then rerun the suite before declaring Stage 2 complete.
