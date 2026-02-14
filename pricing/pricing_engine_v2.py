"""
AUTO-BROKER Pricing Engine v2
Real-time pricing with market rate integration
Enterprise Integration - P1

Features:
- Base cost + margin + market adjustment
- Real-time DAT iQ rate fetching
- 95th percentile confidence interval
"""

import logging
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

import numpy as np
from scipy import stats

from market_data.dat_iq_client import DATiQClient, DATRate, DATRouteType
from services.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class PricingStrategy(Enum):
    """Pricing strategy types."""
    MARKET_BASED = "market_based"
    COST_PLUS = "cost_plus"
    VALUE_BASED = "value_based"
    COMPETITIVE = "competitive"


@dataclass
class PricingInput:
    """Input parameters for pricing calculation."""
    # Route
    origin_country: str
    origin_city: str
    dest_country: str
    dest_city: str
    distance_km: float
    
    # Cargo
    weight_kg: float
    volume_m3: Optional[float] = None
    pallets: Optional[int] = None
    adr: bool = False
    temperature_controlled: bool = False
    
    # Equipment
    equipment_type: DATRouteType = DATRouteType.VAN
    
    # Service level
    express: bool = False
    dedicated: bool = False


@dataclass
class PricingBreakdown:
    """Detailed pricing breakdown."""
    base_cost: float
    fuel_surcharge: float
    tolls: float
    driver_cost: float
    insurance: float
    margin: float
    market_adjustment: float
    expedite_fee: float
    adr_surcharge: float
    temp_control_surcharge: float
    subtotal: float
    vat_amount: float
    total: float


@dataclass
class PricingConfidence:
    """Pricing confidence interval."""
    point_estimate: float
    lower_bound_95: float
    upper_bound_95: float
    confidence_level: float = 0.95
    sample_size: int = 0
    volatility_index: float = 0.0


@dataclass
class PricingResult:
    """Complete pricing result."""
    shipment_id: str
    customer_price: float
    carrier_price: float
    margin_eur: float
    margin_pct: float
    breakdown: PricingBreakdown
    confidence: PricingConfidence
    strategy: PricingStrategy
    market_rate: Optional[DATRate]
    valid_until: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "shipment_id": self.shipment_id,
            "customer_price": round(self.customer_price, 2),
            "carrier_price": round(self.carrier_price, 2),
            "margin_eur": round(self.margin_eur, 2),
            "margin_pct": round(self.margin_pct, 2),
            "breakdown": {
                "base_cost": round(self.breakdown.base_cost, 2),
                "fuel_surcharge": round(self.breakdown.fuel_surcharge, 2),
                "tolls": round(self.breakdown.tolls, 2),
                "driver_cost": round(self.breakdown.driver_cost, 2),
                "insurance": round(self.breakdown.insurance, 2),
                "margin": round(self.breakdown.margin, 2),
                "market_adjustment": round(self.breakdown.market_adjustment, 2),
                "total": round(self.breakdown.total, 2)
            },
            "confidence": {
                "point_estimate": round(self.confidence.point_estimate, 2),
                "range_95": [
                    round(self.confidence.lower_bound_95, 2),
                    round(self.confidence.upper_bound_95, 2)
                ],
                "volatility": round(self.confidence.volatility_index, 2)
            },
            "strategy": self.strategy.value,
            "market_rate": self.market_rate.to_dict() if self.market_rate else None,
            "valid_until": self.valid_until.isoformat()
        }


