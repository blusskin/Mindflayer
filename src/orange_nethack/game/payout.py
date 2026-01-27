"""Payout service for handling ascension rewards."""
import logging

from pydantic import ValidationError

from orange_nethack.database import get_db
from orange_nethack.lightning.strike import get_lightning_client
from orange_nethack.models import SetAddressRequest

logger = logging.getLogger(__name__)


class PayoutService:
    """Service for handling payouts to ascending players."""

    def __init__(self):
        self.lightning = get_lightning_client()

    async def handle_ascension(self, session: dict) -> dict | None:
        """Handle payout for an ascending player.

        Args:
            session: The session dict from the database

        Returns:
            Dict with payout details on success, None on failure
        """
        db = get_db()

        # Get the lightning address
        lightning_address = session.get("lightning_address")
        if not lightning_address:
            logger.error(f"No lightning address for session {session['id']}")
            return None

        # Validate Lightning address format BEFORE draining pot (V5 security fix)
        try:
            validated = SetAddressRequest(lightning_address=lightning_address)
            lightning_address = validated.lightning_address  # Use validated version
        except ValidationError as e:
            logger.error(f"Invalid lightning address for session {session['id']}: {e}")
            return None

        # Get and drain the pot (only after validation succeeds)
        pot_amount = await db.drain_pot()
        if pot_amount <= 0:
            logger.error("Pot is empty!")
            return None

        logger.info(f"Attempting payout of {pot_amount} sats to {lightning_address}")

        # Try to pay via LNURL/Lightning Address
        result = await self.lightning.pay_lnurl(lightning_address, pot_amount)

        if result.success:
            logger.info(f"Payout successful! Hash: {result.payment_hash}")
            return {
                "amount": pot_amount,
                "payment_hash": result.payment_hash,
                "lightning_address": lightning_address,
            }
        else:
            logger.error(f"Payout failed: {result.error}")
            # Restore the pot to original amount on failure
            await db.set_pot_balance(pot_amount)
            logger.info(f"Restored pot to {pot_amount} sats")
            return None

    async def check_balance(self) -> int:
        """Check the Lightning wallet balance."""
        return await self.lightning.get_balance()
