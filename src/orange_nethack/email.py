"""Email service for sending notifications to players."""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from orange_nethack.config import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending email notifications."""

    def __init__(self):
        self.settings = get_settings()

    def _get_smtp_connection(self) -> smtplib.SMTP:
        """Create and return an SMTP connection."""
        if self.settings.smtp_use_tls:
            smtp = smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port)
            smtp.starttls()
        else:
            smtp = smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port)

        if self.settings.smtp_user and self.settings.smtp_password:
            smtp.login(self.settings.smtp_user, self.settings.smtp_password)

        return smtp

    def _send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Send an email. Returns True on success, False on failure."""
        if not self.settings.smtp_configured:
            logger.debug("SMTP not configured, skipping email")
            return False

        try:
            msg = MIMEMultipart()
            msg["From"] = self.settings.smtp_from_email
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with self._get_smtp_connection() as smtp:
                smtp.sendmail(self.settings.smtp_from_email, to_email, msg.as_string())

            logger.info(f"Email sent to {to_email}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    def send_payment_confirmed(
        self,
        email: str,
        username: str,
        password: str,
        hostname: str,
        ante_sats: int,
        pot_balance: int,
        session_id: int | None = None,
        access_token: str | None = None,
    ) -> bool:
        """Send payment confirmation email with SSH credentials."""
        subject = "Orange Nethack - Payment Confirmed!"

        # Build play in browser link if we have session_id and access_token
        play_link = ""
        if session_id and access_token:
            play_link = f"""
Play in Browser:
  https://{hostname}/play/{session_id}?token={access_token}
"""

        body = f"""Your ante of {ante_sats:,} sats has been received.
{play_link}
Your session is active. Use the link above to play in your browser,
or access your SSH credentials via the web interface.

The current pot is {pot_balance:,} sats. Ascend to win it all!

---
Orange Nethack - Stack sats. Ascend. Win the pot.
"""
        return self._send_email(email, subject, body)

    def send_game_result(
        self,
        email: str,
        character_name: str | None,
        score: int,
        turns: int,
        death_reason: str,
        ascended: bool,
        ante_sats: int,
        pot_balance: int,
        payout_sats: int | None = None,
    ) -> bool:
        """Send game result notification email."""
        if ascended:
            subject = "Orange Nethack - ASCENSION!"
        else:
            subject = "Orange Nethack - Game Over"

        char_display = character_name or "Unknown"

        if ascended:
            if payout_sats:
                result_text = f"""
CONGRATULATIONS! You ascended and won {payout_sats:,} sats!

Your mastery of the dungeon has been rewarded. The payout has been sent
to your Lightning address.
"""
            else:
                result_text = """
CONGRATULATIONS! You ascended!

However, there was an issue processing your payout. Please contact the
administrator with your session details.
"""
        else:
            result_text = f"""
Your {ante_sats:,} sats ante has been added to the pot.
Current pot: {pot_balance:,} sats

Better luck next time, adventurer!
"""

        body = f"""Game Over

Character: {char_display}
Score: {score:,}
Turns: {turns:,}
Death: {death_reason}
{result_text}
---
Orange Nethack - Stack sats. Ascend. Win the pot.
"""
        return self._send_email(email, subject, body)


# Global email service instance
_email_service: EmailService | None = None


def get_email_service() -> EmailService:
    """Get the global email service instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
