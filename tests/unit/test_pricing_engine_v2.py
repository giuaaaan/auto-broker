"""
Unit tests for Pricing Engine V2
Tests market rate integration and confidence interval calculation
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from pricing.pricing_engine_v2 import (
    PricingEngineV2,
    PricingInput,
    PricingStrategy,
    PricingBreakdown
)
from market_data.dat_iq_client import DATRate, DATRouteType


@pytest.fixture
def mock_dat_client():
    """Mock DAT iQ client."""
    client = MagicMock()
    client.get_spot_rate = AsyncMock(return_value=DATRate(
        route="IT-MIL-IT-ROM",
        route_type=DATRouteType.VAN,
        avg_rate=450.0,
        low_rate=380.0,
        high_rate=520.0,
        rate_per_km=0.90,
        fuel_surcharge=45.0,
        timestamp=datetime.now(),
        equipment_type="VAN",
        distance_km=500
    ))
    client.get_historical_rates = AsyncMock(return_value=[])
    return client


@pytest.fixture
def pricing_engine(mock_dat_client):
    """Pricing engine with mocked DAT client."""
    return PricingEngineV2(
        dat_client=mock_dat_client,
        default_margin_pct=15.0,
        min_margin_eur=50.0
    )


@pytest.fixture
def sample_pricing_input():
    """Sample pricing input."""
    return PricingInput(
        origin_country="IT",
        origin_city="Milano",
        dest_country="IT",
        dest_city="Roma",
        distance_km=500,
        weight_kg=5000,
        equipment_type=DATRouteType.VAN
    )


class TestPricingEngineV2:
    """Test Pricing Engine V2 functionality."""
    
    @pytest.mark.asyncio
    async def test_calculate_price_basic(self, pricing_engine, sample_pricing_input):
        """Test basic price calculation."""
        result = await pricing_engine.calculate_price(
            shipment_id="TEST001",
            input_data=sample_pricing_input,
            strategy=PricingStrategy.COST_PLUS
        )
        
        assert result.shipment_id == "TEST001"
        assert result.customer_price > 0
        assert result.carrier_price > 0
        assert result.margin_eur >= 50.0  # Minimum margin
        assert result.margin_pct >= 0
        assert result.breakdown is not None
        assert result.confidence is not None
    
    @pytest.mark.asyncio
    async def test_market_based_strategy(self, pricing_engine, sample_pricing_input):
        """Test market-based pricing strategy."""
        result = await pricing_engine.calculate_price(
            shipment_id="TEST002",
            input_data=sample_pricing_input,
            strategy=PricingStrategy.MARKET_BASED
        )
        
        # Market rate should be fetched
        pricing_engine.dat_client.get_spot_rate.assert_called_once()
        assert result.market_rate is not None
        assert result.market_rate.avg_rate == 450.0
    
    @pytest.mark.asyncio
    async def test_cost_plus_strategy_no_market(self, pricing_engine, sample_pricing_input):
        """Test cost-plus pricing doesn't require market data."""
        # Set market rate to None
        pricing_engine.dat_client.get_spot_rate = AsyncMock(return_value=None)
        
        result = await pricing_engine.calculate_price(
            shipment_id="TEST003",
            input_data=sample_pricing_input,
            strategy=PricingStrategy.COST_PLUS
        )
        
        assert result.customer_price > 0
        assert result.market_rate is None
    
    @pytest.mark.asyncio
    async def test_margin_enforcement(self, pricing_engine, sample_pricing_input):
        """Test minimum margin enforcement."""
        # Set very low margin percentage
        result = await pricing_engine.calculate_price(
            shipment_id="TEST004",
            input_data=sample_pricing_input,
            strategy=PricingStrategy.COST_PLUS,
            target_margin_pct=1.0  # Very low %
        )
        
        # Should still respect minimum margin
        assert result.margin_eur >= 50.0
    
    @pytest.mark.asyncio
    async def test_breakdown_components(self, pricing_engine, sample_pricing_input):
        """Test pricing breakdown components."""
        result = await pricing_engine.calculate_price(
            shipment_id="TEST005",
            input_data=sample_pricing_input,
            strategy=PricingStrategy.COST_PLUS
        )
        
        breakdown = result.breakdown
        assert breakdown.base_cost > 0
        assert breakdown.fuel_surcharge > 0
        assert breakdown.tolls >= 0
        assert breakdown.driver_cost > 0
        assert breakdown.margin > 0
        assert breakdown.total > breakdown.subtotal
    
    @pytest.mark.asyncio
    async def test_adr_surcharge(self, pricing_engine, sample_pricing_input):
        """Test ADR dangerous goods surcharge."""
        input_adr = PricingInput(
            origin_country="IT",
            origin_city="Milano",
            dest_country="IT",
            dest_city="Roma",
            distance_km=500,
            weight_kg=5000,
            equipment_type=DATRouteType.VAN,
            adr=True
        )
        
        result_adr = await pricing_engine.calculate_price(
            shipment_id="TEST006",
            input_data=input_adr,
            strategy=PricingStrategy.COST_PLUS
        )
        
        assert result_adr.breakdown.adr_surcharge > 0
    
    @pytest.mark.asyncio
    async def test_temperature_control_surcharge(self, pricing_engine, sample_pricing_input):
        """Test temperature controlled surcharge."""
        input_temp = PricingInput(
            origin_country="IT",
            origin_city="Milano",
            dest_country="IT",
            dest_city="Roma",
            distance_km=500,
            weight_kg=5000,
            equipment_type=DATRouteType.VAN,
            temperature_controlled=True
        )
        
        result_temp = await pricing_engine.calculate_price(
            shipment_id="TEST007",
            input_data=input_temp,
            strategy=PricingStrategy.COST_PLUS
        )
        
        assert result_temp.breakdown.temp_control_surcharge > 0
    
    @pytest.mark.asyncio
    async def test_express_fee(self, pricing_engine, sample_pricing_input):
        """Test express delivery fee."""
        input_express = PricingInput(
            origin_country="IT",
            origin_city="Milano",
            dest_country="IT",
            dest_city="Roma",
            distance_km=500,
            weight_kg=5000,
            equipment_type=DATRouteType.VAN,
            express=True
        )
        
        result_express = await pricing_engine.calculate_price(
            shipment_id="TEST008",
            input_data=input_express,
            strategy=PricingStrategy.COST_PLUS
        )
        
        assert result_express.breakdown.expedite_fee > 0
    
    def test_base_cost_calculation(self, pricing_engine, sample_pricing_input):
        """Test base cost calculation."""
        base_cost = pricing_engine._calculate_base_cost(sample_pricing_input)
        
        # 500km * (0.35 fuel + 0.15 toll + 0.45 driver) + insurance
        assert base_cost > 0
        # Should be roughly: 500 * 0.95 + ~65 = ~540
        assert 400 < base_cost < 700


