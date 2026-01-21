import aiosqlite
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from orange_nethack.config import get_settings

SCHEMA = """
-- Pot tracking (single row)
CREATE TABLE IF NOT EXISTS pot (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    balance_sats INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Player sessions
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    lightning_address TEXT,
    email TEXT,
    linux_uid INTEGER,
    payment_hash TEXT UNIQUE NOT NULL,
    ante_sats INTEGER NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'playing', 'ended')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP
);

-- Game results
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY,
    session_id INTEGER REFERENCES sessions(id),
    death_reason TEXT,
    score INTEGER,
    turns INTEGER,
    ascended BOOLEAN DEFAULT FALSE,
    payout_sats INTEGER,
    payout_hash TEXT,
    ended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_username ON sessions(username);
CREATE INDEX IF NOT EXISTS idx_sessions_payment_hash ON sessions(payment_hash);
CREATE INDEX IF NOT EXISTS idx_games_session_id ON games(session_id);
CREATE INDEX IF NOT EXISTS idx_games_ascended ON games(ascended);
"""


class Database:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or get_settings().database_path

    async def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with self.connection() as db:
            await db.executescript(SCHEMA)
            # Initialize pot if not exists
            await db.execute(
                "INSERT OR IGNORE INTO pot (id, balance_sats) VALUES (1, ?)",
                (get_settings().pot_initial,),
            )
            # Migration: add email and character_name columns if they don't exist
            await self._migrate_sessions_table(db)
            await db.commit()

    async def _migrate_sessions_table(self, db: aiosqlite.Connection) -> None:
        """Add email and linux_uid columns if they don't exist."""
        cursor = await db.execute("PRAGMA table_info(sessions)")
        columns = {row[1] for row in await cursor.fetchall()}

        if "email" not in columns:
            await db.execute("ALTER TABLE sessions ADD COLUMN email TEXT")

        if "linux_uid" not in columns:
            await db.execute("ALTER TABLE sessions ADD COLUMN linux_uid INTEGER")

        # Create index on linux_uid (after column exists)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_linux_uid ON sessions(linux_uid)"
        )

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            yield db

    # Pot operations
    async def get_pot_balance(self) -> int:
        async with self.connection() as db:
            cursor = await db.execute("SELECT balance_sats FROM pot WHERE id = 1")
            row = await cursor.fetchone()
            return row["balance_sats"] if row else 0

    async def add_to_pot(self, amount_sats: int) -> int:
        async with self.connection() as db:
            await db.execute(
                "UPDATE pot SET balance_sats = balance_sats + ?, updated_at = ? WHERE id = 1",
                (amount_sats, datetime.now(timezone.utc)),
            )
            await db.commit()
            return await self.get_pot_balance()

    async def drain_pot(self) -> int:
        async with self.connection() as db:
            balance = await self.get_pot_balance()
            await db.execute(
                "UPDATE pot SET balance_sats = ?, updated_at = ? WHERE id = 1",
                (get_settings().pot_initial, datetime.now(timezone.utc)),
            )
            await db.commit()
            return balance

    # Session operations
    async def create_session(
        self,
        username: str,
        password: str,
        payment_hash: str,
        ante_sats: int,
        email: str | None = None,
    ) -> int:
        async with self.connection() as db:
            cursor = await db.execute(
                """
                INSERT INTO sessions (username, password, payment_hash, ante_sats, email, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
                """,
                (username, password, payment_hash, ante_sats, email),
            )
            await db.commit()
            return cursor.lastrowid

    async def get_session(self, session_id: int) -> dict | None:
        async with self.connection() as db:
            cursor = await db.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_session_by_payment_hash(self, payment_hash: str) -> dict | None:
        async with self.connection() as db:
            cursor = await db.execute(
                "SELECT * FROM sessions WHERE payment_hash = ?", (payment_hash,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_session_by_username(self, username: str) -> dict | None:
        async with self.connection() as db:
            cursor = await db.execute(
                "SELECT * FROM sessions WHERE username = ?", (username,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_session_by_uid(self, linux_uid: int) -> dict | None:
        async with self.connection() as db:
            cursor = await db.execute(
                "SELECT * FROM sessions WHERE linux_uid = ? AND status IN ('active', 'playing')",
                (linux_uid,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def set_linux_uid(self, session_id: int, linux_uid: int) -> None:
        async with self.connection() as db:
            await db.execute(
                "UPDATE sessions SET linux_uid = ? WHERE id = ?",
                (linux_uid, session_id),
            )
            await db.commit()

    async def get_active_sessions(self) -> list[dict]:
        async with self.connection() as db:
            cursor = await db.execute(
                "SELECT * FROM sessions WHERE status IN ('active', 'playing')"
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def update_session_status(self, session_id: int, status: str) -> None:
        async with self.connection() as db:
            if status == "ended":
                await db.execute(
                    "UPDATE sessions SET status = ?, ended_at = ? WHERE id = ?",
                    (status, datetime.now(timezone.utc), session_id),
                )
            else:
                await db.execute(
                    "UPDATE sessions SET status = ? WHERE id = ?",
                    (status, session_id),
                )
            await db.commit()

    async def set_lightning_address(self, session_id: int, address: str) -> None:
        async with self.connection() as db:
            await db.execute(
                "UPDATE sessions SET lightning_address = ? WHERE id = ?",
                (address, session_id),
            )
            await db.commit()

    async def count_active_sessions(self) -> int:
        async with self.connection() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) as count FROM sessions WHERE status IN ('active', 'playing')"
            )
            row = await cursor.fetchone()
            return row["count"]

    # Game operations
    async def create_game(
        self,
        session_id: int,
        death_reason: str,
        score: int,
        turns: int,
        ascended: bool,
        payout_sats: int | None = None,
        payout_hash: str | None = None,
    ) -> int:
        async with self.connection() as db:
            cursor = await db.execute(
                """
                INSERT INTO games
                (session_id, death_reason, score, turns, ascended, payout_sats, payout_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, death_reason, score, turns, ascended, payout_sats, payout_hash),
            )
            await db.commit()
            return cursor.lastrowid

    async def get_recent_games(self, limit: int = 10) -> list[dict]:
        async with self.connection() as db:
            cursor = await db.execute(
                """
                SELECT g.*, s.username
                FROM games g
                JOIN sessions s ON g.session_id = s.id
                ORDER BY g.ended_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_leaderboard(self, limit: int = 10) -> list[dict]:
        async with self.connection() as db:
            cursor = await db.execute(
                """
                SELECT g.*, s.username
                FROM games g
                JOIN sessions s ON g.session_id = s.id
                ORDER BY g.score DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_ascensions(self) -> list[dict]:
        async with self.connection() as db:
            cursor = await db.execute(
                """
                SELECT g.*, s.username
                FROM games g
                JOIN sessions s ON g.session_id = s.id
                WHERE g.ascended = TRUE
                ORDER BY g.ended_at DESC
                """
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_stats(self) -> dict:
        async with self.connection() as db:
            cursor = await db.execute(
                """
                SELECT
                    COUNT(*) as total_games,
                    SUM(CASE WHEN ascended THEN 1 ELSE 0 END) as total_ascensions,
                    SUM(score) as total_score,
                    MAX(score) as high_score,
                    AVG(score) as avg_score,
                    SUM(turns) as total_turns
                FROM games
                """
            )
            row = await cursor.fetchone()
            return dict(row) if row else {}


# Global database instance
_db: Database | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


async def init_db() -> None:
    await get_db().init()
