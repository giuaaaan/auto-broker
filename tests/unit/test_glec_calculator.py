"""
Unit tests for GLEC Framework Carbon Calculator
Tests ISO 14083-compliant emissions calculation
"""

import pytest
from datetime import datetime

from carbon.glec_calculator import (
    GLECCalculator,
    TransportMode,
    FuelType,
    ShipmentEmissions,
    calculate_road_emissions,
    generate_shipment_carbon_label
)


@pytest.fixture
def calculator():
    """GLEC calculator instance."""
    return GLECCalculator()


class TestGLECCalculator:
    """Test GLEC Framework calculator."""
    
    def test_calculate_road_diesel_emissions(self, calculator):
        """Test road transport emissions with diesel."""
        emissions = calculator.calculate_shipment_emissions(
            shipment_id="TEST001",
            transport_mode=TransportMode.ROAD_HGV,
            fuel_type=FuelType.DIESEL,
            distance_km=500,
            weight_kg=5000  # 5 tons
        )
        
        assert emissions.shipment_id == "TEST001"
        assert emissions.transport_mode == TransportMode.ROAD_HGV
        assert emissions.fuel_type == FuelType.DIESEL
        assert emissions.distance_km == 500
        assert emissions.weight_tons == 5.0
        
        # Check emission values are positive
        assert emissions.wtw_emissions > 0
        assert emissions.ttw_emissions > 0
        assert emissions.wtt_emissions > 0
        
        # WTW should be greater than TTW alone
        assert emissions.wtw_emissions > emissions.ttw_emissions
        
        # Intensity should be reasonable (kg CO2e per ton-km)
        assert 0.05 < emissions.intensity < 0.15
    
    def test_calculate_electric_emissions(self, calculator):
        """Test electric vehicle emissions (lower than diesel)."""
        diesel = calculator.calculate_shipment_emissions(
            shipment_id="TEST_DIESEL",
            transport_mode=TransportMode.ROAD_HGV,
            fuel_type=FuelType.DIESEL,
            distance_km=500,
            weight_kg=5000
        )
        
        electric = calculator.calculate_shipment_emissions(
            shipment_id="TEST_ELECTRIC",
            transport_mode=TransportMode.ROAD_HGV,
            fuel_type=FuelType.ELECTRIC,
            distance_km=500,
            weight_kg=5000
        )
        
        # Electric should have much lower TTW emissions
        assert electric.ttw_emissions < diesel.ttw_emissions
        
        # But WTT (electricity generation) still contributes
        assert electric.wtt_emissions > 0
    
    def test_calculate_rail_emissions(self, calculator):
        """Test rail transport emissions."""
        rail = calculator.calculate_shipment_emissions(
            shipment_id="TEST_RAIL",
            transport_mode=TransportMode.RAIL,
            fuel_type=FuelType.ELECTRIC,
            distance_km=500,
            weight_kg=5000
        )
        
        # Rail should be more efficient than road
        road = calculator.calculate_shipment_emissions(
            shipment_id="TEST_ROAD",
            transport_mode=TransportMode.ROAD_HGV,
            fuel_type=FuelType.DIESEL,
            distance_km=500,
            weight_kg=5000
        )
        
        assert rail.intensity < road.intensity
    
    def test_calculate_sea_emissions(self, calculator):
        """Test sea freight emissions."""
        sea = calculator.calculate_shipment_emissions(
            shipment_id="TEST_SEA",
            transport_mode=TransportMode.SEA,
            fuel_type=FuelType.DIESEL,
            distance_km=1000,
            weight_kg=10000
        )
        
        assert sea.transport_mode == TransportMode.SEA
        assert sea.wtw_emissions > 0
        # Sea should be most efficient per ton-km
        assert sea.intensity < 0.05
    
    def test_temperature_controlled_surcharge(self, calculator):
        """Test temperature controlled cargo has higher emissions."""
        normal = calculator.calculate_shipment_emissions(
            shipment_id="TEST_NORMAL",
            transport_mode=TransportMode.ROAD_HGV,
            fuel_type=FuelType.DIESEL,
            distance_km=500,
            weight_kg=5000,
            temperature_controlled=False
        )
        
        refrigerated = calculator.calculate_shipment_emissions(
            shipment_id="TEST_REEFER",
            transport_mode=TransportMode.ROAD_HGV,
            fuel_type=FuelType.DIESEL,
            distance_km=500,
            weight_kg=5000,
            temperature_controlled=True
        )
        
        # Reefer should have ~15% higher emissions
        assert refrigerated.wtw_emissions > normal.wtw_emissions
        assert refrigerated.wtw_emissions > normal.wtw_emissions * 1.1
    
    def test_empty_running_factor(self, calculator):
        """Test empty running increases emissions."""
        loaded = calculator.calculate_shipment_emissions(
            shipment_id="TEST_LOADED",
            transport_mode=TransportMode.ROAD_HGV,
            fuel_type=FuelType.DIESEL,
            distance_km=500,
            weight_kg=5000,
            empty_running_factor=1.0
        )
        
        empty = calculator.calculate_shipment_emissions(
            shipment_id="TEST_EMPTY",
            transport_mode=TransportMode.ROAD_HGV,
            fuel_type=FuelType.DIESEL,
            distance_km=500,
            weight_kg=5000,
            empty_running_factor=1.5  # 50% empty running
        )
        
        assert empty.intensity > loaded.intensity
    
    def test_uncertainty_range(self, calculator):
        """Test uncertainty range calculation."""
        emissions = calculator.calculate_shipment_emissions(
            shipment_id="TEST001",
            transport_mode=TransportMode.ROAD_HGV,
            fuel_type=FuelType.DIESEL,
            distance_km=500,
            weight_kg=5000
        )
        
        # Uncertainty bounds should surround point estimate
        assert emissions.uncertainty_low < emissions.wtw_emissions
        assert emissions.uncertainty_high > emissions.wtw_emissions
    
    def test_calculation_logging(self, calculator):
        """Test calculation is logged."""
        initial_count = len(calculator.calculation_log)
        
        calculator.calculate_shipment_emissions(
            shipment_id="TEST_LOG",
            transport_mode=TransportMode.ROAD_HGV,
            fuel_type=FuelType.DIESEL,
            distance_km=500,
            weight_kg=5000
        )
        
        assert len(calculator.calculation_log) == initial_count + 1
        last_entry = calculator.calculation_log[-1]
        assert last_entry['shipment_id'] == "TEST_LOG"
        assert last_entry['mode'] == 'road_hgv'