class PricingEngineV2:
    """
    Advanced Pricing Engine with Market Rate Integration.
    
    Formula:
    Customer Price = Base Cost + Margin + Market Adjustment
    
    Components:
    - Base Cost: Fuel, tolls, driver, insurance
    - Margin: Configurable % or fixed amount
    - Market Adjustment: Deviation from DAT iQ benchmark
    
    Confidence Interval:
    - Uses historical volatility to calculate 95% CI
    - Based on 30-day rate history
    """
    
    def __init__(
        self,
        dat_client: Optional[DATiQClient] = None,
        default_margin_pct: float = 15.0,
        min_margin_eur: float = 50.0
    ):
        """
        Initialize pricing engine.
        
        Args:
            dat_client: DAT iQ client for market rates
            default_margin_pct: Default margin percentage
            min_margin_eur: Minimum margin in EUR
        """
        self.dat_client = dat_client
        self.default_margin_pct = default_margin_pct
        self.min_margin_eur = min_margin_eur
        
        # Cost factors (configurable per market)
        self.cost_factors = {
            "fuel_per_km": 0.35,  # EUR/km
            "toll_per_km": 0.15,  # EUR/km (average Europe)
            "driver_per_km": 0.45,  # EUR/km
            "driver_per_hour": 25.0,  # EUR/hour
            "loading_unloading_hours": 2.0,
            "insurance_per_kg": 0.001,  # EUR/kg
            "insurance_base": 50.0,
            "adr_surcharge_pct": 15.0,
            "temp_control_surcharge_pct": 20.0,
            "expedite_fee": 150.0,
            "dedicated_fee": 200.0
        }
        
        self.circuit = CircuitBreaker(
            name="pricing_engine",
            failure_threshold=3,
            recovery_timeout=30
        )
    
    async def calculate_price(
        self,
        shipment_id: str,
        input_data: PricingInput,
        strategy: PricingStrategy = PricingStrategy.MARKET_BASED,
        target_margin_pct: Optional[float] = None
    ) -> PricingResult:
        """
        Calculate shipment price with market integration.
        
        Args:
            shipment_id: Unique shipment identifier
            input_data: Pricing input parameters
            strategy: Pricing strategy to use
            target_margin_pct: Override default margin
            
        Returns:
            PricingResult with full breakdown and confidence interval
        """
        margin_pct = target_margin_pct or self.default_margin_pct
        
        # 1. Calculate base cost
        base_cost = self._calculate_base_cost(input_data)
        
        # 2. Fetch market rate
        market_rate = await self._fetch_market_rate(input_data)
        
        # 3. Calculate margin
        margin_amount = self._calculate_margin(base_cost, margin_pct)
        
        # 4. Calculate market adjustment
        market_adjustment = self._calculate_market_adjustment(
            base_cost + margin_amount,
            market_rate
        )
        
        # 5. Apply strategy
        if strategy == PricingStrategy.MARKET_BASED:
            customer_price = base_cost + margin_amount + market_adjustment
        elif strategy == PricingStrategy.COST_PLUS:
            customer_price = base_cost + margin_amount
            market_adjustment = 0
        elif strategy == PricingStrategy.COMPETITIVE:
            # Price at market rate minus small discount
            if market_rate:
                customer_price = market_rate.avg_rate * 0.98
            else:
                customer_price = base_cost + margin_amount
        else:  # VALUE_BASED
            customer_price = base_cost + margin_amount + market_adjustment
        
        # Ensure minimum margin
        carrier_price = base_cost
        actual_margin = customer_price - carrier_price
        if actual_margin < self.min_margin_eur:
            customer_price = carrier_price + self.min_margin_eur
            actual_margin = self.min_margin_eur
        
        # Build breakdown
        breakdown = self._build_breakdown(
            input_data, base_cost, margin_amount, market_adjustment
        )
        
        # Calculate confidence interval
        confidence = await self._calculate_confidence(
            input_data, customer_price
        )
        
        return PricingResult(
            shipment_id=shipment_id,
            customer_price=round(customer_price, 2),
            carrier_price=round(carrier_price, 2),
            margin_eur=round(actual_margin, 2),
            margin_pct=round((actual_margin / customer_price) * 100, 2),
            breakdown=breakdown,
            confidence=confidence,
            strategy=strategy,
            market_rate=market_rate,
            valid_until=datetime.now() + timedelta(hours=24)
        )
    
    def _calculate_base_cost(self, input_data: PricingInput) -> float:
        """Calculate base transportation cost."""
        distance = input_data.distance_km
        
        # Distance-based costs
        fuel_cost = distance * self.cost_factors["fuel_per_km"]
        toll_cost = distance * self.cost_factors["toll_per_km"]
        driver_distance_cost = distance * self.cost_factors["driver_per_km"]
        
        # Time-based costs (assume 70 km/h average)
        driving_hours = distance / 70.0
        total_hours = driving_hours + self.cost_factors["loading_unloading_hours"]
        driver_time_cost = total_hours * self.cost_factors["driver_per_hour"]
        driver_cost = max(driver_distance_cost, driver_time_cost)
        
        # Insurance
        insurance = (
            self.cost_factors["insurance_base"] +
            input_data.weight_kg * self.cost_factors["insurance_per_kg"]
        )
        
        # Surcharges
        adr_surcharge = 0
        if input_data.adr:
            adr_surcharge = fuel_cost * (self.cost_factors["adr_surcharge_pct"] / 100)
        
        temp_surcharge = 0
        if input_data.temperature_controlled:
            temp_surcharge = fuel_cost * (self.cost_factors["temp_control_surcharge_pct"] / 100)
        
        expedite_fee = self.cost_factors["expedite_fee"] if input_data.express else 0
        dedicated_fee = self.cost_factors["dedicated_fee"] if input_data.dedicated else 0
        
        base_cost = (
            fuel_cost + toll_cost + driver_cost + insurance +
            adr_surcharge + temp_surcharge + expedite_fee + dedicated_fee
        )
        
        return base_cost
    
    def _calculate_margin(self, base_cost: float, margin_pct: float) -> float:
        """Calculate margin amount."""
        margin = base_cost * (margin_pct / 100)
        return max(margin, self.min_margin_eur)
    
    async def _fetch_market_rate(
        self,
        input_data: PricingInput
    ) -> Optional[DATRate]:
        """Fetch market rate from DAT iQ."""
        if not self.dat_client:
            return None
        
        try:
            # Map locations to DAT format
            origin = f"{input_data.origin_country}-{input_data.origin_city[:3].upper()}"
            dest = f"{input_data.dest_country}-{input_data.dest_city[:3].upper()}"
            
            rate = await self.circuit.call(
                self.dat_client.get_spot_rate,
                origin=origin,
                destination=dest,
                route_type=input_data.equipment_type
            )
            
            return rate
            
        except Exception as e:
            logger.warning(f"Failed to fetch market rate: {e}")
            return None
    
    def _calculate_market_adjustment(
        self,
        current_price: float,
        market_rate: Optional[DATRate]
    ) -> float:
        """
        Calculate market adjustment.
        
        If our price is significantly below market, adjust up.
        If significantly above, consider adjusting down.
        """
        if not market_rate:
            return 0.0
        
        market_avg = market_rate.avg_rate
        deviation = (current_price - market_avg) / market_avg
        
        # If we're more than 10% below market, adjust up
        if deviation < -0.10:
            adjustment = market_avg * 0.05  # Move 5% toward market
            return adjustment
        
        # If we're more than 20% above market, adjust down slightly
        if deviation > 0.20:
            adjustment = -market_avg * 0.03  # Reduce 3%
            return adjustment
        
        return 0.0
    
    def _build_breakdown(
        self,
        input_data: PricingInput,
        base_cost: float,
        margin: float,
        market_adjustment: float
    ) -> PricingBreakdown:
        """Build detailed cost breakdown."""
        distance = input_data.distance_km
        
        fuel = distance * self.cost_factors["fuel_per_km"]
        tolls = distance * self.cost_factors["toll_per_km"]
        driver = self._calculate_base_cost(input_data) - fuel - tolls
        
        # Adjust driver cost to remove surcharges
        adr = fuel * (self.cost_factors["adr_surcharge_pct"] / 100) if input_data.adr else 0
        temp = fuel * (self.cost_factors["temp_control_surcharge_pct"] / 100) if input_data.temperature_controlled else 0
        expedite = self.cost_factors["expedite_fee"] if input_data.express else 0
        driver = driver - adr - temp - expedite
        
        insurance = self.cost_factors["insurance_base"] + input_data.weight_kg * 0.001
        
        subtotal = base_cost + margin + market_adjustment
        vat = subtotal * 0.22  # Italian VAT
        
        return PricingBreakdown(
            base_cost=round(base_cost, 2),
            fuel_surcharge=round(fuel, 2),
            tolls=round(tolls, 2),
            driver_cost=round(driver, 2),
            insurance=round(insurance, 2),
            margin=round(margin, 2),
            market_adjustment=round(market_adjustment, 2),
            expedite_fee=expedite if input_data.express else 0,
            adr_surcharge=adr,
            temp_control_surcharge=temp,
            subtotal=round(subtotal, 2),
            vat_amount=round(vat, 2),
            total=round(subtotal + vat, 2)
        )
    
    async def _calculate_confidence(
        self,
        input_data: PricingInput,
        point_estimate: float
    ) -> PricingConfidence:
        """Calculate 95% confidence interval."""
        if not self.dat_client:
            # No market data, return wide interval
            return PricingConfidence(
                point_estimate=point_estimate,
                lower_bound_95=point_estimate * 0.8,
                upper_bound_95=point_estimate * 1.2,
                sample_size=0,
                volatility_index=0.3
            )
        
        try:
            # Fetch historical rates
            origin = f"{input_data.origin_country}-{input_data.origin_city[:3].upper()}"
            dest = f"{input_data.dest_country}-{input_data.dest_city[:3].upper()}"
            
            history = await self.circuit.call(
                self.dat_client.get_historical_rates,
                origin=origin,
                destination=dest,
                days=30,
                route_type=input_data.equipment_type
            )
            
            if len(history) < 7:
                # Insufficient data
                return PricingConfidence(
                    point_estimate=point_estimate,
                    lower_bound_95=point_estimate * 0.85,
                    upper_bound_95=point_estimate * 1.15,
                    sample_size=len(history),
                    volatility_index=0.2
                )
            
            # Calculate statistics
            rates = [r.avg_rate for r in history]
            mean = np.mean(rates)
            std = np.std(rates)
            
            # 95% confidence interval using t-distribution
            confidence_level = 0.95
            degrees_freedom = len(rates) - 1
            t_value = stats.t.ppf((1 + confidence_level) / 2, degrees_freedom)
            
            margin_error = t_value * (std / np.sqrt(len(rates)))
            
            # Adjust based on our pricing
            deviation = point_estimate / mean if mean > 0 else 1.0
            
            lower = point_estimate - margin_error * deviation
            upper = point_estimate + margin_error * deviation
            
            # Volatility index (coefficient of variation)
            volatility = std / mean if mean > 0 else 0
            
            return PricingConfidence(
                point_estimate=point_estimate,
                lower_bound_95=round(max(lower, point_estimate * 0.7), 2),
                upper_bound_95=round(min(upper, point_estimate * 1.3), 2),
                confidence_level=0.95,
                sample_size=len(rates),
                volatility_index=round(volatility, 3)
            )
            
        except Exception as e:
            logger.warning(f"Failed to calculate confidence: {e}")
            return PricingConfidence(
                point_estimate=point_estimate,
                lower_bound_95=point_estimate * 0.85,
                upper_bound_95=point_estimate * 1.15,
                sample_size=0,
                volatility_index=0.2
            )
    
    async def batch_calculate(
        self,
        requests: List[Tuple[str, PricingInput]]
    ) -> List[PricingResult]:
        """Calculate prices for multiple shipments."""
        tasks = [
            self.calculate_price(shipment_id, input_data)
            for shipment_id, input_data in requests
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    def update_cost_factors(self, factors: Dict[str, float]) -> None:
        """Update cost factor configuration."""
        self.cost_factors.update(factors)
        logger.info(f"Updated cost factors: {factors}")


# Import required for calculate_price method
from datetime import timedelta
