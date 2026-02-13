"""
Unit tests for Stripe service.
"""
import pytest
from decimal import Decimal

from api.services.stripe_service import StripeService, stripe_service


class TestStripeService:
    """Test suite for StripeService."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_checkout_session_returns_mock_when_no_key(self):
        """Test creating checkout session returns mock when no API key."""
        result = await stripe_service.create_checkout_session(
            amount=Decimal("425.00"),
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            customer_email="mario@rossi.it",
            metadata={"contract_id": "contr-123"}
        )
        
        assert "id" in result
        assert "url" in result
        assert result["mock"] == True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_checkout_session_without_email(self):
        """Test creating checkout session without customer email."""
        result = await stripe_service.create_checkout_session(
            amount=Decimal("500.00"),
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel"
        )
        
        assert "id" in result
        assert "url" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_calculate_fees(self):
        """Test fee calculation."""
        amount = Decimal("100.00")
        
        result = await stripe_service.calculate_fees(amount)
        
        # 1.5% + 0.25€ for 100€ = 1.50 + 0.25 = 1.75€
        assert result["gross_amount"] == Decimal("100.00")
        assert result["stripe_fees"] == Decimal("1.75")
        assert result["net_amount"] == Decimal("98.25")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_calculate_fees_large_amount(self):
        """Test fee calculation for large amount."""
        amount = Decimal("1000.00")
        
        result = await stripe_service.calculate_fees(amount)
        
        # 1.5% + 0.25€ for 1000€ = 15.00 + 0.25 = 15.25€
        assert result["stripe_fees"] == Decimal("15.25")
        assert result["net_amount"] == Decimal("984.75")

    @pytest.mark.unit
    def test_stripe_service_singleton(self):
        """Test that stripe_service is a singleton instance."""
        assert isinstance(stripe_service, StripeService)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_checkout_session_with_real_key(self, mocker):
        """Test creating checkout session with real API key."""
        mocker.patch("api.services.stripe_service.STRIPE_SECRET_KEY", "sk_test_xxx")
        
        mock_session = mocker.MagicMock()
        mock_session.id = "cs_real_123"
        mock_session.url = "https://checkout.stripe.com/real"
        
        mock_stripe = mocker.MagicMock()
        mock_stripe.checkout.Session.create.return_value = mock_session
        mocker.patch.object(stripe_service, "stripe", mock_stripe)
        
        result = await stripe_service.create_checkout_session(
            amount=Decimal("425.00"),
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel"
        )
        
        assert result["id"] == "cs_real_123"
        assert result["url"] == "https://checkout.stripe.com/real"
