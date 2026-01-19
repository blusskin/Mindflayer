import httpx
import secrets
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from orange_nethack.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class Invoice:
    payment_hash: str  # Strike invoice ID (used as unique identifier)
    payment_request: str  # BOLT11 invoice string
    amount_sats: int
    expires_at: datetime | None = None


@dataclass
class PaymentResult:
    success: bool
    payment_hash: str | None = None
    error: str | None = None


class LightningClient(Protocol):
    """Protocol for Lightning payment clients."""

    async def create_invoice(
        self,
        amount_sats: int,
        memo: str = "Orange Nethack ante",
        webhook_url: str | None = None,
        expiry_seconds: int = 3600,
    ) -> Invoice: ...

    async def check_payment(self, payment_hash: str) -> bool: ...

    async def pay_lnurl(self, lnurl_or_address: str, amount_sats: int) -> PaymentResult: ...

    async def get_balance(self) -> int: ...


class MockLightningClient:
    """Mock Lightning client for testing without real payments.

    - Invoices are auto-paid immediately
    - Payouts always succeed
    - Balance is infinite
    """

    def __init__(self):
        self._pending_payments: dict[str, bool] = {}
        logger.info("Using MOCK Lightning client - no real payments!")

    async def create_invoice(
        self,
        amount_sats: int,
        memo: str = "Orange Nethack ante",
        webhook_url: str | None = None,
        expiry_seconds: int = 3600,
    ) -> Invoice:
        payment_hash = f"mock_{secrets.token_hex(16)}"
        # Generate a fake BOLT11 invoice
        payment_request = f"lnbc{amount_sats}mock1{secrets.token_hex(32)}"

        # Auto-mark as paid for testing
        self._pending_payments[payment_hash] = True

        logger.info(f"[MOCK] Created invoice: {amount_sats} sats, hash={payment_hash[:16]}...")

        return Invoice(
            payment_hash=payment_hash,
            payment_request=payment_request,
            amount_sats=amount_sats,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expiry_seconds),
        )

    async def check_payment(self, payment_hash: str) -> bool:
        # All mock payments are instantly "paid"
        is_paid = self._pending_payments.get(payment_hash, True)
        logger.info(f"[MOCK] Check payment {payment_hash[:16]}... = {is_paid}")
        return is_paid

    async def get_payment_details(self, payment_hash: str) -> dict | None:
        return {
            "payment_hash": payment_hash,
            "paid": True,
            "amount": 1000,
        }

    async def pay_invoice(self, bolt11: str) -> PaymentResult:
        payment_hash = f"mock_out_{secrets.token_hex(16)}"
        logger.info(f"[MOCK] Paid invoice: {bolt11[:30]}...")
        return PaymentResult(success=True, payment_hash=payment_hash)

    async def pay_lnurl(self, lnurl_or_address: str, amount_sats: int) -> PaymentResult:
        payment_hash = f"mock_lnurl_{secrets.token_hex(16)}"
        logger.info(f"[MOCK] Paid {amount_sats} sats to {lnurl_or_address}")
        return PaymentResult(success=True, payment_hash=payment_hash)

    async def get_balance(self) -> int:
        # Infinite balance in mock mode
        return 999999999


