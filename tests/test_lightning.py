"""Tests for Strike Lightning client."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from orange_nethack.lightning.strike import StrikeClient, Invoice, PaymentResult


@pytest.fixture
def strike_client():
    return StrikeClient(api_key="test_api_key")


class TestStrikeClient:
    @pytest.mark.asyncio
    async def test_create_invoice(self, strike_client):
        # Mock invoice creation response
        mock_invoice_response = MagicMock()
        mock_invoice_response.json.return_value = {
            "invoiceId": "abc123-uuid",
            "correlationId": "test-correlation",
            "description": "Test invoice",
            "state": "UNPAID",
        }
        mock_invoice_response.raise_for_status = MagicMock()

        # Mock quote response
        mock_quote_response = MagicMock()
        mock_quote_response.json.return_value = {
            "lnInvoice": "lnbc1000...",
            "expirationInSec": 3600,
        }
        mock_quote_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            # First call creates invoice, second call gets quote
            mock_client_instance.post.side_effect = [mock_invoice_response, mock_quote_response]

            invoice = await strike_client.create_invoice(
                amount_sats=1000,
                memo="Test invoice",
            )

            assert invoice.payment_hash == "abc123-uuid"
            assert invoice.payment_request == "lnbc1000..."
            assert invoice.amount_sats == 1000
            assert invoice.expires_at is not None

            # Verify both API calls were made
            assert mock_client_instance.post.call_count == 2

            # Check first call (create invoice)
            first_call = mock_client_instance.post.call_args_list[0]
            assert first_call[0][0] == "https://api.strike.me/v1/invoices"
            # Amount should be in BTC (1000 sats = 0.00001 BTC)
            assert first_call[1]["json"]["amount"]["amount"] == "0.00001000"
            assert first_call[1]["json"]["amount"]["currency"] == "BTC"

            # Check second call (generate quote)
            second_call = mock_client_instance.post.call_args_list[1]
            assert second_call[0][0] == "https://api.strike.me/v1/invoices/abc123-uuid/quote"

    @pytest.mark.asyncio
    async def test_check_payment_paid(self, strike_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"state": "PAID"}
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.return_value = mock_response

            is_paid = await strike_client.check_payment("abc123-uuid")

            assert is_paid is True

    @pytest.mark.asyncio
    async def test_check_payment_unpaid(self, strike_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"state": "UNPAID"}
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.return_value = mock_response

            is_paid = await strike_client.check_payment("abc123-uuid")

            assert is_paid is False

    @pytest.mark.asyncio
    async def test_check_payment_not_found(self, strike_client):
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.return_value = mock_response

            is_paid = await strike_client.check_payment("nonexistent")

            assert is_paid is False

    @pytest.mark.asyncio
    async def test_pay_lnurl_success(self, strike_client):
        # Mock quote creation response
        mock_quote_response = MagicMock()
        mock_quote_response.status_code = 200
        mock_quote_response.json.return_value = {
            "paymentQuoteId": "quote123",
        }

        # Mock execution response
        mock_exec_response = MagicMock()
        mock_exec_response.status_code = 200
        mock_exec_response.json.return_value = {
            "paymentId": "payment123",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.post.return_value = mock_quote_response
            mock_client_instance.patch.return_value = mock_exec_response

            result = await strike_client.pay_lnurl("user@getalby.com", 5000)

            assert result.success is True
            assert result.payment_hash == "payment123"

            # Verify quote creation call
            quote_call = mock_client_instance.post.call_args
            assert quote_call[0][0] == "https://api.strike.me/v1/payment-quotes/lightning/lnurl"
            # Amount should be in BTC (5000 sats = 0.00005 BTC)
            assert quote_call[1]["json"]["amount"]["amount"] == "0.00005000"

            # Verify execution call
            exec_call = mock_client_instance.patch.call_args
            assert exec_call[0][0] == "https://api.strike.me/v1/payment-quotes/quote123/execute"

    @pytest.mark.asyncio
    async def test_pay_lnurl_quote_failure(self, strike_client):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"message": "Invalid LNURL"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.post.return_value = mock_response

            result = await strike_client.pay_lnurl("invalid@address.com", 5000)

            assert result.success is False
            assert result.error == "Invalid LNURL"

    @pytest.mark.asyncio
    async def test_get_balance(self, strike_client):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"currency": "USD", "available": "100.00"},
            {"currency": "BTC", "available": "0.0001"},  # 10000 sats
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.return_value = mock_response

            balance = await strike_client.get_balance()

            assert balance == 10000  # 0.0001 BTC = 10000 sats

    @pytest.mark.asyncio
    async def test_get_balance_no_btc(self, strike_client):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"currency": "USD", "available": "100.00"},
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.return_value = mock_response

            balance = await strike_client.get_balance()

            assert balance == 0

    def test_headers(self, strike_client):
        headers = strike_client._headers()
        assert headers["Authorization"] == "Bearer test_api_key"
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_get_invoice(self, strike_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "invoiceId": "abc123-uuid",
            "state": "PAID",
            "amount": {"amount": "0.00001000", "currency": "BTC"},
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.return_value = mock_response

            invoice_data = await strike_client.get_invoice("abc123-uuid")

            assert invoice_data["invoiceId"] == "abc123-uuid"
            assert invoice_data["state"] == "PAID"

    @pytest.mark.asyncio
    async def test_get_invoice_not_found(self, strike_client):
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.return_value = mock_response

            invoice_data = await strike_client.get_invoice("nonexistent")

            assert invoice_data is None

    @pytest.mark.asyncio
    async def test_subscribe_to_webhooks(self, strike_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "subscription123",
            "webhookUrl": "https://example.com/webhook",
            "enabled": True,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.post.return_value = mock_response

            subscription_id = await strike_client.subscribe_to_webhooks(
                "https://example.com/webhook"
            )

            assert subscription_id == "subscription123"

            # Verify the call
            call_args = mock_client_instance.post.call_args
            assert call_args[0][0] == "https://api.strike.me/v1/subscriptions"
            payload = call_args[1]["json"]
            assert payload["webhookUrl"] == "https://example.com/webhook"
            assert payload["eventTypes"] == ["invoice.updated"]
            assert payload["enabled"] is True
