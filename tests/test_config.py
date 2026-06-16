from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings

ENV_KEYS = (
    "HOST",
    "PORT",
    "EMAIL_ENABLED",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_SECURITY",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "ACCESS_REQUEST_RECIPIENT",
    "ACCESS_REQUEST_FROM",
    "ACCESS_REQUEST_FROM_USER",
    "USERS_GROUP",
    "OPERATORS_GROUP",
    "APPS_CONFIG_PATH",
)


@pytest.fixture
def clean_env(monkeypatch):
    [monkeypatch.delenv(key, raising=False) for key in ENV_KEYS]
    return monkeypatch


# --- happy paths -----------------------------------------------------------


def test_defaults(clean_env):
    settings = Settings(_env_file=None)
    assert (settings.host, settings.port) == ("0.0.0.0", 8080)  # noqa: S104
    assert settings.email_enabled is False
    assert settings.smtp_port == 25
    assert settings.smtp_security == "none"
    assert settings.access_request_from_user is False
    assert settings.users_group == "users"
    assert settings.operators_group == "operators"
    assert settings.apps_config_path == Path("/config/apps.json")


@pytest.mark.parametrize(
    ("env", "attr", "expected"),
    [
        pytest.param({"HOST": "127.0.0.1"}, "host", "127.0.0.1", id="host"),
        pytest.param({"PORT": "9000"}, "port", 9000, id="port-int-coercion"),
        pytest.param({"EMAIL_ENABLED": "true"}, "email_enabled", True, id="email-true"),
        pytest.param({"EMAIL_ENABLED": "0"}, "email_enabled", False, id="email-zero-false"),
        pytest.param({"SMTP_PORT": "587"}, "smtp_port", 587, id="smtp-port"),
        pytest.param({"SMTP_SECURITY": "starttls"}, "smtp_security", "starttls", id="security-starttls"),
        pytest.param({"SMTP_SECURITY": "tls"}, "smtp_security", "tls", id="security-tls"),
        pytest.param({"ACCESS_REQUEST_FROM_USER": "yes"}, "access_request_from_user", True, id="fromuser-yes"),
        pytest.param({"USERS_GROUP": "readers"}, "users_group", "readers", id="users-group"),
        pytest.param({"OPERATORS_GROUP": "admins"}, "operators_group", "admins", id="operators-group"),
        pytest.param(
            {"APPS_CONFIG_PATH": "/data/apps.json"}, "apps_config_path", Path("/data/apps.json"), id="apps-path"
        ),
    ],
)
def test_env_override(clean_env, env, attr, expected):
    [clean_env.setenv(key, value) for key, value in env.items()]
    assert getattr(Settings(_env_file=None), attr) == expected


@pytest.mark.parametrize(
    ("file_contents", "real_env", "attr", "expected"),
    [
        pytest.param("PORT=4321\n", {}, "port", 4321, id="value-from-file"),
        pytest.param("USERS_GROUP=readers\n", {}, "users_group", "readers", id="group-from-file"),
        pytest.param("PORT=4321\n", {"PORT": "9999"}, "port", 9999, id="real-env-overrides-file"),
    ],
)
def test_env_file_is_read(clean_env, tmp_path, file_contents, real_env, attr, expected):
    env_file = tmp_path / "ana-automation-ui.env"
    env_file.write_text(file_contents)
    [clean_env.setenv(key, value) for key, value in real_env.items()]
    assert getattr(Settings(_env_file=env_file), attr) == expected


# --- unhappy paths ---------------------------------------------------------


@pytest.mark.parametrize(
    "env",
    [
        pytest.param({"PORT": "not-a-number"}, id="port-non-numeric"),
        pytest.param({"SMTP_PORT": "abc"}, id="smtp-port-non-numeric"),
        pytest.param({"SMTP_SECURITY": "ssl"}, id="security-invalid-literal"),
        pytest.param({"EMAIL_ENABLED": "maybe"}, id="email-enabled-invalid-bool"),
        pytest.param({"ACCESS_REQUEST_FROM_USER": "sometimes"}, id="fromuser-invalid-bool"),
    ],
)
def test_invalid_env_raises(clean_env, env):
    [clean_env.setenv(key, value) for key, value in env.items()]
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
