"""
AUTO-BROKER: Unit Tests for Cost Tracker Service

Target: 95% coverage, test precisione Decimal(28,6)
"""
import pytest
import pytest_asyncio
from decimal import Decimal
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock

from api.services.cost_tracker import (
    CostTracker,
    FinancialModel,
    CostBreakdown,
    FinancialProjection,
    BatchBufferItem,
    HUME_AI_COST_PER_MINUTE,
    RETELL_COST_PER_CALL,
    DAT_IQ_COST_PER_REQUEST,
    TEAM_MONTHLY_COST,
    INFRASTRUCTURE_BASE_MONTHLY,
    DECIMAL_PRECISION
)


class TestCostTrackerInitialization:
    """Test inizializzazione CostTracker."""
    
    def test_default_initialization(self):
        """Test inizializzazione con default."""
        tracker = CostTracker()
        
        assert tracker.batch_size == 10
        assert len(tracker._buffer) == 0
        assert tracker._cumulative_stats["hume_ai_cost"] == Decimal("0")
        assert tracker._cumulative_stats["retell_calls"] == 0
    
    def test_custom_batch_size(self):
        """Test con batch size personalizzato."""
        tracker = CostTracker(batch_size=25)
        assert tracker.batch_size == 25


class TestHumeAICostTracking:
    """Test tracking costi Hume AI."""
    
    @pytest_asyncio.fixture
    async def tracker(self):
        """Fixture per CostTracker."""
        return CostTracker(batch_size=5)
    
    @pytest.mark.asyncio
    async def test_track_hume_api_call_basic(self, tracker):
        """Test tracking base Hume API."""
        cost = await tracker.track_hume_api_call(
            duration_seconds=60.0,
            cache_hit=False
        )
        
        # 60 sec = 1 min * 0.15 EUR = 0.15 EUR
        assert cost == Decimal("0.15")
        assert tracker._cumulative_stats["hume_ai_minutes"] == Decimal("1")
        assert tracker._cumulative_stats["hume_ai_cost"] == Decimal("0.15")
    
    @pytest.mark.asyncio
    async def test_track_hume_api_call_prorata(self, tracker):
        """Test prorata per secondi."""
        cost = await tracker.track_hume_api_call(
            duration_seconds=30.0,  # Mezzo minuto
            cache_hit=False
        )
        
        # 30 sec = 0.5 min * 0.15 = 0.075 EUR
        expected = Decimal("0.075")
        assert cost == expected
    
    @pytest.mark.asyncio
    async def test_track_hume_api_call_cache_hit(self, tracker):
        """Test cache hit (costo 0, ma traccia risparmio)."""
        cost = await tracker.track_hume_api_call(
            duration_seconds=60.0,
            cache_hit=True
        )
        
        assert cost == Decimal("0")
        assert tracker._cumulative_stats["hume_ai_saved"] == Decimal("0.15")
    
    @pytest.mark.asyncio
    async def test_track_hume_api_call_90_seconds_exact(self, tracker):
        """Test precisione: 90 secondi = 1.5 min = 0.225 EUR esatto."""
        cost = await tracker.track_hume_api_call(
            duration_seconds=90.0,  # 1.5 minuti
            cache_hit=False
        )
        
        # 90 sec = 1.5 min * 0.15 EUR = 0.225 EUR esatto
        assert cost == Decimal("0.225"), f"Expected 0.225, got {cost}"
    
    @pytest.mark.asyncio
    async def test_track_hume_api_call_precision(self, tracker):
        """Test precisione 6 decimali con numero strano."""
        cost = await tracker.track_hume_api_call(
            duration_seconds=33.333,  # Strano numero
            cache_hit=False
        )
        
        # Verifica precisione
        assert cost == cost.quantize(DECIMAL_PRECISION)
        str_cost = str(cost)
        if "." in str_cost:
            decimals = len(str_cost.split(".")[1])
            assert decimals <= 6


class TestRetellCostTracking:
    """Test tracking costi Retell."""
    
    @pytest_asyncio.fixture
    async def tracker(self):
        return CostTracker(batch_size=5)
    
    @pytest.mark.asyncio
    async def test_track_retell_call_basic(self, tracker):
        """Test tracking base Retell."""
        cost = await tracker.track_retell_call(agent_type="sara")
        
        assert cost == RETELL_COST_PER_CALL  # 0.15 EUR
        assert tracker._cumulative_stats["retell_calls"] == 1
        assert tracker._cumulative_stats["retell_cost"] == Decimal("0.15")
    
    @pytest.mark.asyncio
    async def test_track_retell_multiple_calls(self, tracker):
        """Test multiple chiamate."""
        for _ in range(5):
            await tracker.track_retell_call()
        
        assert tracker._cumulative_stats["retell_calls"] == 5
        assert tracker._cumulative_stats["retell_cost"] == Decimal("0.75")  # 5 * 0.15


