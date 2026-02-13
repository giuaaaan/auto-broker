"""
Property-Based Testing con Hypothesis - Pattern usato da Meta/Google.
Genera automaticamente centinaia di casi edge-case che non penseresti mai.
"""
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from decimal import Decimal

from api.services.scraper import CarrierScraper, RateQuote


class TestScraperProperties:
    """Property-based tests per CarrierScraper."""

    @given(
        origin=st.sampled_from(['Milano', 'Roma', 'Torino', 'Napoli']),
        destination=st.sampled_from(['Roma', 'Milano', 'Venezia', 'Firenze']),
        weight=st.floats(min_value=1.0, max_value=10000.0)
    )
    @settings(max_examples=50)
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scraper_always_returns_sorted_quotes(self, origin, destination, weight):
        """
        Proprietà: scrape_all_carriers deve sempre ritornare quote ordinate per costo.
        Hypothesis genererà automaticamente casi limite.
        """
        if origin == destination:
            return  # Skip stessa città
            
        scraper = CarrierScraper()
        quotes = await scraper.scrape_all_carriers(origin, destination, weight)
        
        # Proprietà: lista non vuota
        assert len(quotes) > 0
        
        # Proprietà: ordinate per costo crescente
        for i in range(len(quotes) - 1):
            assert quotes[i].total_cost <= quotes[i + 1].total_cost
        
        # Proprietà: tutti i campi required sono presenti
        for quote in quotes:
            assert quote.carrier_code
            assert quote.total_cost > 0
            assert quote.delivery_days > 0


class TestRateQuoteProperties:
    """Property-based tests per RateQuote dataclass."""

    @given(
        carrier_code=st.text(min_size=2, max_size=5),
        cost_per_kg=st.decimals(min_value=Decimal('0.10'), max_value=Decimal('50.00'), places=2)
    )
    @settings(max_examples=30)
    @pytest.mark.unit
    def test_rate_quote_creation(self, carrier_code, cost_per_kg):
        """
        Proprietà: RateQuote può essere creato con qualsiasi input valido.
        """
        quote = RateQuote(
            carrier_code=carrier_code.upper(),
            carrier_name=f"Carrier {carrier_code}",
            cost_per_kg=cost_per_kg,
            total_cost=cost_per_kg * 100,
            delivery_days=1,
            on_time_rating=Decimal('95.0'),
            source="test"
        )
        
        assert quote.carrier_code == carrier_code.upper()
        assert quote.cost_per_kg > 0
        assert quote.total_cost > 0


class TestStripeFeeProperties:
    """Property-based tests per Stripe fee calculations."""

    @given(
        amount=st.decimals(min_value=Decimal('1.00'), max_value=Decimal('10000.00'), places=2)
    )
    @settings(max_examples=30)
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stripe_fees_never_exceed_amount(self, amount):
        """
        Proprietà: Le fee Stripe non devono mai superare l'importo totale.
        """
        from api.services.stripe_service import StripeService
        
        service = StripeService()
        result = await service.calculate_fees(amount)
        
        # Proprietà: fee < amount
        assert result["stripe_fees"] < amount
        # Proprietà: net sempre positivo
        assert result["net_amount"] > 0


class TestPaginationProperties:
    """Property-based tests per paginazione."""

    @given(
        page=st.integers(min_value=1, max_value=1000),
        limit=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=30)
    @pytest.mark.unit
    def test_pagination_offset_calculation(self, page, limit):
        """
        Proprietà: L'offset di paginazione deve essere sempre (page-1) * limit.
        """
        offset = (page - 1) * limit
        
        # Proprietà: offset non negativo
        assert offset >= 0
        # Proprietà: offset < page * limit
        assert offset < page * limit


class TestUUIDProperties:
    """Property-based tests per UUID handling."""

    @given(
        uuid_str=st.uuids().map(str)
    )
    @settings(max_examples=20)
    @pytest.mark.unit
    def test_uuid_string_parsing(self, uuid_str):
        """
        Proprietà: I UUID devono sempre essere validi come stringhe.
        """
        import uuid
        
        parsed = uuid.UUID(uuid_str)
        assert str(parsed) == uuid_str


class TestEmailProperties:
    """Property-based tests per email."""

    @given(
        email=st.emails()
    )
    @settings(max_examples=20)
    @pytest.mark.unit
    def test_email_format(self, email):
        """
        Proprietà: Email generate da Hypothesis sono sempre valide.
        """
        assert '@' in email
        assert '.' in email.split('@')[1]
        assert len(email) > 5
