"""Unit tests for layered Stage 0 configuration."""

from pathlib import Path

import pytest
from sqlalchemy import make_url

from config.settings import load_settings


def test_development_configuration_layers_over_base() -> None:
    """Development settings should inherit base values and override only differences."""

    settings = load_settings("dev", environ={})

    assert settings.app.name == "AegisQuant"
    assert settings.app.environment == "development"
    assert settings.app.log_level == "DEBUG"
    assert settings.database.host == "127.0.0.1"
    assert settings.database.password is None


def test_production_configuration_layers_over_base() -> None:
    """Production settings should select the production environment overrides."""

    settings = load_settings("prod", environ={})

    assert settings.app.environment == "production"
    assert settings.app.log_level == "WARNING"


def test_explicit_environment_values_override_yaml() -> None:
    """Runtime values should override non-secret YAML and inject the database secret."""

    settings = load_settings(
        "dev",
        environ={
            "AEGISQUANT_APP_PORT": "9000",
            "AEGISQUANT_DATABASE_HOST": "database",
            "AEGISQUANT_DATABASE_PASSWORD": "p@ss:word",
        },
    )

    assert settings.app.port == 9000
    assert settings.database.host == "database"
    url = make_url(settings.database.sqlalchemy_url())
    assert url.password == "p@ss:word"
    assert url.query["connect_timeout"] == "5"


def test_database_url_requires_runtime_password() -> None:
    """Database access should fail loudly when no secret was injected."""

    settings = load_settings("dev", environ={})

    with pytest.raises(RuntimeError, match="AEGISQUANT_DATABASE_PASSWORD"):
        settings.database.sqlalchemy_url()


def test_unknown_environment_is_rejected() -> None:
    """Only the two checked-in environment layers should be selectable."""

    with pytest.raises(ValueError, match="either 'dev' or 'prod'"):
        load_settings("staging", environ={})


def test_missing_configuration_directory_fails_loudly(tmp_path: Path) -> None:
    """A missing config file must not silently fall back to hardcoded values."""

    with pytest.raises(FileNotFoundError, match=r"base\.yaml"):
        load_settings("dev", environ={}, config_dir=tmp_path)
