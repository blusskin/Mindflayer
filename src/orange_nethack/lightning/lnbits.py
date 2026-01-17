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
    payment_hash: str
    payment_request: str
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


class LNbitsClient:
    """Real LNbits API client."""

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        admin_key: str | None = None,
    ):
        settings = get_settings()
        self.url = (url or settings.lnbits_url).rstrip("/")
        self.api_key = api_key or settings.lnbits_api_key
        self.admin_key = admin_key or settings.lnbits_admin_key

    def _headers(self, admin: bool = False) -> dict[str, str]:
        key = self.admin_key if admin else self.api_key
        return {"X-Api-Key": key, "Content-Type": "application/json"}

    async def create_invoice(
        self,
        amount_sats: int,
        memo: str = "Orange Nethack ante",
        webhook_url: str | None = None,
        expiry_seconds: int = 3600,
    ) -> Invoice:
        async with httpx.AsyncClient() as client:
            payload: dict[str, Any] = {
                "out": False,
                "amount": amount_sats,
                "memo": memo,
                "expiry": expiry_seconds,
            }
            if webhook_url:
                payload["webhook"] = webhook_url

            response = await client.post(
                f"{self.url}/api/v1/payments",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            return Invoice(
                payment_hash=data["payment_hash"],
                payment_request=data["payment_request"],
                amount_sats=amount_sats,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=expiry_seconds),
            )

    async def check_payment(self, payment_hash: str) -> bool:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.url}/api/v1/payments/{payment_hash}",
                headers=self._headers(),
            )
            if response.status_code == 404:
                return False
            response.raise_for_status()
            data = response.json()
            return data.get("paid", False)

    async def get_payment_details(self, payment_hash: str) -> dict | None:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.url}/api/v1/payments/{payment_hash}",
                headers=self._headers(),
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

    async def pay_invoice(self, bolt11: str) -> PaymentResult:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.url}/api/v1/payments",
                headers=self._headers(admin=True),
                json={"out": True, "bolt11": bolt11},
            )
            if response.status_code >= 400:
                error_detail = response.json().get("detail", "Payment failed")
                return PaymentResult(success=False, error=error_detail)

            data = response.json()
            return PaymentResult(
                success=True,
                payment_hash=data.get("payment_hash"),
            )

    async def pay_lnurl(self, lnurl_or_address: str, amount_sats: int) -> PaymentResult:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.url}/api/v1/payments/lnurl",
                headers=self._headers(admin=True),
                json={
                    "out": True,
                    "lnurl": lnurl_or_address,
                    "amount": amount_sats * 1000,  # Convert to millisats
                },
            )
            if response.status_code >= 400:
                try:
                    error_detail = response.json().get("detail", "LNURL payment failed")
                except Exception:
                    error_detail = response.text
                return PaymentResult(success=False, error=error_detail)

            data = response.json()
            return PaymentResult(
                success=True,
                payment_hash=data.get("payment_hash"),
            )

    async def get_balance(self) -> int:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.url}/api/v1/wallet",
                headers=self._headers(),
            )
            response.raise_for_status()
            data = response.json()
            # LNbits returns balance in millisats
            return data.get("balance", 0) // 1000


# Global client instance
_client: LightningClient | None = None


def get_lnbits_client() -> LightningClient:
    """Get the Lightning client (mock or real based on settings)."""
    global _client
    if _client is None:
        settings = get_settings()
        if settings.mock_lightning:
            _client = MockLightningClient()
        else:
            _client = LNbitsClient()
    return _client


def reset_client() -> None:
    """Reset the client (useful for testing)."""
    global _client
    _client = None
