"""Tests for database operations."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from orange_nethack.database import Database


@pytest.fixture
async def db():
    """Create a test database."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        db_path = Path(f.name)

    with patch("orange_nethack.database.get_settings") as mock_settings:
        mock_settings.return_value.database_path = db_path
        mock_settings.return_value.pot_initial = 10000

        database = Database(db_path)
        await database.init()
        yield database

    if db_path.exists():
        db_path.unlink()


class TestPotOperations:
    @pytest.mark.asyncio
    async def test_initial_pot_balance(self, db):
        balance = await db.get_pot_balance()
        assert balance == 10000

    @pytest.mark.asyncio
    async def test_add_to_pot(self, db):
        new_balance = await db.add_to_pot(1000)
        assert new_balance == 11000

        balance = await db.get_pot_balance()
        assert balance == 11000

    @pytest.mark.asyncio
    async def test_drain_pot(self, db):
        await db.add_to_pot(5000)

        drained = await db.drain_pot()
        assert drained == 15000

        # Should be back to initial
        balance = await db.get_pot_balance()
        assert balance == 10000


class TestSessionOperations:
    @pytest.mark.asyncio
    async def test_create_session(self, db):
        session_id = await db.create_session(
            username="nh_test123",
            password="password123",
            payment_hash="abc123",
            ante_sats=1000,
        )

        assert session_id is not None
        assert session_id > 0

    @pytest.mark.asyncio
    async def test_get_session(self, db):
        session_id = await db.create_session(
            username="nh_test456",
            password="password456",
            payment_hash="def456",
            ante_sats=1000,
        )

        session = await db.get_session(session_id)

        assert session is not None
        assert session["username"] == "nh_test456"
        assert session["password"] == "password456"
        assert session["payment_hash"] == "def456"
        assert session["status"] == "pending"

    @pytest.mark.asyncio
    async def test_get_session_by_payment_hash(self, db):
        await db.create_session(
            username="nh_test789",
            password="password789",
            payment_hash="ghi789",
            ante_sats=1000,
        )

        session = await db.get_session_by_payment_hash("ghi789")

        assert session is not None
        assert session["username"] == "nh_test789"

    @pytest.mark.asyncio
    async def test_get_session_by_username(self, db):
        await db.create_session(
            username="nh_unique",
            password="password",
            payment_hash="unique_hash",
            ante_sats=1000,
        )

        session = await db.get_session_by_username("nh_unique")

        assert session is not None
        assert session["payment_hash"] == "unique_hash"

    @pytest.mark.asyncio
    async def test_update_session_status(self, db):
        session_id = await db.create_session(
            username="nh_status",
            password="password",
            payment_hash="status_hash",
            ante_sats=1000,
        )

        await db.update_session_status(session_id, "active")

        session = await db.get_session(session_id)
        assert session["status"] == "active"

    @pytest.mark.asyncio
    async def test_set_lightning_address(self, db):
        session_id = await db.create_session(
            username="nh_addr",
            password="password",
            payment_hash="addr_hash",
            ante_sats=1000,
        )

        await db.set_lightning_address(session_id, "user@getalby.com")

        session = await db.get_session(session_id)
        assert session["lightning_address"] == "user@getalby.com"

    @pytest.mark.asyncio
    async def test_get_active_sessions(self, db):
        # Create some sessions with different statuses
        s1 = await db.create_session(
            username="nh_pending",
            password="p",
            payment_hash="h1",
            ante_sats=1000,
        )
        s2 = await db.create_session(
            username="nh_active",
            password="p",
            payment_hash="h2",
            ante_sats=1000,
        )
        s3 = await db.create_session(
            username="nh_playing",
            password="p",
            payment_hash="h3",
            ante_sats=1000,
        )

        await db.update_session_status(s2, "active")
        await db.update_session_status(s3, "playing")

        active = await db.get_active_sessions()

        assert len(active) == 2
        usernames = [s["username"] for s in active]
        assert "nh_active" in usernames
        assert "nh_playing" in usernames
        assert "nh_pending" not in usernames

    @pytest.mark.asyncio
    async def test_count_active_sessions(self, db):
        s1 = await db.create_session(
            username="nh_c1",
            password="p",
            payment_hash="ch1",
            ante_sats=1000,
        )
        s2 = await db.create_session(
            username="nh_c2",
            password="p",
            payment_hash="ch2",
            ante_sats=1000,
        )

        await db.update_session_status(s1, "active")
        await db.update_session_status(s2, "playing")

        count = await db.count_active_sessions()
        assert count == 2


class TestGameOperations:
    @pytest.mark.asyncio
    async def test_create_game(self, db):
        session_id = await db.create_session(
            username="nh_game",
            password="p",
            payment_hash="game_hash",
            ante_sats=1000,
        )

        game_id = await db.create_game(
            session_id=session_id,
            death_reason="killed by a jackal",
            score=1234,
            turns=500,
            ascended=False,
        )

        assert game_id is not None
        assert game_id > 0

    @pytest.mark.asyncio
    async def test_get_recent_games(self, db):
        session_id = await db.create_session(
            username="nh_recent",
            password="p",
            payment_hash="recent_hash",
            ante_sats=1000,
        )

        await db.create_game(
            session_id=session_id,
            death_reason="died",
            score=100,
            turns=50,
            ascended=False,
        )

        games = await db.get_recent_games(limit=10)

        assert len(games) == 1
        assert games[0]["score"] == 100
        assert games[0]["username"] == "nh_recent"

    @pytest.mark.asyncio
    async def test_get_leaderboard(self, db):
        session_id = await db.create_session(
            username="nh_leader",
            password="p",
            payment_hash="leader_hash",
            ante_sats=1000,
        )

        await db.create_game(
            session_id=session_id,
            death_reason="died",
            score=5000,
            turns=1000,
            ascended=False,
        )

        leaderboard = await db.get_leaderboard(limit=10)

        assert len(leaderboard) == 1
        assert leaderboard[0]["score"] == 5000

    @pytest.mark.asyncio
    async def test_get_ascensions(self, db):
        session_id = await db.create_session(
            username="nh_winner",
            password="p",
            payment_hash="winner_hash",
            ante_sats=1000,
        )

        await db.create_game(
            session_id=session_id,
            death_reason="ascended",
            score=999999,
            turns=50000,
            ascended=True,
            payout_sats=15000,
        )

        ascensions = await db.get_ascensions()

        assert len(ascensions) == 1
        assert bool(ascensions[0]["ascended"]) is True
        assert ascensions[0]["payout_sats"] == 15000

    @pytest.mark.asyncio
    async def test_get_stats(self, db):
        session_id = await db.create_session(
            username="nh_stats",
            password="p",
            payment_hash="stats_hash",
            ante_sats=1000,
        )

        await db.create_game(
            session_id=session_id,
            death_reason="died",
            score=1000,
            turns=100,
            ascended=False,
        )

        stats = await db.get_stats()

        assert stats["total_games"] == 1
        assert stats["total_ascensions"] == 0
        assert stats["high_score"] == 1000
