"""
Unit tests for carrier scraper service.
"""
import pytest
from decimal import Decimal

from api.services.scraper import CarrierScraper, RateQuote, carrier_scraper


class TestCarrierScraper:
    """Test suite for CarrierScraper."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scrape_all_carriers_returns_quotes(self):
        """Test that scrape_all_carriers returns list of quotes."""
        scraper = CarrierScraper()
        
        quotes = await scraper.scrape_all_carriers(
            origin="Milano, Italia",
            destination="Roma, Italia",
            weight=100.0
        )
        
        assert isinstance(quotes, list)
        assert len(quotes) > 0
        
        # All items should be RateQuote instances
        for quote in quotes:
            assert isinstance(quote, RateQuote)
            assert isinstance(quote.cost_per_kg, Decimal)
            assert isinstance(quote.total_cost, Decimal)
            assert quote.delivery_days > 0
            assert quote.on_time_rating >= 0
            assert quote.on_time_rating <= 100

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scrape_all_carriers_sorted_by_cost(self):
        """Test that quotes are sorted by total cost."""
        scraper = CarrierScraper()
        
        quotes = await scraper.scrape_all_carriers(
            origin="Milano",
            destination="Roma",
            weight=500.0
        )
        
        # Verify sorting
        for i in range(len(quotes) - 1):
            assert quotes[i].total_cost <= quotes[i + 1].total_cost

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scrape_carriers_with_international_destination(self):
        """Test scraping with international destination."""
        scraper = CarrierScraper()
        
        quotes = await scraper.scrape_all_carriers(
            origin="Milano, Italia",
            destination="Berlin, Germany",
            weight=100.0
        )
        
        assert len(quotes) > 0
        # International carriers should be included
        carrier_codes = [q.carrier_code for q in quotes]
        assert "DHLE" in carrier_codes or "FEDEX" in carrier_codes or "UPS" in carrier_codes

    @pytest.mark.unit
    def test_rate_quote_dataclass(self):
        """Test RateQuote dataclass."""
        quote = RateQuote(
            carrier_code="TEST",
            carrier_name="Test Carrier",
            cost_per_kg=Decimal("1.50"),
            total_cost=Decimal("150.00"),
            delivery_days=2,
            on_time_rating=Decimal("95.50"),
            source="test"
        )
        
        assert quote.carrier_code == "TEST"
        assert quote.cost_per_kg == Decimal("1.50")
        assert quote.total_cost == Decimal("150.00")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fallback_rates_used(self):
        """Test that fallback rates are used when scraping fails."""
        scraper = CarrierScraper()
        
        quotes = await scraper.scrape_all_carriers(
            origin="Milano",
            destination="Roma",
            weight=100.0
        )
        
        # All quotes should have source="fallback" in our simplified implementation
        for quote in quotes:
            assert quote.source == "fallback"