class TestMultiLegShipment:
    """Test multi-leg shipment calculations."""
    
    def test_calculate_multi_leg(self, calculator):
        """Test multi-leg shipment aggregation."""
        legs = [
            {
                'transport_mode': TransportMode.ROAD_HGV,
                'fuel_type': FuelType.DIESEL,
                'distance_km': 100,
                'weight_kg': 5000
            },
            {
                'transport_mode': TransportMode.RAIL,
                'fuel_type': FuelType.ELECTRIC,
                'distance_km': 400,
                'weight_kg': 5000
            },
            {
                'transport_mode': TransportMode.ROAD_HGV,
                'fuel_type': FuelType.DIESEL,
                'distance_km': 50,
                'weight_kg': 5000
            }
        ]
        
        result = calculator.calculate_multi_leg_shipment("MULTI001", legs)
        
        assert result['shipment_id'] == "MULTI001"
        assert result['num_legs'] == 3
        assert result['total_wtw_kg'] > 0
        assert result['total_ton_km'] > 0
        assert 'leg_emissions' in result
        assert len(result['leg_emissions']) == 3
    
    def test_multi_leg_with_empty_leg(self, calculator):
        """Test multi-leg with empty legs list."""
        result = calculator.calculate_multi_leg_shipment("EMPTY001", [])
        
        assert result['num_legs'] == 0
        assert result['total_wtw_kg'] == 0


class TestEmissionFactors:
    """Test emission factor retrieval."""
    
    def test_get_default_factors(self, calculator):
        """Test default emission factors are available."""
        factors = calculator.get_emission_factors(
            TransportMode.ROAD_HGV,
            FuelType.DIESEL
        )
        
        assert factors.wtw_total > 0
        assert factors.ttw_co2 > 0
        assert factors.wtt_co2 >= 0
    
    def test_get_missing_factors_fallback(self, calculator):
        """Test fallback for missing factor combinations."""
        # Try a combination that might not exist
        factors = calculator.get_emission_factors(
            TransportMode.AIR,
            FuelType.HYDROGEN  # Unlikely to have specific factors
        )
        
        # Should return some factors (fallback)
        assert factors.wtw_total > 0


class TestCSRDReporting:
    """Test CSRD report generation."""
    
    def test_generate_csrd_report(self, calculator):
        """Test CSRD report generation."""
        from datetime import date
        
        shipments = [
            calculator.calculate_shipment_emissions(
                shipment_id=f"SHP{i:03d}",
                transport_mode=TransportMode.ROAD_HGV,
                fuel_type=FuelType.DIESEL,
                distance_km=500,
                weight_kg=5000
            )
            for i in range(10)
        ]
        
        report = calculator.generate_csrd_report(
            entity_name="Test Company S.p.A.",
            reporting_period=date(2024, 12, 31),
            shipments=shipments
        )
        
        assert report.entity_name == "Test Company S.p.A."
        assert report.total_ton_km > 0
        assert report.total_emissions_tons_co2e > 0
        assert report.methodology == "GLEC Framework v3.0 / ISO 14083:2023"


