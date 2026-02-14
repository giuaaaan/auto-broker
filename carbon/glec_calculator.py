"""
AUTO-BROKER GLEC Framework Carbon Calculator
ISO 14083-compliant emissions calculation
Enterprise Integration - P1

Features:
- Well-to-wheel (WTW) emissions calculation
- CO2 equivalents (CO2e)
- CSRD reporting format
- Transport mode specific factors
"""

import logging
from dataclasses import dataclass
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class TransportMode(Enum):
    """GLEC Framework transport modes."""
    ROAD = "road"
    ROAD_HGV = "road_hgv"  # Heavy goods vehicle
    ROAD_LGV = "road_lgv"  # Light goods vehicle
    RAIL = "rail"
    SEA = "sea"
    AIR = "air"
    INLAND_WATERWAY = "inland_waterway"


class FuelType(Enum):
    """Fuel types for emission factors."""
    DIESEL = "diesel"
    PETROL = "petrol"
    LNG = "lng"
    CNG = "cng"
    ELECTRIC = "electric"
    HYDROGEN = "hydrogen"
    BIODIESEL = "biodiesel"
    HVO = "hvo"  # Hydrotreated vegetable oil


@dataclass
class EmissionFactors:
    """Emission factors for a transport mode (kg CO2e per ton-km)."""
    # Well-to-tank (WTT) - fuel production
    wtt_co2: float
    wtt_ch4: float
    wtt_n2o: float
    
    # Tank-to-wheel (TTW) - vehicle operation
    ttw_co2: float
    ttw_ch4: float
    ttw_n2o: float
    
    @property
    def wtw_co2(self) -> float:
        """Well-to-wheel CO2."""
        return self.wtt_co2 + self.ttw_co2
    
    @property
    def wtw_total(self) -> float:
        """Total WTW CO2e (CO2 + CH4*28 + N2O*265)."""
        co2 = self.wtw_co2
        ch4 = (self.wtt_ch4 + self.ttw_ch4) * 28  # GWP100
        n2o = (self.wtt_n2o + self.ttw_n2o) * 265  # GWP100
        return co2 + ch4 + n2o


@dataclass
class ShipmentEmissions:
    """Calculated emissions for a shipment."""
    shipment_id: str
    transport_mode: TransportMode
    fuel_type: FuelType
    distance_km: float
    weight_tons: float
    
    # Emissions (kg CO2e)
    wtt_emissions: float
    ttw_emissions: float
    wtw_emissions: float
    
    # Intensity (kg CO2e per ton-km)
    intensity: float
    
    # Uncertainty
    uncertainty_low: float
    uncertainty_high: float
    
    # Metadata
    calculation_date: datetime
    glec_version: str = "3.0"
    iso_14083_compliant: bool = True


@dataclass
class CSRDReportEntry:
    """CSRD (Corporate Sustainability Reporting Directive) entry."""
    reporting_period: date
    entity_name: str
    transport_mode: str
    total_ton_km: float
    total_emissions_tons_co2e: float
    intensity_kg_co2e_per_ton_km: float
    methodology: str
    assurance_level: str  # Limited, Reasonable


