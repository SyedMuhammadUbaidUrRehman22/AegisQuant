# Repository Guidelines

## Project Structure & Module Organization

AegisQuant is a Python 3.12 quantitative-research platform organized by domain. Core packages live at the repository root: `data_pipeline/`, `feature_engineering/`, `regime_detection/`, `portfolio_optimization/`, `risk_engine/`, `backtesting/`, `execution_engine/`, `monte_carlo/`, and `representation_learning/`. API code is under `services/`; shared environment settings and YAML profiles are in `config/`. Database migrations and container definitions live in `infra/`. Put automated tests in `tests/`, grouped into `tests/integration/` when they require PostgreSQL/TimescaleDB. Keep exploratory work in `notebooks/` and architecture or data documentation in `docs/`.

## Build, Test, and Development Commands

- `python -m pip install --constraint constraints.lock -e ".[dev]"` installs the project and pinned development tools.
- `docker compose up --build -d` starts the reproducible local stack; inspect it with `docker compose ps`.
- `python -m uvicorn services.health_service.main:app --host 127.0.0.1 --port 8000` runs the health API locally.
- `python -m alembic upgrade head` applies all committed schema migrations.
- `python -m ruff check .` and `python -m ruff format --check .` run lint and formatting checks.
- `python -m mypy` performs strict static type checking.
- `python -m pytest` runs the complete test suite.

## Coding Style & Naming Conventions

Use four-space indentation, double quotes, and a 100-character line limit. Ruff enforces imports and Python correctness; format code with `python -m ruff format .` before submitting. Mypy runs in strict mode, so add precise annotations and avoid untyped escape hatches. Name modules, functions, and fixtures in `snake_case`, classes in `PascalCase`, and constants in `UPPER_SNAKE_CASE`.

## Testing Guidelines

Pytest discovers `test_*.py` files and `test_*` functions under `tests/`. Mirror the relevant package or behavior in test names and use shared builders from `tests/factories.py`. Mark database-dependent tests with `@pytest.mark.database` and explicitly enabled provider tests with `@pytest.mark.external`. Add regression tests for bug fixes and integration coverage for migrations or persistence changes.

## Commit & Pull Request Guidelines

History uses short, imperative subjects such as `Harden ingestion versioning...` and `Fix SQLAlchemy result conversion...`. Keep each commit focused and explain non-obvious design choices in its body. Pull requests should summarize behavior changes, list verification commands, link related issues or blueprint sections, and include screenshots only for dashboard changes. Call out migrations, configuration changes, and compatibility risks explicitly.

## Security & Configuration

Copy `.env.example` for local configuration; never commit secrets or credentials. Make schema changes only through versioned Alembic revisions. Treat `docker compose down --volumes` as destructive because it removes local database data.
