# Database Migrations

Alembic owns every database schema change. Stage 0 intentionally contains no revisions and no
domain tables. The first schema revision belongs to Stage 1 and must be introduced alongside its
data-ingestion contract and tests.
