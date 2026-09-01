# Health Service

This is the only service implemented during Stage 0. It exposes `GET /` and `GET /health`
with the same small, Pydantic-validated contract. The health endpoint proves process liveness;
it deliberately does not claim database readiness or expose later-stage business logic.

Run from the repository root:

```bash
uvicorn services.health_service.main:app --host 0.0.0.0 --port 8000
```
