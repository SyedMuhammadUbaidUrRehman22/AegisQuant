# AegisQuant

AegisQuant is a regime-aware quantitative research and portfolio-management platform. The project
has implemented **Stages 0–2**: the reproducible foundation, a versioned and audited daily OHLCV
pipeline for the approved 20-ETF research universe, and deterministic point-in-time feature
engineering. Regime models, representation learning, portfolio logic, risk calculations, execution,
backtests, agents, and dashboard functionality remain intentionally unimplemented.

The authoritative architecture and build order are in
[`docs/AegisQuant_Master_Development_Blueprint.md`](docs/AegisQuant_Master_Development_Blueprint.md).
Development history is append-only in [`DEVELOPMENT_LOG.md`](DEVELOPMENT_LOG.md).

## Prerequisites

Choose one workflow:

- Docker Desktop with Docker Compose v2 (recommended and fully reproducible), or
- CPython 3.12 for local service/test development.

The container image pins Python 3.12.14. The Python package accepts Python 3.12.x only, every direct
runtime/development dependency is exactly pinned in `pyproject.toml`, and `constraints.lock` freezes
the resolved transitive dependency set used by local setup, Docker, and CI.

## Run with Docker Compose

1. Copy the environment template:

   PowerShell:

   ```powershell
   Copy-Item .env.example .env
   ```

   Bash:

   ```bash
   cp .env.example .env
   ```

2. Change `POSTGRES_PASSWORD` in `.env`. The supplied value is explicitly local-only.

3. Build and start the foundation:

   ```bash
   docker compose up --build -d
   ```

4. Verify container health and the API:

   ```bash
   docker compose ps
   curl http://127.0.0.1:8000/health
   ```

   Expected response:

   ```json
   {"service":"AegisQuant","status":"ok","version":"0.0.1","environment":"development"}
   ```

5. Stop the services without deleting database state:

   ```bash
   docker compose down
   ```

   To intentionally remove the local database volume, run `docker compose down --volumes`.

The database binds only to `127.0.0.1` by default. The Compose stack uses
`timescale/timescaledb:2.18.0-pg17`, waits for PostgreSQL readiness, and then starts the stateless
health service. The Stage 1 migration creates application tables only when Alembic is run.

## Local Python workflow

Create an isolated Python 3.12 environment:

PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --constraint constraints.lock ".[dev]"
```

Bash:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --constraint constraints.lock ".[dev]"
```

Run the service (database credentials are not required for the liveness-only API):

```bash
python -m uvicorn services.health_service.main:app --host 127.0.0.1 --port 8000
```

Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

## Configuration

Configuration follows the blueprint's two-layer model:

1. `config/base.yaml` is the single source of defaults.
2. `config/dev.yaml` or `config/prod.yaml` overrides only environment differences.
3. Explicit environment variables override YAML at runtime.

Select a layer with `AEGISQUANT_ENV=dev` (default) or `AEGISQUANT_ENV=prod`. Supported overrides are:

- `AEGISQUANT_APP_HOST`
- `AEGISQUANT_APP_PORT`
- `AEGISQUANT_APP_LOG_LEVEL`
- `AEGISQUANT_DATABASE_HOST`
- `AEGISQUANT_DATABASE_PORT`
- `AEGISQUANT_DATABASE_NAME`
- `AEGISQUANT_DATABASE_USER`
- `AEGISQUANT_DATABASE_PASSWORD`
- `AEGISQUANT_DATABASE_CONNECT_TIMEOUT_SECONDS`
- `AEGISQUANT_RAW_DATA_DIR`
- `AEGISQUANT_INGESTION_REQUEST_TIMEOUT_SECONDS`
- `AEGISQUANT_INGESTION_MAX_ATTEMPTS`

Secrets are never stored in YAML. `AEGISQUANT_DATABASE_PASSWORD` is optional for the liveness
service but required before any database connection is attempted.

## Database migrations

