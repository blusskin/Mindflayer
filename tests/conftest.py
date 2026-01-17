"""Pytest configuration and fixtures."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        path = Path(f.name)
    yield path
    if path.exists():
        path.unlink()


@pytest.fixture
def mock_settings(temp_db_path):
    """Mock settings for testing."""
    with patch("orange_nethack.config.get_settings") as mock:
        settings = mock.return_value
        settings.database_path = temp_db_path
        settings.pot_initial = 10000
        settings.ante_sats = 1000
        settings.nethack_user_prefix = "nh_"
        settings.nethack_group = "games"
        settings.lnbits_url = "https://test.lnbits.com"
        settings.lnbits_api_key = "test_api_key"
        settings.lnbits_admin_key = "test_admin_key"
        settings.xlogfile_path = Path("/tmp/test_xlogfile")
        settings.nethack_binary = Path("/usr/games/nethack")
        settings.max_active_sessions = 100
        settings.session_timeout_hours = 24
        yield settings