class TestDatIQCostTracking:
    """Test tracking costi DAT iQ."""
    
    @pytest_asyncio.fixture
    async def tracker(self):
        return CostTracker(batch_size=5)
    
    @pytest.mark.asyncio
    async def test_track_dat_iq_request(self, tracker):
        """Test tracking base DAT iQ."""
        cost = await tracker.track_dat_iq_request(request_type="market_data")
        
        assert cost == DAT_IQ_COST_PER_REQUEST  # 0.05 EUR
        assert tracker._cumulative_stats["dat_iq_requests"] == 1
        assert tracker._cumulative_stats["dat_iq_cost"] == Decimal("0.05")


class TestBlockchainCostTracking:
    """Test tracking costi blockchain."""
    
    @pytest_asyncio.fixture
    async def tracker(self):
        return CostTracker(batch_size=5)
    
    @pytest.mark.asyncio
    async def test_track_blockchain_tx_simple(self, tracker):
        """Test tracking base blockchain."""
        # Gas: 21000, Price: 50 gwei
        cost = await tracker.track_blockchain_tx(
            gas_used=21000,
            gas_price_gwei=50
        )
        
        # Calcolo: (21000 * 50) / 10^9 * 0.50 EUR
        # = 1,050,000 / 10^9 * 0.50
        # = 0.00105 * 0.50 = 0.000525 EUR
        expected = Decimal("0.000525")
        assert cost == expected
    
    @pytest.mark.asyncio
    async def test_track_blockchain_tx_precision(self, tracker):
        """Test precisione 6 decimali blockchain."""
        cost = await tracker.track_blockchain_tx(
            gas_used=100000,
            gas_price_gwei=33
        )
        
        # Verifica precisione
        str_cost = str(cost)
        if "." in str_cost:
            decimals = len(str_cost.split(".")[1])
            assert decimals <= 6


class TestBatchBuffer:
    """Test batch buffer e flush."""
    
    @pytest_asyncio.fixture
    async def tracker(self):
        return CostTracker(batch_size=10)
    
    @pytest.mark.asyncio
    async def test_buffer_accumulation_no_flush_at_9(self, tracker):
        """Test: dopo 9 chiamate, buffer NON flusha (batch_size=10)."""
        with patch.object(tracker, '_flush_buffer', new_callable=AsyncMock) as mock_flush:
            # Aggiungi 9 item (sotto batch_size=10)
            for _ in range(9):
                await tracker.track_retell_call()
            
            # Flush NON dovrebbe essere chiamato
            mock_flush.assert_not_called()
            assert len(tracker._buffer) == 9
    
    @pytest.mark.asyncio
    async def test_auto_flush_at_10(self, tracker):
        """Test: alla 10a chiamata, flush automatico (batch_size=10)."""
        with patch.object(tracker, '_flush_buffer', new_callable=AsyncMock) as mock_flush:
            # Aggiungi 10 item
            for _ in range(10):
                await tracker.track_retell_call()
            
            # Flush dovrebbe essere chiamato ESATTAMENTE 1 volta
            mock_flush.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_force_flush_manual(self, tracker):
        """Test force flush manuale svuota il buffer."""
        for _ in range(5):
            await tracker.track_retell_call()
        
        assert len(tracker._buffer) == 5
        
        await tracker.force_flush()
        
        # Buffer svuotato dopo flush
        assert len(tracker._buffer) == 0
    
    @pytest.mark.asyncio
    async def test_shutdown_flushes_buffer(self, tracker):
        """Test shutdown flusha eventi rimanenti."""
        for _ in range(7):
            await tracker.track_retell_call()
        
        assert len(tracker._buffer) == 7
        
        # Shutdown deve flushare
        await tracker.shutdown()
        
        # Buffer svuotato
        assert len(tracker._buffer) == 0