Alembic migrations are under `infra/migrations/`. Stage 1 creates instrument metadata, source
mappings, ingestion audit records, canonical OHLCV, corporate actions, and the TimescaleDB
hypertable. Stage 2 adds the versioned `feature_values` table. No Stage 3+ model tables exist.

With a database running, either set `AEGISQUANT_DATABASE_URL` to a full SQLAlchemy URL or export the
individual database variables, then run:

```bash
python -m alembic upgrade head
```

All future schema changes must be committed Alembic revisions; manual schema changes are prohibited.

## Stage 1 market-data ingestion

Yahoo Finance via `yfinance` is the sole canonical historical adapter. It is configured explicitly
for unadjusted daily OHLC, adjusted close, volume, and corporate actions; request end dates are
exclusive. Yahoo Finance access is intended for research/personal use and remains subject to the
provider's terms. Alpha Vantage is an optional, read-only validation source and never acts as an
automatic failover or writes canonical data.

With the database healthy and migrated, run:

```bash
python -m data_pipeline seed
python -m data_pipeline ingest --pilot --start 2008-01-02 --end 2026-09-03
python -m data_pipeline ingest --full --start 2008-01-02 --end 2026-09-03
python -m data_pipeline ingest --full --incremental
python -m data_pipeline inspect
```

Replace the example end date as needed. It is always exclusive; omitting it safely requests through
the prior civil day. Each instrument has an independent audit record and transaction. Provider
responses are stored as immutable, checksum-verified snapshots under `data/raw/`, and batch quality
reports are written under `data/reports/`; both directories are deliberately ignored by Git. Compose
persists `/app/data` in its `market_data` named volume, while host CLI runs use the local directory.

For the optional five-symbol secondary-source check, set `ALPHAVANTAGE_API_KEY` and run:

```bash
python -m data_pipeline compare-second-source
```

The canonical contract, table responsibilities, quality policy, and timestamp definitions are in
[`docs/stage_1_data_dictionary.md`](docs/stage_1_data_dictionary.md).

## Stage 2 feature materialization

Stage 2 reads canonical `ohlcv_bars` only and materializes five versioned daily features: adjusted
simple/log returns, 20-session rolling annualized volatility, 20-session momentum, and 60-session
rolling correlation to SPY. Every run requires an explicit, timezone-aware cutoff:

```bash
python -m feature_engineering --as-of 2026-09-04T21:00:00Z
```

The command applies both bar-time and information-time cutoffs, records warm-up or undefined values
explicitly, and writes in bounded transactional batches. Formulas and missing-data policies are in
[`feature_engineering/README.md`](feature_engineering/README.md).

## Quality checks

Run the same checks used by CI:

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest
```

GitHub Actions also starts the pinned TimescaleDB image, applies the migration, and executes the
database-marked integration and idempotency tests. Ordinary tests use deterministic fixtures and do
not require provider network access.

## Repository boundaries

Top-level packages mirror the blueprint dependency graph. Their short READMEs define ownership and
most are placeholders until their prescribed stage begins. Research/business logic belongs in its
module package; FastAPI code belongs in `services/`; notebooks are exploration-only and must never
be imported by production code.

## Troubleshooting

- `docker` is not recognized: install/start Docker Desktop and ensure Docker Compose v2 is available.
- Port 5432 or 8000 is occupied: change `POSTGRES_PORT` or `API_PORT` in `.env`.
- Compose rejects `POSTGRES_PASSWORD`: copy `.env.example` to `.env` and set a non-empty value.
- PostgreSQL rejects a newly changed password: `POSTGRES_PASSWORD` initializes credentials only when
  the database volume is first created. If and only if the local database is disposable, run
  `docker compose down --volumes` and start again; otherwise restore the original password or rotate
  it explicitly inside PostgreSQL rather than deleting the volume.
- Python installation fails: confirm `python --version` reports 3.12.x and that the virtual
  environment is active.
- Configuration validation fails: inspect the named YAML/environment value; invalid or unknown
  configuration fails loudly by design.