class TestPricingConfidence:
    """Test confidence interval calculation."""
    
    @pytest.mark.asyncio
    async def test_confidence_interval_without_market(self, pricing_engine, sample_pricing_input):
        """Test confidence without market data."""
        pricing_engine.dat_client = None
        
        result = await pricing_engine.calculate_price(
            shipment_id="TEST009",
            input_data=sample_pricing_input,
            strategy=PricingStrategy.COST_PLUS
        )
        
        # Should return wide interval
        assert result.confidence.lower_bound_95 < result.confidence.point_estimate
        assert result.confidence.upper_bound_95 > result.confidence.point_estimate
        assert result.confidence.sample_size == 0


class TestPricingStrategies:
    """Test different pricing strategies."""
    
    @pytest.mark.asyncio
    async def test_competitive_strategy(self, pricing_engine, sample_pricing_input):
        """Test competitive pricing strategy."""
        result = await pricing_engine.calculate_price(
            shipment_id="TEST010",
            input_data=sample_pricing_input,
            strategy=PricingStrategy.COMPETITIVE
        )
        
        assert result.strategy == PricingStrategy.COMPETITIVE
        assert result.market_rate is not None
    
    @pytest.mark.asyncio
    async def test_value_based_strategy(self, pricing_engine, sample_pricing_input):
        """Test value-based pricing strategy."""
        result = await pricing_engine.calculate_price(
            shipment_id="TEST011",
            input_data=sample_pricing_input,
            strategy=PricingStrategy.VALUE_BASED
        )
        
        assert result.strategy == PricingStrategy.VALUE_BASED
        assert result.customer_price > 0
