"""Tests for LNbits client."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from orange_nethack.lightning.lnbits import LNbitsClient, Invoice, PaymentResult


@pytest.fixture
def lnbits_client():
    return LNbitsClient(
        url="https://test.lnbits.com",
        api_key="test_api_key",
        admin_key="test_admin_key",
    )


class TestLNbitsClient:
    @pytest.mark.asyncio
    async def test_create_invoice(self, lnbits_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "payment_hash": "abc123",
            "payment_request": "lnbc1000...",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.post.return_value = mock_response

            invoice = await lnbits_client.create_invoice(
                amount_sats=1000,
                memo="Test invoice",
            )

            assert invoice.payment_hash == "abc123"
            assert invoice.payment_request == "lnbc1000..."
            assert invoice.amount_sats == 1000
            assert invoice.expires_at is not None

            mock_client_instance.post.assert_called_once()
            call_args = mock_client_instance.post.call_args
            assert call_args[0][0] == "https://test.lnbits.com/api/v1/payments"
            assert call_args[1]["json"]["amount"] == 1000
            assert call_args[1]["json"]["memo"] == "Test invoice"

    @pytest.mark.asyncio
    async def test_check_payment_paid(self, lnbits_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"paid": True}
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.return_value = mock_response

            is_paid = await lnbits_client.check_payment("abc123")

            assert is_paid is True

    @pytest.mark.asyncio
    async def test_check_payment_not_found(self, lnbits_client):
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.return_value = mock_response

            is_paid = await lnbits_client.check_payment("nonexistent")

            assert is_paid is False

    @pytest.mark.asyncio
    async def test_pay_invoice_success(self, lnbits_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"payment_hash": "payout123"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.post.return_value = mock_response

            result = await lnbits_client.pay_invoice("lnbc1000...")

            assert result.success is True
            assert result.payment_hash == "payout123"

    @pytest.mark.asyncio
    async def test_pay_invoice_failure(self, lnbits_client):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"detail": "Insufficient balance"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.post.return_value = mock_response

            result = await lnbits_client.pay_invoice("lnbc1000...")

            assert result.success is False
            assert result.error == "Insufficient balance"

    @pytest.mark.asyncio
    async def test_pay_lnurl_success(self, lnbits_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"payment_hash": "lnurl_payout123"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.post.return_value = mock_response

            result = await lnbits_client.pay_lnurl("user@getalby.com", 5000)

            assert result.success is True
            assert result.payment_hash == "lnurl_payout123"

            call_args = mock_client_instance.post.call_args
            assert call_args[1]["json"]["amount"] == 5000000  # millisats

    @pytest.mark.asyncio
    async def test_get_balance(self, lnbits_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"balance": 10000000}  # millisats
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.return_value = mock_response

            balance = await lnbits_client.get_balance()

            assert balance == 10000  # sats

    def test_headers_invoice_key(self, lnbits_client):
        headers = lnbits_client._headers(admin=False)
        assert headers["X-Api-Key"] == "test_api_key"

    def test_headers_admin_key(self, lnbits_client):
        headers = lnbits_client._headers(admin=True)
        assert headers["X-Api-Key"] == "test_admin_key"
