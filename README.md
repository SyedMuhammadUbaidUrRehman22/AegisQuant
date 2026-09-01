# AegisQuant

AegisQuant is a regime-aware quantitative research and portfolio-management platform. The project
is currently at **Stage 0: Environment & Repo Scaffolding**. This iteration intentionally provides
only a reproducible foundation: a minimal FastAPI health service, an empty TimescaleDB/PostgreSQL
instance, configuration, migrations, tests, and CI. It contains no market-data ingestion, features,
models, portfolio logic, risk calculations, execution, backtests, agents, or dashboard application.

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

   To intentionally remove the local Stage 0 database volume, run `docker compose down --volumes`.

The database binds only to `127.0.0.1` by default. The Compose stack uses
`timescale/timescaledb:2.18.0-pg17`, waits for PostgreSQL readiness, and then starts the stateless
health service. No application tables are created.

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

Secrets are never stored in YAML. `AEGISQUANT_DATABASE_PASSWORD` is optional for the liveness
service but required before any database connection is attempted.

## Database migrations

Alembic is scaffolded under `infra/migrations/`. Stage 0 deliberately has no revisions or metadata
because market-data tables belong to Stage 1.

With a database running, either set `AEGISQUANT_DATABASE_URL` to a full SQLAlchemy URL or export the
individual database variables, then run:

```bash
python -m alembic upgrade head
```

All future schema changes must be committed Alembic revisions; manual schema changes are prohibited.

## Quality checks

Run the same checks used by CI:

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest
```

GitHub Actions also starts the pinned TimescaleDB image and verifies that the empty Alembic history
can connect and upgrade to `head`.

## Repository boundaries

Top-level packages mirror the blueprint dependency graph. Their short READMEs define ownership and
most are placeholders until their prescribed stage begins. Research/business logic belongs in its
module package; FastAPI code belongs in `services/`; notebooks are exploration-only and must never
be imported by production code.

## Troubleshooting

- `docker` is not recognized: install/start Docker Desktop and ensure Docker Compose v2 is available.
- Port 5432 or 8000 is occupied: change `POSTGRES_PORT` or `API_PORT` in `.env`.
- Compose rejects `POSTGRES_PASSWORD`: copy `.env.example` to `.env` and set a non-empty value.
- Python installation fails: confirm `python --version` reports 3.12.x and that the virtual
  environment is active.
- Configuration validation fails: inspect the named YAML/environment value; invalid or unknown
  configuration fails loudly by design.
