# Feature Engineering

Stage 2 consumes only canonical daily rows from `ohlcv_bars`. `access.py` owns that read contract,
`features/` contains pure vectorized formulas, `computation.py` applies registry definitions,
`persistence.py` owns the versioned long-form `feature_values` table, and `service.py` orchestrates
one materialization run. No component downloads or fills data.

## Feature specification (version 1)

All windows count observed sessions, include the current completed bar, exclude future/target bars,
and become available exactly at `bar_end_at`. Adjusted close is used to avoid split/dividend return
discontinuities. Outputs are float64 and are not rounded.

| Feature | Formula | Required prices/returns | Domain |
|---|---|---:|---|
| `adjusted_simple_return_1d` | `P[t]/P[t-1]-1` | 2 prices | `(-1,+inf)` |
| `adjusted_log_return_1d` | `ln(P[t]/P[t-1])` | 2 prices | finite real |
| `realized_volatility_20d` | `sample_std(log returns[t-19:t])*sqrt(252)` | 21 prices | `[0,+inf)` |
| `momentum_20d` | `P[t]/P[t-20]-1` | 21 prices | `(-1,+inf)` |
| `rolling_correlation_spy_60d` | sample correlation with SPY simple returns | 61 prices, 60 aligned returns | `[-1,1]` |

There is no forward-fill. Legitimate closures have no row. Pre-listing and ordinary warm-up rows are
`insufficient_history`; absent canonical inputs are `missing_input`; mathematically indeterminate
results (such as constant correlation windows) are `undefined`. Misaligned instrument sessions are
excluded by an exact timestamp inner join. Unexpected Stage 1 gaps are not repaired and therefore
reduce aligned history.

No normalization/scaling is materialized. A later model must fit scaling parameters only within
each time-ordered training window. Current Stage 1 storage represents the latest canonical truth,
not bitemporal vendor revisions; historical source corrections require rematerializing affected
feature identities.