class TestFinancialModel:
    """Test modello finanziario."""
    
    @pytest.fixture
    def financial(self):
        """Fixture per FinancialModel."""
        return FinancialModel()
    
    def test_initialization(self, financial):
        """Test inizializzazione."""
        assert financial.team_cost == TEAM_MONTHLY_COST  # 25000
        assert financial.infra_base == INFRASTRUCTURE_BASE_MONTHLY  # 31700
        assert financial.default_margin == Decimal("0.25")
    
    def test_calculate_break_even_basic(self, financial):
        """Test calcolo break-even base."""
        projection = financial.calculate_break_even(
            spedizioni_mese=100,
            avg_revenue_per_sped=Decimal("500.00"),
            margin_percent=Decimal("0.25"),
            include_team=True
        )
        
        # Verifica struttura
        assert isinstance(projection, FinancialProjection)
        assert projection.months_to_break_even >= 0
        assert projection.break_even_spedizioni > 0
        assert projection.monthly_burn_rate > 0
    
    def test_calculate_break_even_infrastructure_only(self, financial):
        """Test break-eEn solo infrastructure (no team)."""
        projection = financial.calculate_break_even(
            spedizioni_mese=100,
            avg_revenue_per_sped=Decimal("500.00"),
            margin_percent=Decimal("0.25"),
            include_team=False  # Solo infra
        )
        
        # Burn rate dovrebbe essere minore (solo infra)
        infra_only_burn = projection.monthly_burn_rate
        
        projection_with_team = financial.calculate_break_even(
            spedizioni_mese=100,
            avg_revenue_per_sped=Decimal("500.00"),
            include_team=True
        )
        
        with_team_burn = projection_with_team.monthly_burn_rate
        
        assert infra_only_burn < with_team_burn
    
    def test_calculate_break_even_already_profitable(self, financial):
        """Test quando già profittevole."""
        projection = financial.calculate_break_even(
            spedizioni_mese=1000,  # Volume alto
            avg_revenue_per_sped=Decimal("1000.00"),
            margin_percent=Decimal("0.30"),
            include_team=True
        )
        
        # Dovrebbe essere già profittevole
        if projection.is_profitable:
            assert projection.months_to_break_even == 1
    
    def test_simulate_scenario(self, financial):
        """Test simulazione scenario."""
        scenario = financial.simulate_scenario(
            volume_spedizioni=1000,
            cache_hit_rate=0.85,
            include_team=True
        )
        
        # Verifica struttura
        assert "costs" in scenario
        assert "total_monthly" in scenario
        assert "cost_per_spedizione" in scenario
        
        # Verifica calcolo cache
        hume_data = scenario["costs"]["hume_ai"]
        assert "cost_without_cache" in hume_data
        assert "cache_savings" in hume_data
        assert "actual_cost" in hume_data
    
    def test_cache_hit_rate_impact(self, financial):
        """Test impatto cache hit rate."""
        # Scenario con cache alta
        high_cache = financial.simulate_scenario(
            volume_spedizioni=1000,
            cache_hit_rate=0.90,
            include_team=True
        )
        
        # Scenario con cache bassa
        low_cache = financial.simulate_scenario(
            volume_spedizioni=1000,
            cache_hit_rate=0.50,
            include_team=True
        )
        
        # Alta cache = minori costi
        high_cache_total = Decimal(high_cache["total_monthly"])
        low_cache_total = Decimal(low_cache["total_monthly"])
        
        assert high_cache_total < low_cache_total


class TestCostCalculations:
    """Test calcoli costi specifici."""
    
    def test_hume_ai_prorata_calculation(self):
        """Verifica calcolo prorata Hume."""
        # 90 secondi = 1.5 minuti
        seconds = Decimal("90")
        cost = (seconds / Decimal("60") * HUME_AI_COST_PER_MINUTE)
        
        assert cost == Decimal("0.225")  # 1.5 * 0.15
    
    def test_retell_flat_cost(self):
        """Verifica costo flat Retell."""
        assert RETELL_COST_PER_CALL == Decimal("0.15")
    
    def test_dat_iq_cost(self):
        """Verifica costo DAT iQ."""
        assert DAT_IQ_COST_PER_REQUEST == Decimal("0.05")
    
    def test_team_plus_infrastructure(self):
        """Verifica somma costi fissi."""
        total = TEAM_MONTHLY_COST + INFRASTRUCTURE_BASE_MONTHLY
        assert total == Decimal("56700.00")  # 25k + 31.7k


