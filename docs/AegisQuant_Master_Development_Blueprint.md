# AegisQuant — Master Development Blueprint

**Internal Technical Documentation**
**Autonomous Regime-Aware Quantitative Intelligence & Portfolio Optimization Platform**
**Version 1.0 — Final Year Project Master Document**

---

## Table of Contents

1. Overall System Overview
2. Development Philosophy
3. Complete Build Order
4. Dependency Graph
5. Detailed Module Design
6. Mathematical Foundations
7. Research Paper Mapping
8. Technology Decisions
9. Project Folder Structure
10. Git Strategy
11. Testing Strategy
12. DevOps Pipeline
13. Security Considerations
14. Performance Optimization
15. Risk Register
16. Things That Usually Go Wrong
17. Recommended Weekly Roadmap
18. Final Architecture Review

---

## 1. Overall System Overview

### 1.1 What AegisQuant Is

AegisQuant is a **regime-aware quantitative research and portfolio management pipeline**. The system does not treat markets as statistically uniform through time. Instead, it explicitly detects the latent "state" the market is in (e.g., low-volatility trending, high-volatility crisis, range-bound) and conditions every downstream decision — return forecasts, portfolio weights, execution style, and risk limits — on that state. This is what "regime-aware" means architecturally: regime is not a feature bolted onto a model, it is a first-class signal that gates or reweights every module downstream of it.

### 1.2 End-to-End Data Flow

At the highest level, data moves through the system in one direction, with feedback loops only at the backtesting and monitoring layers:

```
[Market Data Sources]
        |
        v
[Data Ingestion Pipeline] --> [PostgreSQL / TimescaleDB]
        |
        v
[Feature Engineering] ---------------------------+
        |                                        |
        v                                        v
[Representation Learning]              [Regime Detection (HMM)]
        |                                        |
        +--------------------+-------------------+
                             |
                             v
                  [Forecast / Signal Layer]
                             |
                             v
                  [Monte Carlo Simulation]
                             |
                             v
              [Convex Portfolio Optimization]
                             |
                             v
                    [Risk Management Engine] <-------+
                             |                        |
                             v                        |
                     [Execution Engine (VWAP)]        |
                             |                        |
                             v                        |
                  [Walk-Forward Backtesting] ---------+
                             |
                             v
              [FastAPI Microservices Layer]
                             |
                             v
              [Flutter Dashboard]  [Multi-Agent Layer]
                             |
                             v
                [Docker / CI-CD / Monitoring]
```

Every arrow above is a **service boundary**, not just a function call. Each module communicates through well-defined contracts (Pydantic schemas served over REST, or a shared Postgres schema), which is what allows modules to be built, tested, and even swapped out independently.

### 1.3 Why This Architecture

Three forces shaped the architecture:

- **Regime-conditioning must be structural, not incidental.** If regime detection were just "another feature," it would get diluted inside a large model. Instead it sits as an explicit upstream module whose output (a discrete or probabilistic regime label) is consumed by both the portfolio optimizer (to adjust risk aversion / constraints) and the execution engine (to adjust participation rate in volatile regimes).
- **Research and production must share one codebase without one blocking the other.** Quant research (HMMs, representation learning, Monte Carlo) evolves through notebooks and experiments; production (FastAPI, Docker, dashboard) needs stability and contracts. A microservices boundary lets the research modules be iterated aggressively behind a stable API, while the serving layer stays untouched.
- **Every stage must be independently backtestable.** Because AegisQuant is autonomous, a bug in one module (e.g., a bad correlation estimate feeding portfolio optimization) can silently degrade performance without throwing an exception. The architecture therefore treats walk-forward backtesting not as a final step but as a validation gate that every module must pass in isolation before integration.

### 1.4 How Modules Communicate

Two communication patterns are used, deliberately kept to just two so the system doesn't accumulate ad-hoc integration code:

1. **Synchronous REST (FastAPI, Pydantic-validated JSON)** for anything that needs a request/response cycle with low latency requirements — e.g., the dashboard asking "what is the current regime?" or the execution engine asking the risk engine "is this trade within limits?"
2. **Shared PostgreSQL tables (batch writes, versioned)** for anything that is produced on a schedule and consumed by multiple downstream readers — e.g., feature engineering writes a `features` table nightly; both representation learning and regime detection read from it independently, at their own cadence.

n8n (optional) sits outside both patterns as an orchestration/scheduling layer — it does not carry business logic, only triggers ("run feature engineering job", "if regime = crisis, alert on Slack").

---

## 2. Development Philosophy

AegisQuant is built around seven non-negotiable principles. These are not abstract values — each one maps to a concrete rule enforced in code review.

**Modular architecture.** Every module (regime detection, portfolio optimization, execution, etc.) is a Python package with its own `__init__.py`, its own tests, and its own README explaining its contract. A module must be importable and testable without spinning up any other module. Rule of thumb: if you cannot unit-test a module with mocked inputs alone, it is not modular enough.

**Separation of concerns.** Research code (model fitting, hyperparameter search) never lives in the same file as serving code (FastAPI route handlers). The rule: `research/` produces artifacts (pickled models, ONNX exports, parquet files); `services/` only loads and serves artifacts. A service should never call `.fit()`.

**Scalability.** Design for horizontal scaling from day one even if you only run on one machine for the FYP. Concretely: stateless FastAPI services behind a process manager, feature computation expressed as vectorized/batchable operations (not per-row Python loops), and Monte Carlo simulation written to parallelize trivially (embarrassingly parallel paths).

**Maintainability.** Type hints everywhere, docstrings on every public function, and a single source of truth for configuration (see Section 9 — no hardcoded paths or magic numbers scattered across files). A new contributor should be able to read a module's `README.md` and understand its contract in under 10 minutes.

**Reproducibility.** Every experiment (HMM fit, deep learning training run, backtest) must be reproducible from a config file plus a fixed random seed. Model artifacts are versioned and stored with the exact config and data snapshot hash that produced them. If you cannot regenerate last month's backtest number, the pipeline is not reproducible — this is treated as a release blocker, not a nice-to-have.

**Testing-first mindset.** No module is considered "done" without unit tests for its core logic, at least one integration test proving it composes with its upstream/downstream neighbor, and — for anything touching money (portfolio optimization, execution, risk) — a numerical sanity test against a known closed-form answer (e.g., a two-asset Markowitz problem with a hand-computable efficient frontier).

**Production-oriented design.** Even though this is a Final Year Project, every module is written as if it will run unattended in production: explicit error handling (no bare `except:`), structured logging (not `print()`), and graceful degradation (e.g., if the regime detector fails to update, the system should fall back to the last known regime rather than crash the portfolio optimizer).


---

## 3. Complete Build Order

This is the exact sequence developers should follow. Each stage lists what "done" means (exit criteria) before the next stage starts. Stages 0–2 are sequential and blocking. From Stage 3 onward, sub-stages can run in parallel (marked with **[P]**) if you have more than one developer.

### Stage 0 — Environment & Repo Scaffolding
- **Purpose:** Establish the foundation everything else is built on — repo structure, dependency management, config system, Docker base images.
- **Expected outputs:** A cloned-and-runnable skeleton repo; `docker-compose up` brings up an empty Postgres + a "hello world" FastAPI service.
- **Dependencies:** None.
- **Deliverables:** Repo skeleton (Section 9), `pyproject.toml`/`requirements.txt`, `.env.example`, base `Dockerfile`, `docker-compose.yml`, CI skeleton (lint + test job that passes on an empty repo).
- **Possible blockers:** Docker networking issues on Windows; Python/Postgres version mismatches.
- **Validation:** `docker-compose up` succeeds; `pytest` runs (even with zero tests) with exit code 0; CI pipeline is green on first commit.
- **Exit criteria:** A second developer can clone the repo and get a running environment in under 15 minutes, from a `README.md` alone.

### Stage 1 — Data Ingestion Pipeline
- **Purpose:** Get reliable, versioned historical and (optionally) streaming market data into PostgreSQL/TimescaleDB.
- **Expected outputs:** OHLCV tables populated for a chosen universe (e.g., 20–50 liquid equities/ETFs), with a documented schema.
- **Dependencies:** Stage 0.
- **Deliverables:** Ingestion scripts (batch, idempotent — re-running must not duplicate rows), a data dictionary, and a `data_quality` check script (nulls, gaps, duplicate timestamps).
- **Possible blockers:** Data vendor rate limits; survivorship bias if the universe isn't point-in-time correct; timezone/session-calendar bugs.
- **Validation:** Automated data-quality report shows zero gaps for the chosen date range; spot-check 5 tickers against a second source.
- **Exit criteria:** A full historical load runs end-to-end unattended and the data-quality script reports zero critical issues.

### Stage 2 — Feature Engineering
- **Purpose:** Transform raw OHLCV into the features consumed by regime detection, representation learning, and forecasting.
- **Expected outputs:** A versioned `features` table/parquet store (returns, realized volatility, rolling correlations, macro features if used).
- **Dependencies:** Stage 1.
- **Deliverables:** Feature computation library (pure functions, vectorized), a feature registry (name → definition → lookback window), unit tests comparing computed features against hand-calculated values on a toy series.
- **Possible blockers:** Look-ahead bias (using future data in a rolling window); inconsistent handling of missing data across features.
- **Validation:** Point-in-time correctness test — recomputing features "as of" a past date must match what was stored at that date.
- **Exit criteria:** Feature table is complete, documented, and passes the point-in-time correctness test.

