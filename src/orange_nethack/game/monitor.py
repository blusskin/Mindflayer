"""Game monitor service that watches for completed games and handles payouts."""
import asyncio
import logging
import signal
import sys

from orange_nethack.config import get_settings
from orange_nethack.database import get_db, init_db
from orange_nethack.email import get_email_service
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

        # entry.uid is the Linux UID, entry.name is the character name chosen in Nethack
        if entry.uid is None:
            logger.warning(f"Xlogfile entry has no UID: {entry.name}")
            return

        # Check for explore mode or wizard mode (cheat modes)
        is_cheated = entry.is_cheat_mode
        if is_cheated:
            mode = "wizard" if entry.is_wizard_mode else "explore"
            logger.warning(f"Cheat mode ({mode}) game detected for UID {entry.uid} (character: {entry.name})")
        else:
            logger.info(f"Game ended for UID {entry.uid} (character: {entry.name}): {entry.death} (score: {entry.score})")

        # Find the session by Linux UID
        session = await db.get_session_by_uid(entry.uid)
        if not session:
            logger.debug(f"No active session found for UID {entry.uid}")
            return

        username = session["username"]

        # Check session is in an active state (redundant given get_session_by_uid filters, but safe)
        if session["status"] not in ("active", "playing"):
            logger.warning(f"Session {session['id']} has unexpected status: {session['status']}")
            return

        # Handle ascension (only for legitimate games, not cheat modes)
        payout_sats = None
        payout_hash = None

        if entry.ascended and not is_cheated:
            logger.info(f"ASCENSION! UID {entry.uid} (character: {entry.name}) has ascended!")
            payout_result = await self.payout_service.handle_ascension(session)
            if payout_result:
                payout_sats = payout_result["amount"]
                payout_hash = payout_result.get("payment_hash")
                logger.info(f"Payout of {payout_sats} sats sent to {session['lightning_address']}")
            else:
                logger.error(f"Failed to send payout for ascension by UID {entry.uid}")
        elif entry.ascended and is_cheated:
            logger.warning(f"Cheat mode ascension by UID {entry.uid} - no payout!")

        # Record game in database (cheated games don't count as ascensions)
        death_reason = entry.death
        if is_cheated:
            mode = "wizard" if entry.is_wizard_mode else "explore"
            death_reason = f"[{mode.upper()} MODE] {entry.death}"

        await db.create_game(
            session_id=session["id"],
            character_name=entry.name,
            death_reason=death_reason,
            score=entry.score if not is_cheated else 0,  # No score for cheaters
            turns=entry.turns,
            ascended=entry.ascended and not is_cheated,  # Cheat ascensions don't count
            payout_sats=payout_sats,
            payout_hash=payout_hash,
            role=entry.role,
            race=entry.race,
            gender=entry.gender,
            align=entry.align,
            deathlev=entry.deathlev,
            hp=entry.hp,
            maxhp=entry.maxhp,
            conduct=entry.conduct,
            achieve=entry.achieve,
        )

        # Mark session as ended
        await db.update_session_status(session["id"], "ended")

        # Send game result email if email provided
        email = session.get("email")
        if email:
            try:
                pot_balance = await db.get_pot_balance()
                email_service = get_email_service()
                email_service.send_game_result(
                    email=email,
                    character_name=entry.name,  # Use actual character name from xlogfile
                    score=entry.score,
                    turns=entry.turns,
                    death_reason=entry.death,
                    ascended=entry.ascended,
                    ante_sats=session["ante_sats"],
                    pot_balance=pot_balance,
                    payout_sats=payout_sats,
                )
            except Exception as e:
                logger.error(f"Failed to send game result email: {e}")

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
