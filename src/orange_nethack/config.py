from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Strike configuration
    strike_api_key: str = ""  # Strike API key

    # Game settings
    ante_sats: int = 1000
    pot_initial: int = 10000

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