### Stage 3 **[P]** — Regime Detection (HMM)
- **Purpose:** Produce a regime label/probability distribution per time step.
- **Dependencies:** Stage 2.
- **Deliverables:** Baseline Gaussian HMM (Baum-Welch + Viterbi), model selection via BIC, a `regime_history` table, evaluation notebook comparing regimes against known volatility spikes (e.g., 2020 COVID crash, 2022 rate-hike period) as a sanity check.
- **Possible blockers:** EM converging to a degenerate solution (one state absorbing everything); unstable state count selection.
- **Validation:** Regimes visually align with known historical stress periods; log-likelihood improves over a naive single-state baseline.
- **Exit criteria:** Model is deterministic given a fixed seed, serialized, and served via a `/regime/current` endpoint.

### Stage 4 **[P]** — Representation Learning
- **Purpose:** Learn embeddings/forecasts from time series (LSTM/Transformer) to feed the forecast layer.
- **Dependencies:** Stage 2 (can run in parallel with Stage 3 — they share only feature inputs, not outputs).
- **Deliverables:** Training pipeline, model checkpoint, offline evaluation report (MSE/MAE/directional accuracy vs. naive baseline).
- **Possible blockers:** Overfitting on limited financial history; non-stationarity causing train/test performance gap.
- **Validation:** Must beat a naive persistence baseline out-of-sample; walk-forward (not random) train/test split.
- **Exit criteria:** Model artifact versioned, reproducible from config, and beats baseline on held-out walk-forward folds.

### Stage 5 — Monte Carlo Simulation
- **Purpose:** Generate forward-looking scenario distributions for portfolio and risk modules.
- **Dependencies:** Stage 3 and Stage 4 outputs (regime-conditioned parameters improve simulation realism, though a regime-agnostic version can be built as a fallback).
- **Deliverables:** Simulation engine (GBM baseline, regime-conditioned parameter switching), variance reduction (antithetic variates at minimum), a scenario-output store.
- **Possible blockers:** Runtime blow-up with naive Python loops; incorrect correlation structure in multi-asset simulation.
- **Validation:** Simulated moments (mean, vol) converge to input parameters as path count increases; correlation of simulated paths matches historical correlation matrix within tolerance.
- **Exit criteria:** Simulation runs within an agreed time budget (e.g., 10,000 paths × 50 assets in under N seconds) and passes convergence tests.

### Stage 6 — Convex Portfolio Optimization
- **Purpose:** Convert forecasts + risk estimates into portfolio weights.
- **Dependencies:** Stage 5 (and optionally Stage 3 for regime-conditioned risk aversion).
- **Deliverables:** CVXPY-based optimizer (mean-variance baseline, then constraints: no-short, position limits, turnover/transaction-cost penalty), unit tests against a hand-computable 2–3 asset closed-form solution.
- **Possible blockers:** Infeasible constraint sets (solver returns no solution); numerically unstable covariance matrices requiring shrinkage.
- **Validation:** Solver status is checked and logged on every call (never silently accept a non-optimal status); output weights sum to 1 (or to the intended leverage) within floating-point tolerance.
- **Exit criteria:** Optimizer produces valid weights across at least 3 market regimes in backtest without solver failures.

### Stage 7 — Risk Management Engine
- **Purpose:** Independent check on proposed portfolios/trades — VaR/CVaR, exposure limits, drawdown circuit breakers.
- **Dependencies:** Stage 5 (uses Monte Carlo output), Stage 6 (validates its output).
- **Deliverables:** VaR/CVaR calculator, limit-checking service, a "kill switch" that can block execution if breached.
- **Possible blockers:** Risk engine and optimizer disagreeing on covariance assumptions (must share one estimation source).
- **Validation:** Backtested VaR breach frequency matches the stated confidence level (e.g., ~5% breach rate for 95% VaR) — this is a real statistical test, not a visual check.
- **Exit criteria:** Risk engine can veto a portfolio and this veto is logged and testable end-to-end.

### Stage 8 — Execution Engine
- **Purpose:** Translate target weights into orders with minimal market impact and slippage.
- **Dependencies:** Stage 6 output (target weights), Stage 7 (pre-trade risk check).
- **Deliverables:** VWAP scheduler (volume-curve based order slicing), slippage model, paper-trading simulator.
- **Possible blockers:** Unrealistic slippage assumptions inflating backtest performance (a very common and dangerous mistake — see Section 16).
- **Validation:** Backtested implementation shortfall is within a plausible range versus published academic estimates for similar strategies/liquidity.
- **Exit criteria:** Paper-trading simulation runs end-to-end from target weights to simulated fills with logged slippage.

