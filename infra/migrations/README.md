# Database Migrations

Alembic owns every database schema change. Revision `20260903_01` creates only the five Stage 1
market-data tables and converts `ohlcv_bars` into the daily TimescaleDB hypertable. The SQLAlchemy
Core metadata in `data_pipeline/schema/tables.py` mirrors the migration contract. Future changes
must be new revisions; do not edit a revision after it has been deployed.
