"""Load validated settings from layered YAML and explicit environment overrides."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import URL

EnvironmentName = Literal["dev", "prod"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class AppSettings(BaseModel):
    """Settings owned by the Stage 0 health service."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    environment: Literal["development", "production"]
    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    log_level: LogLevel


class DatabaseSettings(BaseModel):
    """Database connection settings without any schema assumptions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    name: str = Field(min_length=1)
    user: str = Field(min_length=1)
    password: SecretStr | None = None
    connect_timeout_seconds: int = Field(ge=1, le=60)

    def sqlalchemy_url(self) -> str:
        """Return a psycopg SQLAlchemy URL, requiring a runtime password."""

        if self.password is None:
            raise RuntimeError("AEGISQUANT_DATABASE_PASSWORD is required for database access")

        url = URL.create(
            drivername="postgresql+psycopg",
            username=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            database=self.name,
            query={"connect_timeout": str(self.connect_timeout_seconds)},
        )
        return url.render_as_string(hide_password=False)


class DataPipelineSettings(BaseModel):
    """Validated settings for the Stage 1 historical ingestion pipeline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_name: Literal["yahoo_finance"]
    interval_code: Literal["1d"]
    historical_start: date
    raw_data_dir: Path
    request_timeout_seconds: int = Field(ge=1, le=300)
    max_attempts: int = Field(ge=1, le=10)
    backoff_base_seconds: float = Field(gt=0, le=60)
    backoff_cap_seconds: float = Field(gt=0, le=900)
    stale_run_after_seconds: int = Field(ge=60, le=86400)
    price_jump_warning_fraction: float = Field(gt=0)
    repeated_ohlc_warning_sessions: int = Field(ge=2, le=20)
    volume_spike_warning_multiple: float = Field(gt=1)
    volume_window_sessions: int = Field(ge=5, le=252)


class Settings(BaseModel):
    """Complete validated application settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    app: AppSettings
    database: DatabaseSettings
    data_pipeline: DataPipelineSettings


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML mapping and fail loudly for a missing or invalid configuration."""

    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with path.open(encoding="utf-8") as stream:
        raw: object = yaml.safe_load(stream)

    if not isinstance(raw, dict):
        raise ValueError(f"Configuration file must contain a mapping: {path}")
    return cast(dict[str, Any], raw)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Return a recursive merge without mutating either input mapping."""

    merged = dict(base)
    for key, value in override.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(cast(dict[str, Any], base_value), cast(dict[str, Any], value))
        else:
            merged[key] = value
    return merged


def _set_nested(payload: dict[str, Any], path: tuple[str, ...], value: object) -> None:
    """Set one validated environment override in a nested settings payload."""

    current = payload
    for key in path[:-1]:
        nested = current.get(key)
        if not isinstance(nested, dict):
            nested = {}
            current[key] = nested
        current = cast(dict[str, Any], nested)
    current[path[-1]] = value


_ENVIRONMENT_OVERRIDES: dict[str, tuple[tuple[str, ...], Callable[[str], object]]] = {
    "AEGISQUANT_APP_HOST": (("app", "host"), str),
    "AEGISQUANT_APP_PORT": (("app", "port"), int),
    "AEGISQUANT_APP_LOG_LEVEL": (("app", "log_level"), str),
    "AEGISQUANT_DATABASE_HOST": (("database", "host"), str),
    "AEGISQUANT_DATABASE_PORT": (("database", "port"), int),
    "AEGISQUANT_DATABASE_NAME": (("database", "name"), str),
    "AEGISQUANT_DATABASE_USER": (("database", "user"), str),
    "AEGISQUANT_DATABASE_PASSWORD": (("database", "password"), str),
    "AEGISQUANT_DATABASE_CONNECT_TIMEOUT_SECONDS": (
        ("database", "connect_timeout_seconds"),
        int,
    ),
    "AEGISQUANT_RAW_DATA_DIR": (("data_pipeline", "raw_data_dir"), Path),
    "AEGISQUANT_INGESTION_REQUEST_TIMEOUT_SECONDS": (
        ("data_pipeline", "request_timeout_seconds"),
        int,
    ),
    "AEGISQUANT_INGESTION_MAX_ATTEMPTS": (("data_pipeline", "max_attempts"), int),
}


def load_settings(
    environment: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    config_dir: Path | None = None,
) -> Settings:
    """Load base settings, apply one environment file, then explicit environment values."""

    environment_values = os.environ if environ is None else environ
    selected = environment or environment_values.get("AEGISQUANT_ENV", "dev")
    if selected not in {"dev", "prod"}:
        raise ValueError("AEGISQUANT_ENV must be either 'dev' or 'prod'")

    resolved_config_dir = config_dir or Path(__file__).resolve().parent
    payload = _deep_merge(
        _read_yaml(resolved_config_dir / "base.yaml"),
        _read_yaml(resolved_config_dir / f"{selected}.yaml"),
    )

    for variable, (path, converter) in _ENVIRONMENT_OVERRIDES.items():
        raw_value = environment_values.get(variable)
        if raw_value is not None:
            _set_nested(payload, path, converter(raw_value))

    return Settings.model_validate(payload)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process-wide immutable settings loaded once at service startup."""

    return load_settings()
