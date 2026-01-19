"""Tests for API endpoints."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
import tempfile
from pathlib import Path


@pytest.fixture
def mock_lightning():
    with patch("orange_nethack.api.routes.get_lightning_client") as mock:
        client = MagicMock()
        client.create_invoice = AsyncMock(return_value=MagicMock(
            payment_hash="test_hash_123",
            payment_request="lnbc1000test...",
            amount_sats=1000,
            expires_at=None,
        ))
        client.check_payment = AsyncMock(return_value=False)
        mock.return_value = client
        yield client


@pytest.fixture
def mock_db():
    with patch("orange_nethack.api.routes.get_db") as mock:
        db = MagicMock()
        db.count_active_sessions = AsyncMock(return_value=0)
        db.get_pot_balance = AsyncMock(return_value=10000)
        db.create_session = AsyncMock(return_value=1)
        db.set_lightning_address = AsyncMock()
        db.get_session = AsyncMock(return_value={
            "id": 1,
            "username": "nh_test123",
            "password": "testpass",
            "payment_hash": "test_hash_123",
            "lightning_address": None,
            "ante_sats": 1000,
            "status": "pending",
            "created_at": "2024-01-15T12:00:00",
        })
        db.update_session_status = AsyncMock()
        db.add_to_pot = AsyncMock(return_value=11000)
        db.get_stats = AsyncMock(return_value={
            "total_games": 10,
            "total_ascensions": 1,
            "high_score": 50000,
            "avg_score": 5000.0,
        })
        db.get_recent_games = AsyncMock(return_value=[])
        db.get_leaderboard = AsyncMock(return_value=[])
        db.get_ascensions = AsyncMock(return_value=[])
        mock.return_value = db
        yield db


@pytest.fixture
def mock_settings():
    with patch("orange_nethack.api.routes.get_settings") as mock:
        settings = MagicMock()
        settings.ante_sats = 1000
        settings.max_active_sessions = 100
        settings.nethack_user_prefix = "nh_"
        mock.return_value = settings
        yield settings


@pytest.fixture
def client(mock_lightning, mock_db, mock_settings):
    # Patch init_db to prevent actual database initialization
    with patch("orange_nethack.api.main.init_db", new_callable=AsyncMock):
        from orange_nethack.api.main import app
        with TestClient(app) as test_client:
            yield test_client


class TestLandingPage:
    def test_landing_page(self, client, mock_db):
        response = client.get("/")
        assert response.status_code == 200
        assert "Orange Nethack" in response.text
        assert "10,000 sats" in response.text


class TestPlayEndpoint:
    def test_create_session(self, client, mock_db, mock_lightning):
        response = client.post("/api/play", json={})

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "payment_request" in data
        assert "payment_hash" in data
        assert data["amount_sats"] == 1000

    def test_create_session_with_address(self, client, mock_db, mock_lightning):
        response = client.post(
            "/api/play",
            json={"lightning_address": "user@getalby.com"}
        )

        assert response.status_code == 200
        mock_db.set_lightning_address.assert_called()

    def test_create_session_server_full(self, client, mock_db, mock_lightning, mock_settings):
        mock_db.count_active_sessions.return_value = 100

        response = client.post("/api/play", json={})

        assert response.status_code == 503
        assert "full" in response.json()["detail"].lower()


class TestSessionEndpoint:
    def test_get_session_pending(self, client, mock_db, mock_lightning):
        response = client.get("/api/session/1")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        # Should not return credentials for pending session
        assert data.get("username") is None
        assert data.get("password") is None

    def test_get_session_active(self, client, mock_db, mock_lightning):
        mock_db.get_session.return_value = {
            "id": 1,
            "username": "nh_test123",
            "password": "testpass",
            "payment_hash": "test_hash_123",
            "lightning_address": None,
            "ante_sats": 1000,
            "status": "active",
            "created_at": "2024-01-15T12:00:00",
        }

        response = client.get("/api/session/1")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["username"] == "nh_test123"
        assert data["password"] == "testpass"
        assert "ssh" in data["ssh_command"]

    def test_get_session_not_found(self, client, mock_db):
        mock_db.get_session.return_value = None

        response = client.get("/api/session/999")

        assert response.status_code == 404


class TestSetAddressEndpoint:
    def test_set_address(self, client, mock_db):
        response = client.post(
            "/api/play/1/address",
            json={"lightning_address": "new@address.com"}
        )

        assert response.status_code == 200
        mock_db.set_lightning_address.assert_called_with(1, "new@address.com")

    def test_set_address_session_not_found(self, client, mock_db):
        mock_db.get_session.return_value = None

        response = client.post(
            "/api/play/999/address",
            json={"lightning_address": "test@test.com"}
        )

        assert response.status_code == 404

    def test_set_address_session_ended(self, client, mock_db):
        mock_db.get_session.return_value = {
            "id": 1,
            "status": "ended",
        }

        response = client.post(
            "/api/play/1/address",
            json={"lightning_address": "test@test.com"}
        )

        assert response.status_code == 400


class TestPotEndpoint:
    def test_get_pot(self, client, mock_db, mock_settings):
        response = client.get("/api/pot")

        assert response.status_code == 200
        data = response.json()
        assert data["balance_sats"] == 10000
        assert data["ante_sats"] == 1000


class TestStatsEndpoint:
    def test_get_stats(self, client, mock_db):
        response = client.get("/api/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["pot_balance"] == 10000
        assert data["total_games"] == 10
        assert data["total_ascensions"] == 1


class TestHealthEndpoint:
    def test_health_check(self, client, mock_db):
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "pot_balance" in data
        assert "active_sessions" in data
