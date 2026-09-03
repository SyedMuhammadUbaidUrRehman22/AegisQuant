FROM python:3.12.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN addgroup --system aegisquant \
    && adduser --system --ingroup aegisquant aegisquant

COPY . .
RUN python -m pip install --no-cache-dir --constraint constraints.lock . \
    && mkdir -p /app/data \
    && chown -R aegisquant:aegisquant /app

USER aegisquant

EXPOSE 8000

CMD ["uvicorn", "services.health_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
