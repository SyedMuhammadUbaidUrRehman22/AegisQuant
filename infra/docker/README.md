# Docker Infrastructure

The foundation image runs the health service and contains the Stage 1 CLI for operational execution
with `docker compose exec health-service python -m data_pipeline ...`. Compose persists canonical
database state and generated snapshot/report data in separate named volumes. Later bounded-context
services should receive their own Dockerfiles only in their authorized stages.