class TestScenarioComparison:
    """Test emission scenario comparison."""
    
    def test_compare_scenarios(self, calculator):
        """Test comparing different transport scenarios."""
        base_scenario = {
            'shipment_id': 'BASE',
            'transport_mode': TransportMode.ROAD_HGV,
            'fuel_type': FuelType.DIESEL,
            'distance_km': 500,
            'weight_kg': 5000,
            'name': 'Road Diesel (Baseline)'
        }
        
        alternatives = [
            {
                'shipment_id': 'ALT1',
                'transport_mode': TransportMode.ROAD_HGV,
                'fuel_type': FuelType.ELECTRIC,
                'distance_km': 500,
                'weight_kg': 5000,
                'name': 'Road Electric'
            },
            {
                'shipment_id': 'ALT2',
                'transport_mode': TransportMode.RAIL,
                'fuel_type': FuelType.ELECTRIC,
                'distance_km': 500,
                'weight_kg': 5000,
                'name': 'Rail Electric'
            }
        ]
        
        result = calculator.compare_emissions_scenarios(
            "COMP001", base_scenario, alternatives
        )
        
        assert result['shipment_id'] == "COMP001"
        assert 'base_scenario' in result
        assert 'alternatives' in result
        assert len(result['alternatives']) == 2
        assert 'best_alternative' in result
        
        # Alternatives should show savings
        for alt in result['alternatives']:
            assert 'savings_kg' in alt
            assert 'savings_percent' in alt


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_calculate_road_emissions(self):
        """Test quick road emissions function."""
        emissions = calculate_road_emissions(
            shipment_id="QUICK001",
            distance_km=300,
            weight_kg=3000,
            fuel_type=FuelType.DIESEL,
            vehicle_type="hgv"
        )
        
        assert emissions.shipment_id == "QUICK001"
        assert emissions.distance_km == 300
        assert emissions.wtw_emissions > 0
    
    def test_generate_carbon_label(self):
        """Test carbon label generation."""
        calculator = GLECCalculator()
        emissions = calculator.calculate_shipment_emissions(
            shipment_id="LABEL001",
            transport_mode=TransportMode.ROAD_HGV,
            fuel_type=FuelType.DIESEL,
            distance_km=500,
            weight_kg=5000
        )
        
        label = generate_shipment_carbon_label(emissions)
        
        assert label['shipment_id'] == "LABEL001"
        assert 'total_emissions_kg' in label
        assert 'per_kg_km_g' in label
        assert 'rating' in label
        assert label['rating'] in ['A+', 'A', 'B', 'C', 'D']
        assert 'rating_color' in label
        assert 'comparison_text' in label


class TestBenchmarks:
    """Test benchmark functions."""
    
    def test_get_intensity_benchmarks(self, calculator):
        """Test intensity benchmark retrieval."""
        benchmarks = calculator.get_emission_intensity_benchmark(
            TransportMode.ROAD_HGV
        )
        
        assert 'best_in_class' in benchmarks
        assert 'market_average' in benchmarks
        assert 'worst_in_class' in benchmarks
        assert benchmarks['best_in_class'] < benchmarks['market_average']
        assert benchmarks['market_average'] < benchmarks['worst_in_class']


class TestExport:
    """Test export functionality."""
    
    def test_export_calculation_log_json(self, calculator):
        """Test JSON export of calculation log."""
        calculator.calculate_shipment_emissions(
            shipment_id="EXPORT001",
            transport_mode=TransportMode.ROAD_HGV,
            fuel_type=FuelType.DIESEL,
            distance_km=500,
            weight_kg=5000
        )
        
        log = calculator.export_calculation_log(format="json")
        assert isinstance(log, list)
        assert len(log) > 0
    
    def test_export_calculation_log_csv(self, calculator):
        """Test CSV export of calculation log."""
        calculator.calculate_shipment_emissions(
            shipment_id="EXPORT002",
            transport_mode=TransportMode.ROAD_HGV,
            fuel_type=FuelType.DIESEL,
            distance_km=500,
            weight_kg=5000
        )
        
        csv = calculator.export_calculation_log(format="csv")
        assert isinstance(csv, str)
        assert "shipment_id" in csv
        assert "EXPORT002" in csv
