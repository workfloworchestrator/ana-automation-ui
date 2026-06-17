from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

SmtpSecurity = Literal["none", "starttls", "tls"]


class Settings(BaseSettings):
    """Runtime configuration, populated from environment variables."""

    model_config = SettingsConfigDict(
        env_file="ana-automation-ui.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Address uvicorn binds to when started via the console script.
    host: str = "0.0.0.0"  # noqa: S104
    port: int = 8080
    log_level: str = "info"

    # Access-request email feature (point 5). Inert while disabled.
    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 25
    smtp_security: SmtpSecurity = "none"
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    access_request_recipient: str = ""
    access_request_from: str = ""
    access_request_from_user: bool = False

    # OIDC group names forwarded by oauth2-proxy (point 3).
    users_group: str = "users"
    operators_group: str = "operators"

    # Portal apps config rendered into a ConfigMap (point 4).
    apps_config_path: Path = Path("/config/apps.json")


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()