class GLECCalculator:
    """
    GLEC Framework v3.0 Carbon Calculator.
    
    Implements ISO 14083:2023 methodology for greenhouse gas
    emissions calculation in transport and logistics.
    
    Features:
    - Well-to-wheel (WTW) emissions
    - CO2 equivalents with GWP100
    - Transport mode specific factors
    - Fuel type variations
    - CSRD reporting format
    """
    
    # GLEC v3.0 Default Emission Factors (kg CO2e per ton-km)
    DEFAULT_FACTORS: Dict[Tuple[TransportMode, FuelType], EmissionFactors] = {
        # Road - Diesel HGV (40t, EURO 6)
        (TransportMode.ROAD_HGV, FuelType.DIESEL): EmissionFactors(
            wtt_co2=0.008, wtt_ch4=0.0001, wtt_n2o=0.00001,
            ttw_co2=0.062, ttw_ch4=0.0001, ttw_n2o=0.002
        ),
        # Road - LNG HGV
        (TransportMode.ROAD_HGV, FuelType.LNG): EmissionFactors(
            wtt_co2=0.012, wtt_ch4=0.0005, wtt_n2o=0.00001,
            ttw_co2=0.056, ttw_ch4=0.001, ttw_n2o=0.002
        ),
        # Road - Electric HGV (EU grid mix)
        (TransportMode.ROAD_HGV, FuelType.ELECTRIC): EmissionFactors(
            wtt_co2=0.018, wtt_ch4=0.0001, wtt_n2o=0.00001,
            ttw_co2=0.000, ttw_ch4=0.000, ttw_n2o=0.000
        ),
        # Road - HVO HGV
        (TransportMode.ROAD_HGV, FuelType.HVO): EmissionFactors(
            wtt_co2=0.003, wtt_ch4=0.0001, wtt_n2o=0.00001,
            ttw_co2=0.062, ttw_ch4=0.0001, ttw_n2o=0.002
        ),
        # Rail - Electric (EU grid mix)
        (TransportMode.RAIL, FuelType.ELECTRIC): EmissionFactors(
            wtt_co2=0.012, wtt_ch4=0.0001, wtt_n2o=0.00001,
            ttw_co2=0.000, ttw_ch4=0.000, ttw_n2o=0.000
        ),
        # Rail - Diesel
        (TransportMode.RAIL, FuelType.DIESEL): EmissionFactors(
            wtt_co2=0.005, wtt_ch4=0.0001, wtt_n2o=0.00001,
            ttw_co2=0.018, ttw_ch4=0.0001, ttw_n2o=0.001
        ),
        # Sea - Container ship (average)
        (TransportMode.SEA, FuelType.DIESEL): EmissionFactors(
            wtt_co2=0.004, wtt_ch4=0.0002, wtt_n2o=0.00001,
            ttw_co2=0.016, ttw_ch4=0.0002, ttw_n2o=0.001
        ),
        # Air - Freighter
        (TransportMode.AIR, FuelType.DIESEL): EmissionFactors(
            wtt_co2=0.180, wtt_ch4=0.001, wtt_n2o=0.0001,
            ttw_co2=0.602, ttw_ch4=0.001, ttw_n2o=0.019
        ),
    }
    
    # Uncertainty ranges by transport mode (percentage)
    UNCERTAINTY_RANGES: Dict[TransportMode, Tuple[float, float]] = {
        TransportMode.ROAD_HGV: (-10, 15),
        TransportMode.ROAD_LGV: (-15, 20),
        TransportMode.RAIL: (-8, 12),
        TransportMode.SEA: (-20, 25),
        TransportMode.AIR: (-5, 10),
        TransportMode.INLAND_WATERWAY: (-15, 20),
    }
    
    def __init__(self, custom_factors: Optional[Dict] = None):
        """
        Initialize calculator.
        
        Args:
            custom_factors: Override default emission factors
        """
        self.factors = self.DEFAULT_FACTORS.copy()
        if custom_factors:
            self.factors.update(custom_factors)
        
        self.calculation_log: List[Dict] = []
    
    def get_emission_factors(
        self,
        mode: TransportMode,
        fuel: FuelType
    ) -> EmissionFactors:
        """Get emission factors for transport mode and fuel."""
        key = (mode, fuel)
        
        if key in self.factors:
            return self.factors[key]
        
        # Try to find closest match
        if mode == TransportMode.ROAD:
            mode = TransportMode.ROAD_HGV
        
        key = (mode, fuel)
        if key in self.factors:
            return self.factors[key]
        
        # Default to road diesel
        logger.warning(f"No factors for {mode}/{fuel}, using road diesel")
        return self.factors.get(
            (TransportMode.ROAD_HGV, FuelType.DIESEL),
            EmissionFactors(0, 0, 0, 0.062, 0, 0.002)
        )
    
    def calculate_shipment_emissions(
        self,
        shipment_id: str,
        transport_mode: TransportMode,
        fuel_type: FuelType,
        distance_km: float,
        weight_kg: float,
        empty_running_factor: float = 1.0,
        temperature_controlled: bool = False
    ) -> ShipmentEmissions:
        """
        Calculate emissions for a shipment.
        
        Args:
            shipment_id: Unique identifier
            transport_mode: Mode of transport
            fuel_type: Fuel type used
            distance_km: Distance in kilometers
            weight_kg: Cargo weight in kilograms
            empty_running_factor: Factor for empty running (default 1.0)
            temperature_controlled: If cargo requires refrigeration
            
        Returns:
            ShipmentEmissions with calculated values
        """
        weight_tons = weight_kg / 1000
        ton_km = weight_tons * distance_km
        
        # Get emission factors
        factors = self.get_emission_factors(transport_mode, fuel_type)
        
        # Calculate emissions
        intensity = factors.wtw_total
        
        # Apply empty running factor
        intensity *= empty_running_factor
        
        # Temperature control surcharge (+15% for refrigeration)
        if temperature_controlled:
            intensity *= 1.15
        
        # Total emissions
        wtw_emissions = intensity * ton_km
        wtt_emissions = (factors.wtt_co2 * 28 * factors.wtt_ch4 * 265 * factors.wtt_n2o) * ton_km
        ttw_emissions = wtw_emissions - wtt_emissions
        
        # Uncertainty
        uncertainty = self.UNCERTAINTY_RANGES.get(
            transport_mode,
            (-15, 20)
        )
        
        emissions = ShipmentEmissions(
            shipment_id=shipment_id,
            transport_mode=transport_mode,
            fuel_type=fuel_type,
            distance_km=distance_km,
            weight_tons=weight_tons,
            wtt_emissions=wtt_emissions,
            ttw_emissions=ttw_emissions,
            wtw_emissions=wtw_emissions,
            intensity=intensity,
            uncertainty_low=wtw_emissions * (1 + uncertainty[0] / 100),
            uncertainty_high=wtw_emissions * (1 + uncertainty[1] / 100),
            calculation_date=datetime.now(),
            glec_version="3.0",
            iso_14083_compliant=True
        )
        
        # Log calculation
        self.calculation_log.append({
            'shipment_id': shipment_id,
            'mode': transport_mode.value,
            'fuel': fuel_type.value,
            'distance': distance_km,
            'weight_tons': weight_tons,
            'emissions_kg': wtw_emissions,
            'calculated_at': datetime.now().isoformat()
        })
        
        return emissions
    
    def calculate_multi_leg_shipment(
        self,
        shipment_id: str,
        legs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate emissions for multi-leg shipment.
        
        Args:
            shipment_id: Shipment identifier
            legs: List of {
                transport_mode, fuel_type, distance_km, weight_kg,
                empty_running_factor, temperature_controlled
            }
            
        Returns:
            Aggregated emissions report
        """
        leg_emissions = []
        total_wtw = 0
        total_wtt = 0
        total_ttw = 0
        total_ton_km = 0
        
        for i, leg in enumerate(legs):
            leg_id = f"{shipment_id}_leg_{i+1}"
            
            emissions = self.calculate_shipment_emissions(
                shipment_id=leg_id,
                transport_mode=leg['transport_mode'],
                fuel_type=leg.get('fuel_type', FuelType.DIESEL),
                distance_km=leg['distance_km'],
                weight_kg=leg['weight_kg'],
                empty_running_factor=leg.get('empty_running_factor', 1.0),
                temperature_controlled=leg.get('temperature_controlled', False)
            )
            
            leg_emissions.append(emissions)
            total_wtw += emissions.wtw_emissions
            total_wtt += emissions.wtt_emissions
            total_ttw += emissions.ttw_emissions
            total_ton_km += emissions.weight_tons * emissions.distance_km
        
        # Calculate weighted intensity
        avg_intensity = total_wtw / total_ton_km if total_ton_km > 0 else 0
        
        return {
            'shipment_id': shipment_id,
            'num_legs': len(legs),
            'leg_emissions': [self._emissions_to_dict(e) for e in leg_emissions],
            'total_wtw_kg': round(total_wtw, 2),
            'total_wtt_kg': round(total_wtt, 2),
            'total_ttw_kg': round(total_ttw, 2),
            'total_ton_km': round(total_ton_km, 2),
            'avg_intensity': round(avg_intensity, 4),
            'calculation_date': datetime.now().isoformat()
        }
    
    def generate_csrd_report(
        self,
        entity_name: str,
        reporting_period: date,
        shipments: List[ShipmentEmissions],
        assurance_level: str = "Limited"
    ) -> CSRDReportEntry:
        """
        Generate CSRD-compliant emissions report.
        
        Args:
            entity_name: Company name
            reporting_period: Reporting period date
            shipments: List of shipment emissions
            assurance_level: Limited or Reasonable
            
        Returns:
            CSRDReportEntry
        """
        total_ton_km = sum(
            s.weight_tons * s.distance_km for s in shipments
        )
        total_emissions = sum(s.wtw_emissions for s in shipments)
        
        intensity = (
            (total_emissions / total_ton_km) if total_ton_km > 0 else 0
        )
        
        return CSRDReportEntry(
            reporting_period=reporting_period,
            entity_name=entity_name,
            transport_mode="Mixed",
            total_ton_km=total_ton_km,
            total_emissions_tons_co2e=total_emissions / 1000,
            intensity_kg_co2e_per_ton_km=intensity,
            methodology="GLEC Framework v3.0 / ISO 14083:2023",
            assurance_level=assurance_level
        )
    
    def compare_emissions_scenarios(
        self,
        shipment_id: str,
        base_scenario: Dict[str, Any],
        alternative_scenarios: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compare emissions across different scenarios.
        
        Useful for mode shift analysis and optimization.
        """
        base = self.calculate_shipment_emissions(
            shipment_id=f"{shipment_id}_base",
            **base_scenario
        )
        
        alternatives = []
        for i, scenario in enumerate(alternative_scenarios):
            alt = self.calculate_shipment_emissions(
                shipment_id=f"{shipment_id}_alt_{i+1}",
                **scenario
            )
            
            savings = base.wtw_emissions - alt.wtw_emissions
            savings_pct = (savings / base.wtw_emissions * 100) if base.wtw_emissions > 0 else 0
            
            alternatives.append({
                'scenario_name': scenario.get('name', f'Alternative {i+1}'),
                'emissions': self._emissions_to_dict(alt),
                'savings_kg': round(savings, 2),
                'savings_percent': round(savings_pct, 2)
            })
        
        return {
            'shipment_id': shipment_id,
            'base_scenario': self._emissions_to_dict(base),
            'alternatives': alternatives,
            'best_alternative': min(alternatives, key=lambda x: x['emissions']['wtw_emissions'])
                if alternatives else None
        }
    
    def get_emission_intensity_benchmark(
        self,
        transport_mode: TransportMode
    ) -> Dict[str, float]:
        """Get emission intensity benchmarks for transport mode."""
        benchmarks = {
            TransportMode.ROAD_HGV: {
                'best_in_class': 0.040,  # Electric with renewables
                'market_average': 0.072,  # Diesel EURO 6
                'worst_in_class': 0.100  # Old diesel
            },
            TransportMode.RAIL: {
                'best_in_class': 0.008,  # Electric with renewables
                'market_average': 0.018,
                'worst_in_class': 0.025
            },
            TransportMode.SEA: {
                'best_in_class': 0.010,
                'market_average': 0.020,
                'worst_in_class': 0.040
            },
            TransportMode.AIR: {
                'best_in_class': 0.500,
                'market_average': 0.602,
                'worst_in_class': 0.800
            }
        }
        
        return benchmarks.get(transport_mode, {
            'best_in_class': 0,
            'market_average': 0,
            'worst_in_class': 0
        })
    
    def _emissions_to_dict(self, emissions: ShipmentEmissions) -> Dict[str, Any]:
        """Convert ShipmentEmissions to dictionary."""
        return {
            'shipment_id': emissions.shipment_id,
            'transport_mode': emissions.transport_mode.value,
            'fuel_type': emissions.fuel_type.value,
            'distance_km': emissions.distance_km,
            'weight_tons': emissions.weight_tons,
            'wtt_emissions_kg': round(emissions.wtt_emissions, 2),
            'ttw_emissions_kg': round(emissions.ttw_emissions, 2),
            'wtw_emissions_kg': round(emissions.wtw_emissions, 2),
            'intensity': round(emissions.intensity, 4),
            'uncertainty_range': [
                round(emissions.uncertainty_low, 2),
                round(emissions.uncertainty_high, 2)
            ],
            'glec_version': emissions.glec_version,
            'iso_14083_compliant': emissions.iso_14083_compliant
        }
    
    def export_calculation_log(self, format: str = "json") -> Any:
        """Export calculation log."""
        if format == "json":
            return self.calculation_log
        elif format == "csv":
            import csv
            import io
            
            if not self.calculation_log:
                return ""
            
            output = io.StringIO()
            writer = csv.DictWriter(
                output,
                fieldnames=self.calculation_log[0].keys()
            )
            writer.writeheader()
            writer.writerows(self.calculation_log)
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported format: {format}")


# Convenience functions

def calculate_road_emissions(
    shipment_id: str,
    distance_km: float,
    weight_kg: float,
    fuel_type: FuelType = FuelType.DIESEL,
    vehicle_type: str = "hgv"
) -> ShipmentEmissions:
    """Quick calculation for road transport."""
    mode = TransportMode.ROAD_HGV if vehicle_type == "hgv" else TransportMode.ROAD_LGV
    
    calculator = GLECCalculator()
    return calculator.calculate_shipment_emissions(
        shipment_id=shipment_id,
        transport_mode=mode,
        fuel_type=fuel_type,
        distance_km=distance_km,
        weight_kg=weight_kg
    )


def generate_shipment_carbon_label(
    emissions: ShipmentEmissions
) -> Dict[str, Any]:
    """Generate consumer-facing carbon label."""
    # Carbon intensity rating
    benchmarks = {
        TransportMode.ROAD_HGV: (0.040, 0.072, 0.100),
        TransportMode.RAIL: (0.008, 0.018, 0.025),
        TransportMode.SEA: (0.010, 0.020, 0.040)
    }
    
    mode_benchmarks = benchmarks.get(emissions.transport_mode, (0, 0, 0))
    
    if emissions.intensity <= mode_benchmarks[0]:
        rating = "A+"
        color = "#00C853"  # Green
    elif emissions.intensity <= mode_benchmarks[0] * 1.2:
        rating = "A"
        color = "#64DD17"
    elif emissions.intensity <= mode_benchmarks[1]:
        rating = "B"
        color = "#FFD600"  # Yellow
    elif emissions.intensity <= mode_benchmarks[2]:
        rating = "C"
        color = "#FF6D00"  # Orange
    else:
        rating = "D"
        color = "#DD2C00"  # Red
    
    return {
        'shipment_id': emissions.shipment_id,
        'total_emissions_kg': round(emissions.wtw_emissions, 2),
        'per_kg_km_g': round(emissions.intensity, 4),
        'rating': rating,
        'rating_color': color,
        'comparison_text': f"{rating} rated - {'Below' if rating in ['A+', 'A'] else 'Above'} average for {emissions.transport_mode.value}",
        'methodology': f"GLEC {emissions.glec_version}"
    }
