import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_env_file() -> Path | None:
    """Get the .env file path, checking multiple locations."""
    # Check explicit environment variable first
    if env_path := os.environ.get("ORANGE_NETHACK_ENV_FILE"):
        return Path(env_path)

    # Check standard production location
    prod_env = Path("/opt/orange-nethack/.env")
    if prod_env.is_file():
        return prod_env

    # Fall back to current directory
    local_env = Path(".env")
    if local_env.is_file():
        return local_env

    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_get_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Strike configuration
    strike_api_key: str = ""  # Strike API key

    # Game settings
    ante_sats: int = 1000
    pot_initial: int = 0

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    database_path: Path = Path("/var/lib/orange-nethack/db.sqlite")
    webhook_secret: str = ""  # Optional webhook verification

    # Nethack settings
    nethack_binary: Path = Path("/usr/games/nethack")
    xlogfile_path: Path = Path("/var/games/nethack/xlogfile")
    nethack_user_prefix: str = "nh_"  # Prefix for created users
    nethack_group: str = "games"

    # Session settings
    session_timeout_hours: int = 24  # How long a session stays active
    max_active_sessions: int = 100  # Limit concurrent players

    # Development settings
    mock_lightning: bool = True  # Use fake Lightning payments for testing

    # SMTP settings for email notifications
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True

    @property
    def smtp_configured(self) -> bool:
        """Check if SMTP is properly configured."""
        return bool(self.smtp_host and self.smtp_from_email)


@lru_cache
def get_settings() -> Settings:
    return Settings()
