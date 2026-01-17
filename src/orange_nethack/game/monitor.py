"""Game monitor service that watches for completed games and handles payouts."""
import asyncio
import logging
import signal
import sys

from orange_nethack.config import get_settings
from orange_nethack.database import get_db, init_db
from orange_nethack.game.payout import PayoutService
from orange_nethack.game.xlogfile import XlogfileWatcher
from orange_nethack.models import XlogEntry
from orange_nethack.users.manager import UserManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class GameMonitor:
    """Monitor nethack games and handle game completion events."""

    def __init__(self):
        self.settings = get_settings()
        self.watcher = XlogfileWatcher(self.settings.xlogfile_path)
        self.user_manager = UserManager()
        self.payout_service = PayoutService()
        self.running = False
        self.poll_interval = 2.0  # seconds

    async def start(self) -> None:
        """Start the game monitor."""
        await init_db()
        self.running = True
        logger.info(f"Game monitor started, watching {self.settings.xlogfile_path}")

        while self.running:
            try:
                await self._check_for_new_games()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in game monitor loop: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval)

    async def stop(self) -> None:
        """Stop the game monitor."""
        self.running = False
        logger.info("Game monitor stopped")

    async def _check_for_new_games(self) -> None:
        """Check xlogfile for new game completions."""
        entries = self.watcher.get_new_entries()

        for entry in entries:
            await self._handle_game_end(entry)

    async def _handle_game_end(self, entry: XlogEntry) -> None:
        """Handle a completed game."""
        db = get_db()
        username = entry.name

        logger.info(f"Game ended for {username}: {entry.death} (score: {entry.score})")

        # Check if this is one of our managed users
        if not username.startswith(self.settings.nethack_user_prefix):
            logger.debug(f"Ignoring game for non-managed user: {username}")
            return

        # Find the session for this user
        session = await db.get_session_by_username(username)
        if not session:
            logger.warning(f"No session found for user: {username}")
            return

        # Check session is in an active state
        if session["status"] not in ("active", "playing"):
            logger.warning(f"Session {session['id']} has unexpected status: {session['status']}")
            return

        # Handle ascension!
        payout_sats = None
        payout_hash = None

        if entry.ascended:
            logger.info(f"ASCENSION! User {username} has ascended!")
            payout_result = await self.payout_service.handle_ascension(session)
            if payout_result:
                payout_sats = payout_result["amount"]
                payout_hash = payout_result.get("payment_hash")
                logger.info(f"Payout of {payout_sats} sats sent to {session['lightning_address']}")
            else:
                logger.error(f"Failed to send payout for ascension by {username}")

        # Record game in database
        await db.create_game(
            session_id=session["id"],
            death_reason=entry.death,
            score=entry.score,
            turns=entry.turns,
            ascended=entry.ascended,
            payout_sats=payout_sats,
            payout_hash=payout_hash,
        )

        # Mark session as ended
        await db.update_session_status(session["id"], "ended")

        # Clean up Linux user
        try:
            await self.user_manager.delete_user(username)
            logger.info(f"Cleaned up user: {username}")
        except Exception as e:
            logger.error(f"Failed to clean up user {username}: {e}")


async def main():
    """Main entry point for the game monitor service."""
    monitor = GameMonitor()

    # Handle shutdown signals
    loop = asyncio.get_running_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(monitor.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await monitor.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await monitor.stop()


def run():
    """Entry point for the console script."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
