import logging
from dataclasses import dataclass
from fastapi import APIRouter, HTTPException, Request

from orange_nethack.config import get_settings
from orange_nethack.database import get_db
from orange_nethack.email import get_email_service
from orange_nethack.lightning.strike import get_lightning_client, StrikeClient
from orange_nethack.users.manager import UserManager

logger = logging.getLogger(__name__)

webhook_router = APIRouter()


@dataclass
class PaymentConfirmationResult:
    """Result of confirming a payment."""
    success: bool
    session_id: int | None = None
    username: str | None = None
    pot_balance: int | None = None
    error: str | None = None
    already_processed: bool = False


async def confirm_payment(
    payment_hash: str | None = None,
    session_id: int | None = None,
    skip_user_creation: bool = False,
    hostname: str = "localhost",
) -> PaymentConfirmationResult:
    """Confirm payment and activate a session.

    Can look up session by either payment_hash or session_id.
    This function is used by both the webhook and CLI simulate-payment.

    Args:
        payment_hash: The Strike invoice ID (stored as payment_hash in DB)
        session_id: The session ID (alternative to payment_hash)
        skip_user_creation: If True, skip Linux user creation (for mock mode)
        hostname: Server hostname for SSH command in email

    Returns:
        PaymentConfirmationResult with status information
    """
    db = get_db()
    settings = get_settings()

    # Find session
    if session_id:
        session = await db.get_session(session_id)
    elif payment_hash:
        session = await db.get_session_by_payment_hash(payment_hash)
    else:
        return PaymentConfirmationResult(
            success=False,
            error="Must provide either payment_hash or session_id",
        )

    if not session:
        return PaymentConfirmationResult(
            success=False,
            error="Session not found",
        )

    # Check if already processed
    if session["status"] != "pending":
        return PaymentConfirmationResult(
            success=True,
            session_id=session["id"],
            username=session["username"],
            already_processed=True,
        )

    logger.info(f"Payment confirmed for session {session['id']}, username: {session['username']}")

    # Add ante to pot
    new_pot_balance = await db.add_to_pot(session["ante_sats"])
    logger.info(f"Added {session['ante_sats']} sats to pot. New balance: {new_pot_balance}")

    # Create Linux user for SSH access (only skip if explicitly requested)
    if not skip_user_creation:
        try:
            user_manager = UserManager()
            linux_uid = await user_manager.create_user(
                session["username"], session["password"]
            )
            await db.set_linux_uid(session["id"], linux_uid)
            logger.info(f"Created Linux user: {session['username']} (UID: {linux_uid})")
        except Exception as e:
            logger.error(f"Failed to create Linux user {session['username']}: {e}")
            # Still mark as active - user creation might work on retry or manual intervention
    else:
        logger.info(f"[MOCK] Skipping Linux user creation for: {session['username']}")

    # Update session status
    await db.update_session_status(session["id"], "active")

    # Send payment confirmation email if email provided
    email = session.get("email")
    if email:
        try:
            email_service = get_email_service()
            email_service.send_payment_confirmed(
                email=email,
                username=session["username"],
                password=session["password"],
                hostname=hostname,
                ante_sats=session["ante_sats"],
                pot_balance=new_pot_balance,
            )
        except Exception as e:
            logger.error(f"Failed to send payment confirmation email: {e}")

    return PaymentConfirmationResult(
        success=True,
        session_id=session["id"],
        username=session["username"],
        pot_balance=new_pot_balance,
    )


@webhook_router.post("/payment")
async def handle_payment_webhook(request: Request):
    """Handle Strike payment webhook.

    Strike sends a POST request when an invoice is updated.
    The payload contains only the entity ID - we must fetch the invoice
    to check if it's been paid.

    Strike webhook payload format:
    {
        "eventType": "invoice.updated",
        "data": {
            "entityId": "invoice-uuid",
            "changes": ["state"]
        }
    }
    """
    # Parse webhook payload
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = payload.get("eventType")
    if event_type != "invoice.updated":
        logger.info(f"Ignoring webhook event type: {event_type}")
        return {"status": "ignored", "reason": f"event type {event_type}"}

    data = payload.get("data", {})
    invoice_id = data.get("entityId")

    if not invoice_id:
        logger.warning("Webhook received without entityId")
        raise HTTPException(status_code=400, detail="Missing entityId in webhook data")

    logger.info(f"Received Strike webhook for invoice: {invoice_id}")

    # Fetch invoice details from Strike to check payment status
    client = get_lightning_client()

    # Only StrikeClient has get_invoice method
    if isinstance(client, StrikeClient):
        invoice_data = await client.get_invoice(invoice_id)
        if not invoice_data:
            logger.warning(f"Invoice {invoice_id} not found in Strike")
            raise HTTPException(status_code=404, detail="Invoice not found")

        invoice_state = invoice_data.get("state")
        if invoice_state != "PAID":
            logger.info(f"Invoice {invoice_id} state is {invoice_state}, not PAID")
            return {"status": "pending", "state": invoice_state}
    else:
        # Mock client - check if payment is marked as paid
        is_paid = await client.check_payment(invoice_id)
        if not is_paid:
            return {"status": "pending"}

    # Use shared confirmation logic (invoice_id is stored as payment_hash)
    hostname = request.base_url.hostname or "localhost"
    result = await confirm_payment(payment_hash=invoice_id, hostname=hostname)

    if not result.success:
        if result.error == "Session not found":
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(status_code=400, detail=result.error)

    if result.already_processed:
        return {"status": "already_processed"}

    return {
        "status": "ok",
        "session_id": result.session_id,
        "username": result.username,
        "pot_balance": result.pot_balance,
    }