class StrikeClient:
    """Strike API client for Lightning payments.

    Strike API differences from LNbits:
    - Create invoice requires two calls: create invoice -> generate quote
    - Invoice amounts are in BTC (not sats)
    - Webhooks are global subscriptions, not per-invoice
    - Payment tracking uses invoice ID (UUID), not payment_hash
    """

    BASE_URL = "https://api.strike.me/v1"

    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.strike_api_key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def create_invoice(
        self,
        amount_sats: int,
        memo: str = "Orange Nethack ante",
        webhook_url: str | None = None,  # Not used - Strike uses global webhooks
        expiry_seconds: int = 3600,
    ) -> Invoice:
        """Create a Lightning invoice via Strike API.

        Strike requires two API calls:
        1. POST /v1/invoices - Create the invoice
        2. POST /v1/invoices/{id}/quote - Generate the BOLT11 quote

        Args:
            amount_sats: Amount in satoshis
            memo: Invoice description
            webhook_url: Ignored (Strike uses global webhook subscriptions)
            expiry_seconds: Invoice expiry time

        Returns:
            Invoice with payment_hash set to Strike's invoice ID
        """
        # Convert sats to BTC (Strike uses BTC amounts)
        amount_btc = amount_sats / 100_000_000

        async with httpx.AsyncClient() as client:
            # Step 1: Create the invoice
            invoice_payload: dict[str, Any] = {
                "correlationId": secrets.token_hex(16),  # Our tracking ID
                "description": memo,
                "amount": {
                    "amount": f"{amount_btc:.8f}",
                    "currency": "BTC",
                },
            }

            response = await client.post(
                f"{self.BASE_URL}/invoices",
                headers=self._headers(),
                json=invoice_payload,
            )
            response.raise_for_status()
            invoice_data = response.json()

            invoice_id = invoice_data["invoiceId"]
            logger.info(f"Created Strike invoice: {invoice_id}")

            # Step 2: Generate the BOLT11 quote
            quote_response = await client.post(
                f"{self.BASE_URL}/invoices/{invoice_id}/quote",
                headers=self._headers(),
            )
            quote_response.raise_for_status()
            quote_data = quote_response.json()

            bolt11 = quote_data["lnInvoice"]
            expires_at_str = quote_data.get("expirationInSec")

            # Calculate expiry
            if expires_at_str:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_at_str))
            else:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expiry_seconds)

            return Invoice(
                payment_hash=invoice_id,  # Use invoice ID as our tracking key
                payment_request=bolt11,
                amount_sats=amount_sats,
                expires_at=expires_at,
            )

    async def check_payment(self, payment_hash: str) -> bool:
        """Check if an invoice has been paid.

        Args:
            payment_hash: The Strike invoice ID

        Returns:
            True if the invoice state is PAID
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/invoices/{payment_hash}",
                headers=self._headers(),
            )
            if response.status_code == 404:
                return False
            response.raise_for_status()
            data = response.json()
            return data.get("state") == "PAID"

    async def get_invoice(self, invoice_id: str) -> dict | None:
        """Get full invoice details from Strike.

        Args:
            invoice_id: The Strike invoice ID

        Returns:
            Invoice data dict or None if not found
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/invoices/{invoice_id}",
                headers=self._headers(),
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

    async def pay_lnurl(self, lnurl_or_address: str, amount_sats: int) -> PaymentResult:
        """Pay to an LNURL or Lightning Address.

        Strike requires two API calls:
        1. POST /v1/payment-quotes/lightning/lnurl - Create quote
        2. PATCH /v1/payment-quotes/{id}/execute - Execute payment

        Args:
            lnurl_or_address: Lightning Address (user@domain.com) or LNURL
            amount_sats: Amount in satoshis

        Returns:
            PaymentResult with success status
        """
        # Convert sats to BTC
        amount_btc = amount_sats / 100_000_000

        async with httpx.AsyncClient() as client:
            # Step 1: Create payment quote
            quote_payload = {
                "lnUrlOrAddress": lnurl_or_address,
                "sourceCurrency": "BTC",
                "amount": {
                    "amount": f"{amount_btc:.8f}",
                    "currency": "BTC",
                },
            }

            response = await client.post(
                f"{self.BASE_URL}/payment-quotes/lightning/lnurl",
                headers=self._headers(),
                json=quote_payload,
            )

            if response.status_code >= 400:
                try:
                    error_detail = response.json().get("message", "Failed to create payment quote")
                except Exception:
                    error_detail = response.text
                logger.error(f"Strike payment quote failed: {error_detail}")
                return PaymentResult(success=False, error=error_detail)

            quote_data = response.json()
            quote_id = quote_data["paymentQuoteId"]
            logger.info(f"Created Strike payment quote: {quote_id}")

            # Step 2: Execute the payment
            exec_response = await client.patch(
                f"{self.BASE_URL}/payment-quotes/{quote_id}/execute",
                headers=self._headers(),
            )

            if exec_response.status_code >= 400:
                try:
                    error_detail = exec_response.json().get("message", "Payment execution failed")
                except Exception:
                    error_detail = exec_response.text
                logger.error(f"Strike payment execution failed: {error_detail}")
                return PaymentResult(success=False, error=error_detail)

            exec_data = exec_response.json()
            payment_id = exec_data.get("paymentId", quote_id)

            logger.info(f"Strike payment executed: {payment_id}")
            return PaymentResult(success=True, payment_hash=payment_id)

    async def get_balance(self) -> int:
        """Get available balance in satoshis.

        Returns:
            Balance in satoshis (BTC balance converted)
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/balances",
                headers=self._headers(),
            )
            response.raise_for_status()
            balances = response.json()

            # Find BTC balance
            for balance in balances:
                if balance.get("currency") == "BTC":
                    btc_amount = float(balance.get("available", 0))
                    # Convert BTC to sats
                    return int(btc_amount * 100_000_000)

            return 0

    async def subscribe_to_webhooks(self, webhook_url: str) -> str:
        """Subscribe to Strike webhook events.

        Strike uses global webhook subscriptions rather than per-invoice URLs.
        This should be called once during setup.

        Args:
            webhook_url: The URL to receive webhook notifications

        Returns:
            Subscription ID
        """
        async with httpx.AsyncClient() as client:
            payload = {
                "webhookUrl": webhook_url,
                "webhookVersion": "v1",
                "secret": secrets.token_hex(24),  # Max 50 chars, hex gives 48
                "enabled": True,
                "eventTypes": ["invoice.updated"],
            }

            response = await client.post(
                f"{self.BASE_URL}/subscriptions",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            subscription_id = data["id"]
            logger.info(f"Created Strike webhook subscription: {subscription_id}")
            return subscription_id


# Global client instance
_client: LightningClient | None = None


def get_lightning_client() -> LightningClient:
    """Get the Lightning client (mock or real based on settings)."""
    global _client
    if _client is None:
        settings = get_settings()
        if settings.mock_lightning:
            _client = MockLightningClient()
        else:
            _client = StrikeClient()
    return _client


def reset_client() -> None:
    """Reset the client (useful for testing)."""
    global _client
    _client = None