### Stage 9 — Walk-Forward Backtesting Harness
- **Purpose:** The single source of truth for "does this system work" — must be built early enough to validate every module above, and hardened here as its own deliverable.
- **Dependencies:** Conceptually needed from Stage 3 onward (each module's exit criteria references backtesting); this stage is where it becomes a first-class, reusable harness rather than ad-hoc notebooks.
- **Deliverables:** Rolling-window train/validate/test harness, performance report generator (Sharpe, Sortino, max drawdown, turnover), leakage-detection tests.
- **Possible blockers:** Subtle look-ahead bias reappearing when modules are chained together (each module might be leakage-free in isolation but not in combination).
- **Validation:** A "shuffle test" — randomly shuffling regime labels should destroy performance; if it doesn't, the regime signal isn't actually being used.
- **Exit criteria:** Full pipeline (data → regime → forecast → MC → optimize → risk → execute) runs walk-forward over the full history without manual intervention.

### Stage 10 — FastAPI Microservices Layer
- **Purpose:** Expose each module as a service with a stable contract.
- **Dependencies:** The module(s) being wrapped must already pass their own exit criteria.
- **Deliverables:** One FastAPI app per bounded context (or a modular monolith with clear routers), OpenAPI docs auto-generated, request/response Pydantic schemas.
- **Validation:** Contract tests — schema validation on every endpoint; load test at expected request volume.
- **Exit criteria:** All endpoints documented in OpenAPI, integration-tested, and containerized.

### Stage 11 **[P]** — Multi-Agent Layer
- **Purpose:** Orchestrate modules as coordinating agents (e.g., a "strategy agent," a "risk agent," a "execution agent") rather than a single hardcoded pipeline script.
- **Dependencies:** Stage 10 (agents call module services, they don't reimplement module logic).
- **Deliverables:** Agent role definitions, communication protocol (can be as simple as shared state in Postgres + REST calls), a simulated multi-agent trading session log.
- **Exit criteria:** A full trading cycle can be triggered and traced through agent decision logs end-to-end.

### Stage 12 **[P]** — Flutter Dashboard
- **Purpose:** Visualize regime state, portfolio composition, risk metrics, and backtest results.
- **Dependencies:** Stage 10 (dashboard only consumes FastAPI endpoints, never touches the database directly).
- **Exit criteria:** Dashboard renders live data from staging environment without hardcoded mock data.

### Stage 13 — DevOps Hardening & Deployment
- **Purpose:** CI/CD, monitoring, secrets management, final deployment.
- **Dependencies:** All prior stages containerized.
- **Exit criteria:** A single `git push` to `main` triggers tests → build → deploy to staging automatically; production deploy is a manual-approval gate.


---

## 4. Dependency Graph

### 4.1 What Depends on What

| Module | Hard dependencies | Soft dependencies (improves quality, not required) |
|---|---|---|
| Data Pipeline | None | — |
| Feature Engineering | Data Pipeline | — |
| Regime Detection (HMM) | Feature Engineering | — |
| Representation Learning | Feature Engineering | — |
| Monte Carlo | Feature Engineering | Regime Detection (for regime-conditioned parameters) |
| Portfolio Optimization | Monte Carlo | Regime Detection (for regime-based risk aversion) |
| Risk Engine | Monte Carlo, Portfolio Optimization | — |
| Execution Engine | Portfolio Optimization, Risk Engine | Representation Learning (for volume prediction) |
| Backtesting Harness | All of the above, chained | — |
| FastAPI Layer | Whatever module it wraps | — |
| Multi-Agent Layer | FastAPI Layer | — |
| Dashboard | FastAPI Layer | — |
| DevOps | Everything containerized | — |

### 4.2 Independently Developable Modules

Regime Detection and Representation Learning share only an input (the feature table) and have zero interdependency — they can be built by two different developers simultaneously with no coordination needed beyond agreeing on the feature schema. Similarly, the Dashboard and the Multi-Agent Layer both depend only on the FastAPI contract, not on each other, and can be developed in parallel once that contract is frozen.

### 4.3 What Should Never Be Started Before Its Dependencies

- **Never build the Execution Engine before Portfolio Optimization produces stable output.** Execution logic tuned against a moving optimizer target wastes effort re-tuning slippage assumptions.
- **Never build the Dashboard before the FastAPI contract is stable.** This is the single most common source of wasted rework in student projects — UI built against an API that keeps changing shape.
- **Never build the Multi-Agent Layer first "because it's the most interesting part."** Agents are orchestrators; without working services to orchestrate, agent code becomes an unfalsifiable simulation of imaginary logic.
- **Never wire up live/paper trading before the Backtesting Harness has validated the full chained pipeline (Stage 9).** Isolated module correctness does not imply chained-pipeline correctness (leakage can appear only when modules combine).

---

## 5. Detailed Module Design

### 5.1 Data Pipeline
- **Purpose:** Ingest, clean, and store point-in-time-correct market data.
- **Inputs:** Vendor API/CSV feeds (OHLCV, and optionally fundamental/macro data).
- **Outputs:** Normalized tables in PostgreSQL/TimescaleDB.
- **Algorithms:** None (deterministic ETL), plus gap-detection heuristics.
- **Libraries:** `pandas`, `sqlalchemy`, `psycopg2`/`asyncpg`, `apscheduler` or n8n for scheduling.
- **Data structures:** Long-format time series tables (`ticker`, `timestamp`, `open`, `high`, `low`, `close`, `volume`), indexed on `(ticker, timestamp)`.
- **Alternatives:** Flat parquet files instead of Postgres (simpler, but loses relational query power and concurrent-write safety).
- **Expected runtime:** Minutes for a full historical batch load of a 20–50 name universe at daily frequency; seconds for incremental daily updates.
- **Testing strategy:** Idempotency tests (re-running a load produces no duplicate rows), gap-detection unit tests on synthetic data with known gaps.
- **Common implementation mistakes:** Not handling corporate actions (splits/dividends) → silent return discontinuities; using `datetime.now()` instead of exchange-calendar-aware timestamps.
- **Performance considerations:** Bulk inserts (`COPY`) instead of row-by-row inserts.
- **Future improvements:** Streaming ingestion for intraday/tick data if the project scope expands.

### 5.2 Feature Engineering
- **Purpose:** Compute the model-ready feature set from raw prices.
- **Inputs:** OHLCV table.
- **Outputs:** Feature table (returns, realized vol, rolling correlation, momentum, macro joins).
- **Algorithms:** Rolling-window statistics; realized covariance estimators.
- **Libraries:** `pandas`/`polars`, `numpy`, `ta-lib` or hand-rolled indicators.
- **Data structures:** Wide or long feature table, versioned by a feature-definition hash.
- **Alternatives:** `polars` over `pandas` for large universes (columnar, faster rolling ops).
- **Expected runtime:** Seconds to low minutes for daily-frequency, moderate universe size.
- **Testing strategy:** Golden-value tests against manually computed features on a 10-row toy series; point-in-time correctness tests (see Stage 2).
- **Common implementation mistakes:** Look-ahead bias in rolling windows (using `.rolling(centered=True)` by accident); inconsistent NA handling across features silently shrinking usable history.
- **Performance considerations:** Vectorize; avoid per-ticker Python loops where a groupby-vectorized operation works.
- **Future improvements:** Add alternative data (sentiment, order-flow) once core pipeline is stable.

### 5.3 Representation Learning (Transformer/LSTM)
- **Purpose:** Learn compressed, predictive embeddings of financial time series.
- **Inputs:** Feature table (windowed sequences).
- **Outputs:** Embeddings and/or point forecasts, model checkpoint.
- **Algorithms:** LSTM baseline → attention/Transformer variant → optionally contrastive pretraining for embeddings.
- **Libraries:** `PyTorch`, `pytorch-lightning` (optional), `numpy`.
- **Data structures:** Sliding-window tensors `(batch, sequence_length, n_features)`.
- **Alternatives:** Gradient-boosted trees (LightGBM) as a strong, cheaper-to-tune baseline before committing to deep learning.
- **Expected runtime:** Minutes to hours per training run on a single GPU/CPU depending on universe size and sequence length.
- **Testing strategy:** Beat a naive persistence baseline out-of-sample; walk-forward validation, never random shuffling of time-ordered data.
- **Common implementation mistakes:** Random train/test splits on time series (catastrophic leakage); not scaling/normalizing per-fold (using global statistics leaks future information).
- **Performance considerations:** Batch size vs. sequence length tradeoffs; mixed precision training if on GPU.
- **Future improvements:** Joint-embedding predictive architectures (self-supervised pretraining) once supervised baseline is solid.

### 5.4 Regime Detection (HMM)
- **Purpose:** Infer the latent market regime driving observed statistics.
- **Inputs:** Feature table (returns, volatility, macro features).
- **Outputs:** Regime label/probability per time step, transition matrix.
- **Algorithms:** Gaussian HMM (Baum-Welch/EM + Viterbi); optional non-normal emissions for fat tails.
- **Libraries:** `hmmlearn`, or a custom implementation in `numpy`/`PyTorch` for more control over emission distributions.
- **Data structures:** State sequence array, transition matrix, emission parameters per state.
- **Alternatives:** Gaussian Mixture Models (no temporal structure — simpler, weaker); regime detection via unsupervised clustering (k-means on rolling vol/correlation).
- **Expected runtime:** Seconds to low minutes for EM convergence on a multi-year daily dataset.
- **Testing strategy:** Multiple-restart EM to avoid local optima; regime timeline sanity-checked against known historical stress events; BIC-based state-count selection tested across a range (2–5 states).
- **Common implementation mistakes:** Choosing state count by eyeballing instead of BIC/AIC; not detecting label-switching between retrainings (state 0 today might correspond to state 1 last month).
- **Performance considerations:** Multivariate HMMs scale poorly with feature count — keep the emission feature set small and curated (see Section 16 on curse of dimensionality).
- **Future improvements:** Autoencoder/Transformer-augmented emissions, RL-based adaptive regime control (per the literature review's most advanced cited work).

### 5.5 Monte Carlo Simulation
- **Purpose:** Generate forward scenario distributions for risk/portfolio modules.
- **Inputs:** Estimated drift/volatility/correlation (optionally regime-conditioned).
- **Outputs:** Simulated price/return paths.
- **Algorithms:** Geometric Brownian Motion baseline; regime-switching GBM; variance reduction (antithetic variates, control variates).
- **Libraries:** `numpy` (vectorized path generation), `numba` for JIT speedup if needed.
- **Data structures:** `(n_paths, n_steps, n_assets)` array.
- **Alternatives:** Bootstrap resampling of historical returns instead of parametric GBM (fewer distributional assumptions, but assumes history repeats).
- **Expected runtime:** Should be parallelizable to run 10,000+ paths across dozens of assets in seconds to low minutes on a single machine.
- **Testing strategy:** Convergence tests (simulated moments → true parameters as path count grows); correlation-structure preservation tests.
- **Common implementation mistakes:** Python for-loops over paths instead of vectorized array operations (order-of-magnitude slowdown); ignoring cross-asset correlation (simulating each asset independently).
- **Performance considerations:** Vectorize fully; consider multiprocessing across path batches.
- **Future improvements:** Jump-diffusion or regime-conditioned stochastic volatility for more realistic tail behavior.

### 5.6 Portfolio Optimization (CVXPY)
- **Purpose:** Convert forecasts and risk estimates into implementable portfolio weights.
- **Inputs:** Expected returns, covariance matrix (from Monte Carlo/historical estimation), constraints.
- **Outputs:** Target weight vector.
- **Algorithms:** Mean-variance optimization (QP); extensions for turnover penalty, position limits, risk parity as an alternative objective.
- **Libraries:** `cvxpy`, `numpy`.
- **Data structures:** Weight vector, constraint matrices.
- **Alternatives:** Risk parity or Black-Litterman if pure mean-variance proves too sensitive to estimation error.
- **Expected runtime:** Milliseconds to low seconds per solve for a universe of tens of assets.
- **Testing strategy:** Closed-form 2–3 asset sanity test; solver-status assertions on every call (never trust an unchecked `problem.solve()`).
- **Common implementation mistakes:** Not shrinking/regularizing the covariance matrix (near-singular matrices cause unstable, extreme weights); silently accepting infeasible/inaccurate solver statuses.
- **Performance considerations:** Warm-starting the solver across rebalancing periods; caching problem structure when only parameters change.
- **Future improvements:** Higher-moment objectives (skew/kurtosis-aware), multi-period optimization with transaction costs.

### 5.7 Execution Engine
- **Purpose:** Translate target weights into child orders with minimized market impact.
- **Inputs:** Target weights (from optimizer), current positions, volume/liquidity data.
- **Outputs:** Simulated (or live) order schedule and fills.
- **Algorithms:** VWAP order slicing, TWAP fallback, Almgren-Chriss-style impact modeling.
- **Libraries:** `numpy`/`pandas` for scheduling logic; a custom slippage model.
- **Data structures:** Order schedule (child orders with target time/size), fill log.
- **Alternatives:** TWAP-only for simplicity if volume prediction proves unreliable.
- **Expected runtime:** Real-time-capable for paper trading; backtest execution should run in line with the backtesting harness's cadence.
- **Testing strategy:** Compare implementation shortfall against academic benchmark ranges; stress-test with abnormal volume days.
- **Common implementation mistakes:** Zero or unrealistically low slippage assumptions that inflate backtest Sharpe ratios (flagged repeatedly in Section 16 — this is the single most common way student backtests lie).
- **Performance considerations:** N/A at FYP scale; matters more at HFT scale.
- **Future improvements:** Reinforcement-learning-based adaptive execution.

### 5.8 Walk-Forward Backtesting
- **Purpose:** Validate the full pipeline without look-ahead bias.
- **Inputs:** All upstream module outputs, chained.
- **Outputs:** Performance report (returns, Sharpe, Sortino, max drawdown, turnover, exposure over time).
- **Algorithms:** Rolling train/validate/test windows; purged/embargoed cross-validation if applicable.
- **Libraries:** Custom harness (`pandas`), `quantstats` or similar for reporting.
- **Data structures:** Time-indexed performance series, per-window model artifacts.
- **Alternatives:** N/A — walk-forward is the standard for time series; avoid k-fold cross-validation on financial time series.
- **Expected runtime:** Depends on number of windows × per-module runtime; budget hours for a full multi-year walk-forward with retraining at each step.
- **Testing strategy:** Shuffle test (destroy the regime signal — performance should degrade); leakage audit checklist run at every stage boundary.
- **Common implementation mistakes:** Refitting scalers/models on the full dataset before splitting; reusing the same test window across multiple strategy iterations (implicit overfitting via repeated peeking).
- **Performance considerations:** Cache intermediate artifacts per window to avoid recomputation during report iteration.
- **Future improvements:** Combinatorial purged cross-validation (Lopez de Prado) for more robust performance estimates.

### 5.9 Risk Management Engine
- **Purpose:** Independent guardrail on proposed portfolios and trades.
- **Inputs:** Portfolio weights, Monte Carlo scenarios, exposure limits config.
- **Outputs:** VaR/CVaR estimates, limit-breach flags, kill-switch signal.
- **Algorithms:** Historical/parametric/Monte-Carlo VaR, CVaR (expected shortfall).
- **Libraries:** `numpy`/`pandas`, reuse of the Monte Carlo module's scenario output.
- **Data structures:** Risk report object, limit configuration schema.
- **Alternatives:** Semi-parametric risk models if normality assumptions are too strong.
- **Expected runtime:** Sub-second for a VaR calc given precomputed scenarios.
- **Testing strategy:** Backtested VaR breach frequency must statistically match the stated confidence level (Kupiec test or similar).
- **Common implementation mistakes:** Risk engine using a different covariance estimate than the optimizer (inconsistent risk views across the system).
- **Performance considerations:** N/A at this scale.
- **Future improvements:** Stress-testing against historical crisis scenarios, not just simulated ones.

### 5.10 FastAPI Microservices
- **Purpose:** Expose modules as stable, documented services.
- **Inputs/Outputs:** Pydantic-validated JSON per endpoint.
- **Algorithms:** N/A (service layer).
- **Libraries:** `FastAPI`, `Pydantic`, `uvicorn`.
- **Data structures:** Request/response schemas.
- **Alternatives:** Flask (see Section 8 for why FastAPI is preferred).
- **Testing strategy:** Contract tests, OpenAPI schema validation, load testing at expected concurrency.
- **Common implementation mistakes:** Business logic inside route handlers instead of imported from the underlying module (makes the module untestable without spinning up the API).
- **Future improvements:** Async endpoints for I/O-bound calls once synchronous baseline is proven correct.

### 5.11 Flutter Dashboard
- **Purpose:** Visualize system state for the user/researcher.
- **Inputs:** FastAPI endpoints only.
- **Outputs:** Regime timeline, portfolio composition, risk metrics, backtest charts.
- **Libraries:** `Flutter`/`Dart`, an HTTP client package, a charting package.
- **Testing strategy:** Widget tests, and a "no mock data in production build" check.
- **Common implementation mistakes:** Coupling UI directly to a specific backend response shape instead of a stable DTO, causing breakage on every backend refactor.

### 5.12 Multi-Agent Layer
- **Purpose:** Coordinate modules as autonomous agents rather than a single hardcoded script.
- **Inputs/Outputs:** Calls to the FastAPI layer; shared state in Postgres.
- **Algorithms:** Rule-based or LLM-augmented agent decision logic; simple message-passing protocol.
- **Libraries:** Plain Python orchestration to start; LLM API integration only if the project scope explicitly calls for it.
- **Testing strategy:** End-to-end trace logging of a full agent decision cycle; deterministic replay tests.
- **Common implementation mistakes:** Giving agents direct database/model access instead of routing through the same service contracts everything else uses (breaks the "one source of truth" principle).

### 5.13 DevOps
- **Purpose:** Build, test, deploy, and monitor the system reliably.
- **Inputs/Outputs:** Source repo in, running staging/production environment out.
- **Libraries/Tools:** `Docker`, `docker-compose`, `GitHub Actions`, `Alembic` (migrations), a logging/monitoring stack (see Section 12).
- **Testing strategy:** Pipeline itself is tested — a broken Dockerfile or migration should fail CI, not production.
- **Common implementation mistakes:** Secrets committed to the repo; no database migration versioning (manual schema drift between dev and prod).


---

## 6. Mathematical Foundations

### Data Pipeline / Feature Engineering
- **Mathematics required:** Basic time series concepts — log returns vs. simple returns, stationarity, rolling statistics.
- **Concepts to master:** Why log returns are preferred for additivity across time; realized volatility estimation.
- **Common misconceptions:** Treating price levels as stationary inputs to models (they are not — always work in returns or normalized features).

### Regime Detection (HMM)
- **Mathematics required:** Markov chains, conditional probability, the Expectation-Maximization algorithm, the Forward-Backward and Viterbi algorithms.
- **Papers to understand:** Hamilton (1989) for the regime-switching framework; Jalen & Mamon (2014) for non-normal emissions.
- **Concepts to master:** Why EM only guarantees a local optimum (non-convex likelihood surface); how BIC penalizes model complexity to select state count.
- **Equations involved:** The HMM joint likelihood factorization; the Baum-Welch update equations for transition and emission parameters.
- **Common misconceptions:** Believing more hidden states always means a better model — more states without more data increases variance without necessarily improving fit (BIC exists precisely to correct for this).

### Representation Learning
- **Mathematics required:** Backpropagation through time, gradient descent variants (Adam), basic linear algebra for attention mechanisms (dot-product similarity, softmax).
- **Concepts to master:** Why vanishing gradients motivated LSTM's gating mechanism; what self-attention computes conceptually (a weighted combination of all time steps, not just the immediately preceding one).
- **Common misconceptions:** Assuming a Transformer is strictly "better" than an LSTM regardless of dataset size — Transformers typically need more data to outperform recurrent baselines.

### Monte Carlo Simulation
- **Mathematics required:** Stochastic calculus basics (Brownian motion, Itô's lemma is optional background but not required to implement GBM), the law of large numbers underpinning why simulation converges.
- **Equations involved:** Geometric Brownian Motion SDE and its discretized simulation form; Cholesky decomposition for correlated multi-asset paths.
- **Common misconceptions:** Believing more simulated paths fixes a wrong model — Monte Carlo reduces sampling error, not model risk. A biased input assumption stays biased no matter how many paths you run.

### Portfolio Optimization (CVXPY)
- **Mathematics required:** Convex optimization fundamentals (why a local optimum is global under convexity), quadratic programming.
- **Papers to understand:** Markowitz (1952) for the mean-variance foundation; Boyd & Vandenberghe (2004) for the general convex optimization theory; Diamond & Boyd (2016) for CVXPY's modeling layer.
- **Concepts to master:** How adding constraints shrinks the feasible set and can change the optimal solution non-trivially; why the covariance matrix must be positive semi-definite for the problem to remain convex.
- **Common misconceptions:** Treating the efficient frontier as a stable, known object — in practice it is estimated with error, and small input perturbations can produce large swings in optimal weights (motivating shrinkage/regularization).

### Risk Management
- **Mathematics required:** Quantiles of a distribution (VaR), conditional expectation beyond a quantile (CVaR/Expected Shortfall).
- **Common misconceptions:** Treating VaR as a worst-case loss bound — VaR says nothing about the severity of losses beyond the threshold, which is exactly why CVaR is used alongside it.

### Execution Engine
- **Mathematics required:** Basic optimal control intuition (trading off market impact against timing risk).
- **Papers to understand:** Almgren & Chriss (2001) for the canonical impact-vs-risk tradeoff formulation.
- **Common misconceptions:** Modeling market impact as purely linear in order size across all size ranges — real impact is closer to a concave (square-root-like) function for larger orders.

---

## 7. Research Paper Mapping

| Module | Essential | Recommended | Advanced |
|---|---|---|---|
| Regime Detection | Hamilton (1989) — Markov-switching foundation | Mamon & Elliott (2014) — HMM applications in finance | Autoencoder-Transformer-RL regime-aware prediction (2026 preprint) |
| Representation Learning | — | Deep Learning for Financial Time Series survey | Fin-JEPA joint-embedding predictive architecture (2026); Contrastive asset embeddings (2024) |
| Portfolio Optimization | Markowitz (1952) — mean-variance foundation | Diamond & Boyd (2016) — CVXPY | Portfolio optimization of even moments via power cone programming (2026) |
| Convex Optimization | Boyd & Vandenberghe (2004) — Convex Optimization textbook | Multi-period trading via convex optimization (Stanford) | Differentiable convex optimization layers (BPQP, 2024 preprint) |
| Monte Carlo | — | Monte Carlo simulations for portfolio uncertainty (2025) | Regime-conditioned / quasi-Monte Carlo variants |
| Execution | Almgren & Chriss (2001) — optimal execution | VWAP/TWAP mechanics overviews | Deep learning for VWAP execution (2025); RL for trade execution |
| Risk Management | — | Risk management in quantitative finance overviews | Real-time deep-learning risk modeling (2026) |
| Financial ML (general) | Lopez de Prado (2018) — Advances in Financial Machine Learning | — | — |
| Multi-Agent Systems | — | Multi-agent systems for computational economics and finance | LLM-based multi-agent market simulation survey (2026) |
| MLOps / Production | — | MLOps in finance strategy guides | Multi-cloud fault-tolerant MLOps architecture (2026) |

**Why each matters, in one line:** Hamilton (1989) is cited in nearly every regime-detection paper since — skipping it means missing the vocabulary the rest of the literature assumes. Markowitz (1952) and Boyd & Vandenberghe (2004) are the same relationship one level down in the optimization module — everything CVXPY-related assumes this foundation. Lopez de Prado (2018) matters less for any single equation and more because it is the only source in this list written specifically to warn practitioners about the failure modes (leakage, overfitting, non-stationarity) that will otherwise sink this exact kind of project.

---

## 8. Technology Decisions

**Why FastAPI instead of Flask?** FastAPI gives you Pydantic-validated request/response schemas and auto-generated OpenAPI docs for free — for a system with this many inter-module contracts, schema validation at the boundary catches integration bugs immediately instead of as a silent `KeyError` three modules downstream. Flask requires bolting this on manually (e.g., via Marshmallow). FastAPI's async support also matters if any endpoint ends up calling a slow external data vendor.

**Why PyTorch instead of TensorFlow?** PyTorch's imperative execution model makes debugging a custom HMM-adjacent or attention architecture far more transparent (you can `print()`/breakpoint mid-forward-pass). Most recent financial deep learning research (including the papers cited in this document) ships PyTorch reference implementations, reducing translation overhead.

**Why PostgreSQL?** Relational integrity (foreign keys between `tickers`, `features`, `regime_history`, `portfolio_weights`) matters more here than raw write throughput. TimescaleDB (a Postgres extension) can be added later for time series-specific optimizations without a database migration to a different engine.

**Why CVXPY?** It expresses convex portfolio problems (QP, SOCP) in near-mathematical syntax, and swapping the underlying solver (ECOS, OSQP, SCS) requires no rewrite of the problem — useful when the problem size or constraint types change as the project matures.

**Why Docker?** Reproducibility of the entire stack (Postgres version, Python version, system libraries for numerical code) across the developer's machine, CI, and any deployment target — this matters more here than in most student projects because subtle numerical library version differences (BLAS backends, etc.) can change model outputs.

**Why HMM (over pure deep learning for regime detection)?** Interpretability and data efficiency. HMM states have a clear probabilistic meaning and can be fit on years, not decades, of daily data — deep generative alternatives typically need far more data than a single-market FYP dataset provides. HMM is the right starting point; deep-learning-augmented emissions are the documented upgrade path once the baseline is validated.

**Why Monte Carlo (over purely analytical risk formulas)?** Closed-form VaR under normality is fast but wrong in the tails — the entire premise of this project (regime-awareness) is that the distribution of returns changes shape across regimes, which Monte Carlo can represent and a single closed-form Gaussian formula cannot.

**Why Flutter?** Single codebase for a cross-platform dashboard (useful if the FYP demo needs to run on both a laptop and a phone), and its widget-based reactive model maps cleanly onto "redraw this chart when the FastAPI polling endpoint returns new data."

---

## 9. Project Folder Structure

```
aegisquant/
├── data_pipeline/
│   ├── ingestion/
│   ├── schema/
│   └── quality_checks/
├── feature_engineering/
│   ├── features/
│   └── registry.py
├── regime_detection/
│   ├── hmm/
│   └── evaluation/
├── representation_learning/
│   ├── models/
│   ├── training/
│   └── checkpoints/          # gitignored, artifact-versioned separately
├── monte_carlo/
│   └── simulators/
├── portfolio_optimization/
│   └── cvxpy_models/
├── risk_engine/
│   └── metrics/
├── execution_engine/
│   ├── scheduling/
│   └── slippage_models/
├── backtesting/
│   ├── harness/
│   └── reports/
├── services/                  # FastAPI apps, one router per module
│   ├── regime_service/
│   ├── portfolio_service/
│   ├── risk_service/
│   └── execution_service/
├── multi_agent/
│   └── agents/
├── dashboard/                  # Flutter app, separate build system
├── infra/
│   ├── docker/
│   ├── ci/                     # GitHub Actions workflows
│   └── migrations/             # Alembic
├── config/
│   ├── base.yaml
│   ├── dev.yaml
│   └── prod.yaml
├── tests/
│   ├── unit/
│   ├── integration/
│   └── validation/              # numerical/statistical sanity tests
├── notebooks/                   # exploration only — never imported by services/
├── docs/
├── .env.example
├── docker-compose.yml
└── README.md
```

**Folder rationale:** Each top-level directory corresponds to exactly one module from Section 5 — this 1:1 mapping is deliberate so the dependency graph in Section 4 is directly visible in the repo layout. `services/` is kept separate from the modules themselves to enforce the "route handlers import logic, they don't contain it" rule from Section 2.

**Naming conventions:** `snake_case` for all Python files/modules; test files mirror the module they test (`portfolio_optimization/mvo.py` → `tests/unit/test_mvo.py`); config keys use `lower_snake_case` and are never duplicated across environment files (only overridden).

**Configuration management:** A single `config/base.yaml` holds defaults; `dev.yaml`/`prod.yaml` only override what differs. Secrets (API keys, DB passwords) never live in any YAML file — they come from environment variables injected via `.env` (local) or the deployment platform's secret store (see Section 13).

---

## 10. Git Strategy

**Branch strategy:** Trunk-based with short-lived feature branches — `main` is always deployable. Branch naming: `feature/<module>-<short-description>`, `fix/<module>-<short-description>`. No long-running per-developer branches; merge (via PR) at least every few days to avoid painful integration conflicts across modules that share the feature-table schema.

**Commit conventions:** Conventional Commits format — `feat(regime-detection): add BIC-based state selection`, `fix(execution): correct VWAP volume curve off-by-one`, `test(portfolio): add closed-form 2-asset sanity check`. This makes it possible to auto-generate a changelog and to `git log --grep` by module during debugging.

**Release strategy:** Tag releases at meaningful milestones (`v0.1-data-pipeline-complete`, `v0.5-full-pipeline-backtest`, `v1.0-fyp-submission`) rather than on a fixed schedule — this project's milestones are stage-exit-criteria-driven (Section 3), not calendar-driven.

**Versioning:** Semantic versioning for the repo overall (`MAJOR.MINOR.PATCH`); model artifacts are versioned separately with their own scheme (`model_name-vN-<data_hash>-<config_hash>`) so a model checkpoint can be traced back to the exact code+data+config that produced it, independent of the repo's git tag.


---

## 11. Testing Strategy

**Unit testing:** Every pure function (feature calculators, the HMM's likelihood computation, the optimizer's constraint builder) gets a direct unit test with hand-computable expected output. Target: every module in Section 5 has unit tests before it is considered "done" per its Stage exit criteria.

**Integration testing:** Tests that cross exactly one module boundary — e.g., "feature engineering output is consumable by regime detection without a schema mismatch." These live in `tests/integration/` and run against a test database seeded with fixture data, not production data.

**Model validation:** Statistical, not just functional. Regime detection: BIC comparison across state counts, log-likelihood improvement over baseline. Representation learning: beat naive persistence baseline out-of-sample via walk-forward split. Monte Carlo: convergence and correlation-preservation tests. This is validation of correctness of the *statistics*, distinct from validation of correctness of the *code*.

**Backtesting validation:** The shuffle test (Section 3, Stage 9) is the core sanity check — if shuffling regime labels doesn't degrade performance, the signal isn't being used, and reported performance is not to be trusted regardless of how good the Sharpe ratio looks.

**Stress testing:** Replay the pipeline through known historical crisis windows (2008, March 2020, 2022 rate-hike cycle) and confirm the risk engine's limits/kill-switch actually trigger — a risk system that has never been tested against a real crisis is untested by definition.

**Performance testing:** Load-test the FastAPI layer at expected concurrency; time-budget the Monte Carlo and backtesting harness (these are the two most likely modules to blow up in runtime as scope grows).

**Regression testing:** Every bug fix gets a regression test that reproduces the bug before the fix and passes after. CI blocks merges that reduce test coverage on touched files below an agreed threshold.

---

## 12. DevOps Pipeline

**Docker:** One `Dockerfile` per service under `infra/docker/`, all sharing a common base image (pinned Python version + shared system dependencies) to avoid version drift between services. `docker-compose.yml` orchestrates the full local stack: Postgres, all FastAPI services, and (optionally) n8n.

**CI/CD (GitHub Actions):** Pipeline stages — lint (`ruff`/`flake8` + `mypy`) → unit tests → integration tests (against a spun-up test Postgres container) → build Docker images → (on `main` only) deploy to staging. Production deploy is a manual-approval gate, never automatic.

**Database migrations:** `Alembic` for all schema changes — no manual `ALTER TABLE` on any environment. Every migration is committed alongside the code change that requires it, and CI runs migrations against a fresh database as part of the integration test stage to catch migration bugs before they hit staging.

**Deployment:** Staging environment mirrors production configuration (same Docker images, different environment variables/secrets). Blue-green or simple rolling restart is sufficient at FYP scale — no need for a full orchestrator like Kubernetes unless the project scope explicitly requires demonstrating it.

**Logging:** Structured JSON logging (not `print`) from every service, with a correlation ID threaded through a request as it crosses module boundaries (e.g., one "rebalance cycle ID" tags the regime lookup, the optimization call, and the resulting order log so a full cycle can be reconstructed from logs alone).

**Monitoring:** At minimum — service uptime/health checks, request latency per endpoint, and a small set of business-logic alerts (regime detector hasn't updated in > N hours; risk engine kill-switch triggered; solver failure rate above threshold). Prometheus + Grafana is a reasonable stack if time permits; a simpler cron-based health-check script is an acceptable minimum for an FYP.

**Secrets management:** Environment variables only, sourced from `.env` locally (gitignored) and from the CI/CD platform's encrypted secrets store in pipelines — never committed, never logged.

**Configuration management:** As described in Section 9 — layered YAML with environment-specific overrides, secrets excluded entirely and injected separately.

---

## 13. Security Considerations

**API security:** All FastAPI endpoints require authentication (even for an FYP demo — an API key or JWT bearer token is sufficient) once the system is reachable outside `localhost`. Rate limiting on any endpoint that triggers expensive computation (Monte Carlo, backtests) to prevent accidental or malicious resource exhaustion.

**Database security:** Least-privilege DB roles — the ingestion service should not have write access to `portfolio_weights`, and the dashboard's read-only queries should use a role that cannot write at all. Connection strings and credentials only via environment variables.

**Secrets:** Never in git history (use `git-secrets` or a pre-commit hook to catch accidental commits); rotate any credential that is accidentally exposed rather than assuming a force-push removes the exposure.

**Authentication:** If the dashboard has any notion of a "user," use a standard library (e.g., `fastapi-users` or a well-reviewed JWT flow) rather than hand-rolled auth — hand-rolled authentication is one of the most common sources of security bugs in student projects.

**Data integrity:** Foreign key constraints in Postgres to prevent orphaned records (a `portfolio_weights` row referencing a nonexistent `ticker`), and checksums/hashes on model artifacts so a corrupted or tampered checkpoint is detected before being loaded into a live-serving path.

---

## 14. Performance Optimization

**Memory optimization:** Use `float32` instead of `float64` for large Monte Carlo arrays where the precision loss is immaterial; stream large historical loads rather than materializing the entire history in memory at once.

**Parallel computing:** Monte Carlo path generation is embarrassingly parallel — batch across processes (`multiprocessing`) or vectorize fully in `numpy` before reaching for parallelism, since a well-vectorized single-process implementation often outperforms a naively parallelized one.

**Vectorization:** No Python-level `for` loops over time steps or assets in feature engineering, Monte Carlo, or backtesting — every one of these should be expressible as array operations. This is the single highest-leverage performance fix available in this stack.

**Caching:** Cache expensive-but-stable computations (covariance matrix estimation, regime classification for a given historical date) so re-running a backtest report doesn't recompute upstream stages unnecessarily. Content-addressable caching (hash of inputs → cached output) avoids stale-cache bugs.

**Database optimization:** Indexes on `(ticker, timestamp)` for all time series tables; partition large tables by date range if the history grows large enough to matter; use `EXPLAIN ANALYZE` on any query that becomes a bottleneck rather than guessing.

**Inference optimization:** For the representation learning model, batch inference requests rather than serving one prediction at a time; consider exporting to `ONNX` or `TorchScript` if serving latency becomes a bottleneck (unlikely to be necessary at FYP scale, but documented as the upgrade path).

---

## 15. Risk Register

| Risk | Category | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| Look-ahead bias undetected until late in the project | Research | High | Severe | Point-in-time correctness tests from Stage 2 onward; shuffle test at the backtesting stage |
| HMM converges to degenerate/uninformative states | Research | Medium | Moderate | Multiple EM restarts, BIC-based state selection, sanity-check against known historical regimes |
| Deep learning model overfits limited financial history | Research | High | Moderate | Walk-forward validation only, strong regularization, simple baselines required to beat before adding complexity |
| Unrealistic execution/slippage assumptions inflate backtest performance | Implementation | High | Severe | Explicit slippage model with published-benchmark sanity checks (Section 5.7) |
| CVXPY solver returns infeasible/inaccurate status silently | Implementation | Medium | Severe | Mandatory solver-status assertion on every optimization call |
| Scope creep — multi-agent/LLM layer absorbs disproportionate time | Timeline | High | Moderate | Strict adherence to the build order (Section 3); multi-agent layer is explicitly late-stage and optional-depth |
| Database schema drift between developers | Implementation | Medium | Moderate | Alembic migrations mandatory, no manual schema changes |
| Data vendor access lost/rate-limited near deadline | Timeline | Medium | Severe | Cache a full historical snapshot early (Stage 1); do not depend on live API access for the final backtest run |
| Dashboard built against an unstable API contract, requiring rework | Timeline | High | Moderate | Freeze FastAPI schemas before dashboard work starts (Section 4.3) |
| Supervisor/examiner questions the statistical validity of reported performance | Research | Medium | Severe | Document every validation test (shuffle test, VaR breach frequency, walk-forward methodology) explicitly in the final report, not just the results |


---

## 16. Things That Usually Go Wrong

Organized by category. Each item includes the fix, not just the symptom.

### Data & Feature Engineering (1–14)
1. **Using close prices without adjusting for splits/dividends** → returns show fake discontinuities. Fix: use adjusted close or explicitly apply corporate action adjustments.
2. **Survivorship bias in the asset universe** (only including companies that still exist today) → inflated backtest returns. Fix: use a point-in-time constituent list if available, or explicitly disclose the limitation.
3. **Look-ahead bias in rolling windows** (accidentally centered windows, or using `shift(-1)`). Fix: unit test every rolling feature against a hand-built toy series.
4. **Mixing timestamps across timezones/exchange calendars.** Fix: normalize all timestamps to a single timezone and align to a shared trading calendar early.
5. **Silent NaN propagation** turning an entire feature column into NaN without anyone noticing. Fix: automated data-quality report as a CI-gated check.
6. **Treating price levels as stationary model inputs.** Fix: always transform to returns or explicitly detrend.
7. **Not versioning the feature-definition set**, so a "regime detection worked well" result can't be reproduced later. Fix: hash feature definitions and store alongside outputs.
8. **Recomputing features on the full dataset instead of point-in-time**, leaking future information into "historical" feature values. Fix: point-in-time correctness test (Stage 2 exit criterion).
9. **Ignoring outliers/fat-fingers in raw data** (a single bad tick skews rolling volatility for weeks). Fix: basic outlier detection/clipping in the ingestion quality checks.
10. **Hardcoding a specific date range everywhere** instead of parameterizing it, making it impossible to re-run on updated data.
11. **Using an inconsistent set of trading days across assets** when computing correlations, introducing spurious correlation from misaligned dates.
12. **Not testing what happens with missing data for a newly-listed or delisted ticker.**
13. **Overengineering feature engineering before a baseline model exists** — dozens of features with no model to show they matter.
14. **Forgetting to exclude the target variable's own future value from a feature** (e.g., accidentally including next-day return as a "feature").

### Regime Detection / Modeling (15–30)
15. **Choosing the number of HMM states by eyeballing a plot instead of BIC/AIC.**
16. **Not restarting EM from multiple initializations**, silently accepting a local optimum.
17. **Ignoring label-switching between retrainings** — state 0 in January isn't necessarily state 0 in June.
18. **Assuming Gaussian emissions when returns are visibly fat-tailed.** Fix: consider Student-t or mixture emissions.
19. **Fitting a multivariate HMM on too many correlated features**, hitting the curse of dimensionality. Fix: curate/select features deliberately (Section 5.4).
20. **Never sanity-checking regimes against known historical events** (does the model actually flag March 2020 as high-volatility?).
21. **Treating the regime label as ground truth** rather than a probabilistic, noisy signal — downstream modules should use regime probabilities, not just the hard Viterbi path, where feasible.
22. **Retraining the HMM on the full history every time**, silently incorporating future information into what's presented as a "live" regime signal.
23. **Random train/test splits on time series data** for any model (LSTM, HMM, GBM) — this is the single most common and most damaging mistake in student quant projects.
24. **Not comparing a deep learning model against a naive baseline** (persistence, simple moving average) before declaring it "works."
25. **Reporting in-sample metrics as if they were out-of-sample performance.**
26. **Using global normalization statistics (mean/std) computed on the full dataset** instead of fold-specific statistics, leaking information across the train/test boundary.
27. **Overfitting a Transformer/LSTM on a small financial dataset** without adequate regularization or a simpler baseline to compare against.
28. **Not checking model calibration** (do predicted probabilities/regimes actually correspond to observed frequencies?).
29. **Silently letting model training diverge (NaN loss) without an automated check.**
30. **Not saving the exact config used to train a model**, making the result unreproducible a month later.

### Monte Carlo / Statistics (31–40)
31. **Simulating each asset's path independently**, ignoring the correlation structure entirely.
32. **Believing more simulated paths compensates for a wrong model** — path count fixes sampling error, not model bias.
33. **Using Python for-loops for path generation** instead of vectorized array operations, making simulation impractically slow.
34. **Not testing convergence** (do simulated moments actually approach the input parameters as path count grows?).
35. **Assuming constant volatility across the whole simulation horizon** when the whole point of the project is regime-awareness.
36. **Confusing VaR with a worst-case loss bound** rather than a quantile with no information about tail severity.
37. **Not backtesting VaR breach frequency against the stated confidence level.**
38. **Using the wrong random seed handling**, making "reproducible" simulations actually non-reproducible across runs.
39. **Ignoring numerical stability issues in covariance matrix estimation** (near-singular matrices from too few observations relative to asset count).
40. **Not documenting the distributional assumptions behind the risk numbers presented to a supervisor/examiner.**

### Portfolio Optimization (41–52)
41. **Not checking the CVXPY solver status** and silently using a non-optimal or infeasible result.
42. **Using a raw, unshrunk sample covariance matrix**, producing extreme, unstable weights.
43. **Ignoring transaction costs/turnover in the objective**, producing a strategy that looks great before costs and terrible after.
44. **Forgetting to constrain weights to sum to 1 (or the intended leverage)** and not catching this in tests.
45. **Not testing the optimizer against a hand-computable closed-form case** before trusting it on real data.
46. **Setting overly tight constraints that make the problem infeasible**, and not handling that gracefully in code.
47. **Re-optimizing every single day without a turnover penalty**, generating unrealistic amounts of trading in backtest.
48. **Not distinguishing between the covariance matrix used for optimization and the one used for risk reporting** — they should come from the same estimation source.
49. **Treating the efficient frontier as a fixed, known curve** rather than an estimate with its own error bars.
50. **Not comparing the optimized portfolio against a naive baseline** (equal-weight, market-cap-weight).
51. **Numerical issues from mixing units** (e.g., returns in percent vs. decimal) between the forecast module and the optimizer.
52. **Ignoring solver warm-starting**, unnecessarily slowing down repeated re-optimization in a backtest loop.

### Execution & Backtesting (53–66)
53. **Assuming zero or negligible slippage** — the single most common way a backtest lies about real-world performance.
54. **Filling orders at the historical close price with no market impact modeling at all.**
55. **Not modeling partial fills** or the possibility that a large order simply cannot be fully executed at the assumed price.
56. **Backtesting on the same data used to select the strategy's hyperparameters** (implicit overfitting through repeated peeking).
57. **Using k-fold cross-validation on time series** instead of walk-forward validation.
58. **Not running the shuffle test** to confirm the regime signal is actually contributing to performance.
59. **Silently allowing look-ahead bias to reappear when modules are chained**, even if each module passed its individual leakage test.
60. **Not accounting for survivorship bias in the backtest universe** (see item 2, but specifically relevant again at the backtest report stage).
61. **Reporting a single backtest run's Sharpe ratio without any measure of estimation uncertainty.**
62. **Cherry-picking the backtest date range** to show favorable performance.
63. **Not testing the pipeline's behavior during known crisis periods explicitly.**
64. **Ignoring the compounding effect of daily rebalancing costs over a multi-year backtest.**
65. **Treating backtest Sharpe ratio as a prediction of future live performance** rather than a noisy, in-sample-adjacent estimate.
66. **Not versioning backtest reports alongside the exact code/data/config that produced them.**

### Software Engineering / Architecture (67–80)
67. **Putting business logic directly inside FastAPI route handlers**, making it untestable without spinning up the whole API.
68. **No config system** — hardcoded file paths and magic numbers scattered across the codebase.
69. **Notebooks that get imported into production code** instead of being exploration-only.
70. **No automated tests at all**, "testing" only by manually running scripts and eyeballing output.
71. **Tight coupling between the dashboard and a specific backend response shape**, breaking on every backend change.
72. **Giving the multi-agent layer direct database/model access** instead of routing through the same service contracts as everything else.
73. **Not using type hints**, making refactors error-prone and IDE assistance useless.
74. **Committing large model checkpoints directly to git** instead of using artifact storage or Git LFS.
75. **No logging, or `print()`-based logging** that's impossible to search/filter in production.
76. **Not handling exceptions explicitly** — bare `except:` blocks that silently swallow real bugs.
77. **Building the dashboard before the API contract is stable**, causing repeated, wasted rework.
78. **Building the multi-agent layer first "because it's the most interesting part"** before any underlying service actually works.
79. **No dependency pinning**, so the environment silently breaks when an upstream package releases a breaking change.
80. **Circular imports between modules** because separation of concerns wasn't respected from the start.

### DevOps / Deployment (81–90)
81. **Secrets committed to git history**, sometimes discovered only after the repo is public.
82. **No database migration tooling**, causing schema drift between dev, staging, and (if applicable) production.
83. **Docker images that aren't reproducible** because they pull `latest` tags for dependencies instead of pinned versions.
84. **No CI pipeline**, so broken code reaches `main` regularly.
85. **No staging environment**, testing changes directly against what would be the production database.
86. **No monitoring/alerting**, meaning a silently broken regime detector or failed nightly ingestion job goes unnoticed for days.
87. **Manual deployment steps that aren't documented**, making the system undeployable if the original developer is unavailable.
88. **Not load-testing the API before a live demo**, discovering performance issues in front of the examiner.
89. **Environment-specific configuration hardcoded instead of injected**, making "it works on my machine" a recurring problem.
90. **No backup/restore strategy for the database**, risking total data loss from a single mistake.

### Project & Research Management (91–100+)
91. **Starting with the most exciting module (deep learning, multi-agent) instead of the foundational one (data pipeline).**
92. **Underestimating how long data cleaning and validation actually takes** — it is reliably the most time-consuming "boring" stage.
93. **Not keeping a research log of what was tried and why it failed** — repeating failed experiments months later.
94. **Scope creep** — adding features (live trading, more asset classes, an LLM chatbot) that aren't in the original plan without re-negotiating the timeline.
95. **Leaving integration between modules until the final weeks**, discovering interface mismatches too late to fix properly.
96. **Not documenting statistical validation methodology**, leaving the final report unable to defend its performance claims under examiner scrutiny.
97. **Treating the FYP supervisor's early feedback as optional** rather than as a scope-correcting checkpoint.
98. **No clear "definition of done" per module**, leading to endless polishing of one module while others are neglected.
99. **Not budgeting time for the write-up itself**, cramming documentation into the final week.
100. **Presenting backtest performance without disclosing its limitations** (slippage assumptions, survivorship bias, in-sample tuning) — an examiner who asks "what would break this result?" should get a real answer, not a defensive one.
101. **Not having a working end-to-end demo well before the deadline**, discovering an integration bug the night before submission.
102. **Comparing the final strategy against no benchmark at all**, making "is this actually good" unanswerable.


---

## 17. Recommended Weekly Roadmap

One-year timeline, organized into seven phases that mirror the build order in Section 3. Each week specifies its learning/research focus, development objective, documentation/testing objective, and the expected milestone. Weeks are intentionally front-loaded on foundations — this is deliberate, per Section 16, item 92.

### Phase 1 — Foundations & Data Pipeline (Weeks 1–8)

| Week | Learning / Research Objective | Development Objective | Documentation / Testing Objective | Milestone |
|---|---|---|---|---|
| 1 | Read Hamilton (1989) intro sections; survey the literature review's foundational tier | Repo scaffolding, Docker/Postgres skeleton (Stage 0) | Write `README.md` setup instructions | Repo runs via `docker-compose up` |
| 2 | Study point-in-time data correctness and survivorship bias | Choose asset universe; write ingestion scripts | Data dictionary draft | Historical OHLCV loading for 5 test tickers |
| 3 | Study exchange calendars, corporate actions | Extend ingestion to full universe; handle splits/dividends | Data-quality check script + first report | Full universe loads without critical data-quality issues |
| 4 | Read Lopez de Prado (2018) chapters on data structures | Idempotency fixes; incremental update job | Unit tests for ingestion idempotency | Stage 1 exit criteria met |
| 5 | Study log returns, realized volatility estimators | Begin feature engineering library (returns, vol) | Golden-value unit tests on toy series | First 5 features computed and stored |
| 6 | Study rolling-window look-ahead bias patterns | Expand feature set (correlation, momentum) | Point-in-time correctness test suite | Feature table covers full universe/history |
| 7 | Review CI/CD basics (GitHub Actions) | Set up CI pipeline: lint + unit tests | CI badge in README | CI green on every PR |
| 8 | Buffer / catch-up week | Fix any Stage 1–2 issues found in review | Write up "Data Pipeline & Feature Engineering" section of final report (draft) | **Milestone: Stages 0–2 complete** |

### Phase 2 — Regime Detection (Weeks 9–16)

| Week | Learning / Research Objective | Development Objective | Documentation / Testing Objective | Milestone |
|---|---|---|---|---|
| 9 | Deep-dive Hamilton (1989); Markov chain theory | Implement Baum-Welch/Viterbi (baseline Gaussian HMM) | Unit tests on synthetic 2-state data | Baseline HMM fits and decodes correctly |
| 10 | Study BIC/AIC model selection | Implement state-count selection sweep | Evaluation notebook: regimes vs. known events | Regimes align visually with historical stress periods |
| 11 | Read Jalen & Mamon (2014) on non-normal emissions | Extend HMM to non-Gaussian emissions | Compare log-likelihood vs. Gaussian baseline | Non-normal emission model outperforms baseline |
| 12 | Research feature selection for HMMs | Implement feature curation for emission set | Multiple-restart EM test for local optima | Stable, reproducible HMM given fixed seed |
| 13 | Study label-switching problem | Build `regime_history` table + versioning | Regression test for label-switching detection | Regime output stored and queryable |
| 14 | Review FastAPI basics | Wrap regime detector in a minimal `/regime/current` endpoint | Contract test for endpoint schema | First working microservice |
| 15 | Buffer / refine regime module based on supervisor feedback | Address feedback; polish evaluation notebook | Update data dictionary with regime schema | Supervisor checkpoint review |
| 16 | Consolidate learnings | Freeze regime detection module API | Write "Regime Detection" section of final report (draft) | **Milestone: Stage 3 complete** |

### Phase 3 — Representation Learning & Monte Carlo (Weeks 17–24)

| Week | Learning / Research Objective | Development Objective | Documentation / Testing Objective | Milestone |
|---|---|---|---|---|
| 17 | Review LSTM architecture and backprop-through-time | Implement LSTM baseline training pipeline | Walk-forward split validation harness (shared with Phase 4) | LSTM baseline trains without divergence |
| 18 | Study attention/Transformer basics | Add naive-persistence baseline comparison | Out-of-sample MSE/MAE report | LSTM beats naive baseline |
| 19 | Read the large-scale DL financial time series benchmark paper | Experiment with Transformer variant | Ablation notes (what changed performance) | Initial Transformer results logged |
| 20 | Study contrastive learning for embeddings (optional stretch) | Model checkpointing + config-based reproducibility | Reproducibility test (rerun from config matches) | Versioned model artifact system in place |
| 21 | Study Brownian motion / GBM simulation basics | Implement vectorized GBM Monte Carlo engine | Convergence test (simulated vs. true moments) | MC engine passes convergence test |
| 22 | Study variance reduction techniques | Add antithetic variates; multi-asset correlation via Cholesky | Correlation-preservation test | Multi-asset correlated simulation validated |
| 23 | Study regime-conditioned stochastic processes | Wire regime output into MC parameter switching | Compare regime-conditioned vs. static MC scenarios | Regime-aware simulation working end-to-end |
| 24 | Buffer / mid-year review | Address feedback from supervisor checkpoint | Write "Representation Learning" and "Monte Carlo" sections (draft) | **Milestone: Stages 4–5 complete; mid-year review** |

### Phase 4 — Portfolio Optimization & Risk (Weeks 25–32)

| Week | Learning / Research Objective | Development Objective | Documentation / Testing Objective | Milestone |
|---|---|---|---|---|
| 25 | Review Markowitz (1952) mean-variance theory | Implement basic CVXPY MVO | Closed-form 2-asset sanity test | MVO matches hand-computed solution |
| 26 | Study Boyd & Vandenberghe convexity fundamentals | Add no-short, position-limit constraints | Solver-status assertion tests | Constrained optimizer runs reliably |
| 27 | Study covariance shrinkage methods | Implement shrinkage estimator for covariance | Compare shrunk vs. raw covariance stability | Reduced weight instability observed |
| 28 | Study turnover/transaction-cost penalties | Add turnover penalty term to objective | Backtest comparing turnover with/without penalty | Realistic turnover levels achieved |
| 29 | Study VaR/CVaR theory | Implement VaR/CVaR calculator from MC scenarios | Kupiec-style VaR breach-frequency test | VaR breach rate statistically matches confidence level |
| 30 | Study exposure limits and kill-switch design | Implement risk-limit checker + kill switch | End-to-end test: risk engine vetoes a bad portfolio | Kill switch triggers correctly in test scenario |
| 31 | Review regime-conditioned risk aversion approaches | Connect regime output to optimizer risk-aversion parameter | Compare regime-aware vs. static risk aversion in backtest | Regime-aware optimization measurably differs from static |
| 32 | Buffer / consolidate | Freeze optimizer + risk engine APIs | Write "Portfolio Optimization" and "Risk Management" sections (draft) | **Milestone: Stages 6–7 complete** |

### Phase 5 — Execution & Backtesting Integration (Weeks 33–40)

| Week | Learning / Research Objective | Development Objective | Documentation / Testing Objective | Milestone |
|---|---|---|---|---|
| 33 | Read Almgren & Chriss (2001) | Implement VWAP order-slicing baseline | Unit test volume-curve slicing logic | Baseline VWAP scheduler working |
| 34 | Study slippage/market-impact models | Implement slippage model with realistic parameters | Compare implementation shortfall to published benchmark ranges | Slippage model within plausible range |
| 35 | Study implementation shortfall methodology | Build paper-trading simulator | End-to-end test: weights → orders → simulated fills | Paper-trading simulation runs fully |
| 36 | Review walk-forward validation methodology deeply | Build reusable walk-forward harness | Leakage-audit checklist run across full chain | Harness produces a clean walk-forward report |
| 37 | Study the shuffle-test methodology | Implement shuffle test on regime signal | Confirm performance degrades under shuffle | Shuffle test passes (signal proven to matter) |
| 38 | Study crisis-period stress testing | Run full pipeline through 2020, 2022 windows | Stress-test report | Risk engine behaves correctly in stress windows |
| 39 | Buffer / debug integration leakage issues | Fix any cross-module leakage found in chained backtest | Update leakage-audit documentation | Full pipeline passes end-to-end walk-forward |
| 40 | Consolidate | Freeze backtesting harness | Write "Execution Engine" and "Backtesting" sections (draft) | **Milestone: Stages 8–9 complete** |

### Phase 6 — Services, Multi-Agent, Dashboard (Weeks 41–46)

| Week | Learning / Research Objective | Development Objective | Documentation / Testing Objective | Milestone |
|---|---|---|---|---|
| 41 | Review FastAPI/OpenAPI best practices | Wrap remaining modules as services; freeze schemas | Contract tests for all endpoints | All modules exposed via stable API |
| 42 | Study multi-agent orchestration patterns | Implement agent roles (strategy/risk/execution agents) | End-to-end agent decision trace log | First full agent-orchestrated trading cycle |
| 43 | Review LLM-augmented multi-agent survey (if in scope) | Refine agent logic based on trace review | Deterministic replay test for agent cycle | Reproducible agent cycle |
| 44 | Review Flutter/Dart basics if not already familiar | Build dashboard skeleton against frozen API | Widget tests for core screens | Dashboard renders live regime + portfolio data |
| 45 | Study charting/visualization best practices | Add backtest report visualization to dashboard | "No mock data" build check | Dashboard fully data-driven from staging |
| 46 | Buffer / polish | Address usability feedback | Write "Multi-Agent" and "Dashboard" sections (draft) | **Milestone: Stages 10–12 complete** |

### Phase 7 — DevOps, Hardening & Final Report (Weeks 47–52)

| Week | Learning / Research Objective | Development Objective | Documentation / Testing Objective | Milestone |
|---|---|---|---|---|
| 47 | Review CI/CD and monitoring best practices | Finalize CI/CD pipeline, Alembic migrations | Full pipeline load test | Automated deploy to staging on push |
| 48 | Review security checklist (Section 13) | Implement API auth, least-privilege DB roles | Security review checklist completed | No secrets in repo; auth enforced |
| 49 | Review performance optimization checklist (Section 14) | Profile and optimize slowest stages (likely MC/backtest) | Performance benchmarks documented | Runtime within target budgets |
| 50 | Prepare final architecture self-review (Section 18 lens) | Final bug-fixing pass across all modules | Full regression test suite run | Zero known critical bugs |
| 51 | Rehearse demo; anticipate examiner questions | Freeze codebase for submission | Complete final report, including limitations (Section 16, item 100) | Full written report drafted |
| 52 | Final review | Final polish only — no new features | Proofread report; prepare demo script | **Milestone: Submission-ready system and report** |


---

## 18. Final Architecture Review

### As a Quant Researcher
The architecture correctly treats regime detection as a structural, upstream signal rather than a bolted-on feature — this is the right call and matches how the literature (Hamilton onward) actually frames the problem. My concern is estimation risk: every downstream module (Monte Carlo, portfolio optimization, risk) trusts covariance and regime estimates that are themselves noisy, and nothing in the current design explicitly propagates that uncertainty forward. A student version of this system will likely report a single point-estimate Sharpe ratio with no sense of how much that number would move under parameter uncertainty. **Improvement:** add a lightweight uncertainty-propagation step — even something as simple as re-running the backtest across a handful of covariance-shrinkage intensities and reporting the resulting Sharpe ratio range — before presenting any single headline number.

### As a Software Architect
The module boundaries are clean and the dependency graph (Section 4) is genuinely enforceable through the folder structure (Section 9) — that 1:1 mapping is a real strength and will save the team from the tangled-import problem that sinks most student systems of this scope. My concern is the two-pattern communication model (REST + shared Postgres tables): it's simple, which is good, but shared-table communication is an implicit contract that's easy to violate silently (a schema change in `features` breaks two downstream readers without either raising an error at write time). **Improvement:** add lightweight schema validation (e.g., a Pydantic model or `pandera` schema) at every shared-table write, not just at REST boundaries, so a schema break fails loudly and immediately rather than three modules downstream.

### As an ML Engineer
The build order correctly sequences a classical HMM baseline before the deep-learning-augmented regime model, and correctly demands the LSTM beat a naive persistence baseline before anything fancier is attempted — this discipline is exactly what prevents the common failure mode of "impressive-sounding model, worse than doing nothing." My concern is that walk-forward validation, while specified, is easy to get subtly wrong when modules are chained (Section 16, item 59) — leakage that doesn't exist in any single module's isolated test can appear once regime detection, representation learning, and the optimizer are all retrained on the same rolling window. **Improvement:** the shuffle test (Stage 9) is good but insufficient alone; add a second check — an explicit "embargo" period between train and test windows at every stage boundary, following Lopez de Prado's purged/embargoed cross-validation approach, to close this specific gap.

### As a DevOps Engineer
Docker-first, CI-gated, migration-managed from day one is the right baseline discipline, and the explicit choice to skip Kubernetes at this scale is sensible rather than resume-driven over-engineering. My concern is that monitoring (Section 12) is specified as a minimum viable cron-based health check, which is fine for a demo but will not catch the kind of slow-burn failure mode most likely to actually occur in this system — e.g., a regime detector that keeps running but silently degrades in quality after a data schema change upstream. **Improvement:** add at least one *statistical* monitor, not just an uptime check — e.g., alert if the regime distribution over the last 30 days looks implausible (one state disappearing entirely, or transition frequency spiking) — because this is the class of failure that a simple health check will never catch.

### As a University Supervisor
This is an ambitious scope for a Final Year Project — thirteen modules, a full MLOps layer, a multi-agent architecture, and a mobile-capable dashboard is closer to a small startup's year-one roadmap than a typical FYP. The build order and weekly roadmap show real awareness of that risk (front-loading foundations, explicit buffer weeks, an optional-depth framing for the multi-agent layer), which is exactly the kind of planning that keeps ambitious projects from collapsing in the final month. My core concern is examinable depth versus breadth: a committee is more likely to reward a smaller number of modules validated rigorously (with real statistical tests, not just "it ran without crashing") than a full pipeline where every module is shallow. **Recommendation:** if week 24 or week 32's buffer review shows the timeline slipping, cut multi-agent LLM integration and/or the Flutter dashboard's polish before cutting any of the validation/testing work in Sections 3, 11, or 16 — a working, rigorously validated five-module pipeline defends far better in a viva than a thirteen-module pipeline with untested statistical claims.

### Summary of Cross-Cutting Recommendations
1. Propagate estimation uncertainty forward, not just point estimates (Quant Researcher).
2. Validate shared-table contracts as strictly as REST contracts (Architect).
3. Add embargo periods to walk-forward validation, not just the shuffle test (ML Engineer).
4. Add at least one statistical/behavioral monitor, not only uptime checks (DevOps).
5. If timeline pressure hits, protect validation rigor over feature breadth (Supervisor).

---

*End of AegisQuant Master Development Blueprint v1.0.*