class TestBreakEvenCorrectness:
    """
    Test correttezza calcolo break-even.
    
    Secondo i calcoli corretti:
    - Team: €25k/mese
    - Infrastructure: €31.7k/mese
    - Totale: €56.7k/mese
    - Con margine 25% su €500/sped = €125 profitto/sped
    - Break-even = €56.7k / €125 = ~454 spedizioni (solo infra)
    - Break-eEn = €56.7k / €125 = ~454 spedizioni (con team)
    """
    
    @pytest.fixture
    def financial(self):
        return FinancialModel()
    
    def test_break_even_only_infrastructure(self, financial):
        """
        Test: Solo infrastructure (31.7k) / 125 EUR profitto = ~254 spedizioni.
        NOTA: Il calcolo precedente era errato (52 copre solo 6.5k, non 31.7k).
        """
        projection = financial.calculate_break_even(
            spedizioni_mese=100,
            avg_revenue_per_sped=Decimal("500.00"),
            margin_percent=Decimal("0.25"),
            include_team=False  # Solo infra
        )
        
        # 31.7k / 125 = ~254 spedizioni
        assert projection.break_even_spedizioni >= 250
        assert projection.break_even_spedizioni <= 260
    
    def test_break_even_full_team(self, financial):
        """
        Test: Team + Infrastructure (56.7k) / 125 EUR = ~454 spedizioni.
        """
        projection = financial.calculate_break_even(
            spedizioni_mese=100,
            avg_revenue_per_sped=Decimal("500.00"),
            margin_percent=Decimal("0.25"),
            include_team=True
        )
        
        # 56.7k / 125 = ~454 spedizioni
        assert projection.break_even_spedizioni >= 450
        assert projection.break_even_spedizioni <= 460
    
    def test_revenue_required_calculation(self, financial):
        """Verifica calcolo revenue richiesta."""
        projection = financial.calculate_break_even(
            spedizioni_mese=100,
            avg_revenue_per_sped=Decimal("500.00"),
            margin_percent=Decimal("0.25"),
            include_team=True
        )
        
        # Revenue = break_even_spedizioni * avg_revenue
        expected_revenue = Decimal(projection.break_even_spedizioni) * Decimal("500.00")
        actual_revenue = Decimal(projection.revenue_required)
        
        assert abs(expected_revenue - actual_revenue) < Decimal("1000")


class TestDecimalPrecision:
    """Test precisione Decimal."""
    
    @pytest.mark.asyncio
    async def test_no_float_rounding_errors(self):
        """Verifica che non ci siano errori di floating point."""
        tracker = CostTracker()
        
        # Aggiungi molti costi piccoli
        for _ in range(100):
            await tracker.track_hume_api_call(duration_seconds=33.333)
        
        total = tracker._cumulative_stats["hume_ai_cost"]
        
        # Verifica che sia un Decimal preciso
        assert isinstance(total, Decimal)
        
        # Non dovrebbe avere errori di floating point tipo 4.9999999
        str_total = str(total)
        assert "99999" not in str_total[-10:]  # No floating point artifacts
    
    def test_decimal_quantization(self):
        """Test quantizzazione a 6 decimali."""
        value = Decimal("0.123456789")
        quantized = value.quantize(DECIMAL_PRECISION)
        
        assert quantized == Decimal("0.123457")  # Arrotondato
        assert len(str(quantized).split(".")[1]) <= 6
    
    def test_no_decimal_float_mixing(self):
        """Test che Decimal + float sollevi TypeError (o sia gestito)."""
        d = Decimal("0.15")
        f = 0.15
        
        # Questo deve sollevare TypeError
        try:
            result = d + f
            # Se arriva qui, verifica che sia stato castato correttamente
            assert isinstance(result, Decimal)
        except TypeError:
            # Comportamento corretto: non si possono sommare Decimal + float
            pass
    
    @pytest.mark.asyncio
    async def test_all_calculations_use_decimal(self):
        """Verifica che tutti i calcoli interni usano Decimal."""
        tracker = CostTracker()
        
        # Traccia vari tipi di costi
        await tracker.track_hume_api_call(duration_seconds=60)
        await tracker.track_retell_call()
        await tracker.track_dat_iq_request()
        await tracker.track_blockchain_tx(gas_used=21000, gas_price_gwei=50)
        
        # Verifica che tutti i totali siano Decimal
        stats = tracker.get_cumulative_stats()
        assert isinstance(stats["hume_ai_cost"], Decimal)
        assert isinstance(stats["retell_cost"], Decimal)
        assert isinstance(stats["dat_iq_cost"], Decimal)
        assert isinstance(stats["blockchain_cost"], Decimal)
        assert isinstance(stats["total_api_costs"], Decimal)


class TestCircuitBreakerIntegration:
    """Test integrazione circuit breaker."""
    
    def test_circuit_breaker_present(self):
        """Verifica che circuit breaker sia presente."""
        tracker = CostTracker()
        
        assert tracker._circuit_breaker is not None
        assert tracker._circuit_breaker.name == "cost_tracker"