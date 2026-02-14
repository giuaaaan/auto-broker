"""
Test unitari per Revenue Monitor Service.

Coverage target: 95%
- Revenue metrics calculation
- Economic level activation
- Pre-warming logic
- Simulation scenarios
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from api.services.revenue_monitor import (
    RevenueMonitorService,
    RevenueMetrics,
    EconomicLevel,
    ActivationTrigger,
    get_revenue_monitor
)


@pytest.fixture
def mock_config():
    """Configurazione YAML di test."""
    return {
        "revenue_thresholds": {
            "version": "1.0.0",
            "effective_date": "2024-01-01"
        },
        "level_0_survival": {
            "name": "Survival Mode",
            "revenue_range": {"min": 0, "max": 449},
            "max_monthly_burn": 450,
            "auto_enable": [],
            "disabled_components": ["kubernetes", "hume_ai", "tee_confidential"]
        },
        "level_1_bootstrap": {
            "name": "Bootstrap Mode",
            "revenue_range": {"min": 450, "max": 799},
            "max_monthly_burn": 800,
            "required_consecutive_months": 1,
            "auto_enable": [
                {"eks_kubernetes_control_plane": {"region": "eu-west-1"}}
            ],
            "active_components": ["eks_control_plane"],
            "disabled_components": ["hume_ai", "tee_confidential"]
        },
        "level_2_growth": {
            "name": "Growth Mode",
            "revenue_range": {"min": 800, "max": 2999},
            "max_monthly_burn": 3000,
            "required_consecutive_months": 2,
            "auto_enable": [
                "hume_ai_prosody",
                {"kubernetes_workers": {"min_nodes": 2}}
            ],
            "active_components": ["eks_control_plane", "hume_ai"],
            "disabled_components": ["tee_confidential"]
        },
        "level_3_scale": {
            "name": "Scale Mode",
            "revenue_range": {"min": 3000, "max": 9999},
            "max_monthly_burn": 10000,
            "required_consecutive_months": 2,
            "auto_enable": ["vault_ha", "dat_iq"]
        },
        "level_4_enterprise": {
            "name": "Enterprise Mode",
            "revenue_range": {"min": 10000},
            "max_monthly_burn": 35000,
            "required_consecutive_months": 3,
            "auto_enable": ["tee_confidential", "carrier_escrow_full"]
        }
    }


@pytest.fixture
def service(mock_config, tmp_path):
    """Service con config mockato."""
    import yaml
    config_file = tmp_path / "revenue_thresholds.yaml"
    with open(config_file, 'w') as f:
        yaml.dump(mock_config, f)
    
    service = RevenueMonitorService(config_path=str(config_file))
    service._config = mock_config
    service._config_loaded_at = datetime.utcnow()
    return service


class TestRevenueMetrics:
    """Test calcolo metriche revenue."""
    
    @pytest.mark.asyncio
    async def test_calculate_metrics_empty_database(self, service):
        """Calcolo con database vuoto."""
        with patch.object(service, '_calculate_revenue_metrics', new_callable=AsyncMock) as mock_calc:
            mock_calc.return_value = RevenueMetrics(
                mrr=Decimal("0"),
                arr=Decimal("0"),
                last_month_revenue=Decimal("0"),
                last_3_months_avg=Decimal("0"),
                last_6_months_avg=Decimal("0"),
                ytd_revenue=Decimal("0"),
                growth_rate_mom=Decimal("0"),
                growth_rate_qoq=Decimal("0"),
                projected_next_month=Decimal("0"),
                projected_3_months=Decimal("0"),
                projected_6_months=Decimal("0")
            )
            
            metrics = await service._calculate_revenue_metrics()
            
            assert metrics.mrr == Decimal("0")
            assert metrics.arr == Decimal("0")
    
    @pytest.mark.asyncio
    async def test_calculate_metrics_with_data(self, service):
        """Calcolo con dati reali."""
        metrics = RevenueMetrics(
            mrr=Decimal("5000"),
            arr=Decimal("60000"),
            last_month_revenue=Decimal("5000"),
            last_3_months_avg=Decimal("4500"),
            last_6_months_avg=Decimal("4000"),
            ytd_revenue=Decimal("25000"),
            growth_rate_mom=Decimal("0.11"),  # 11% growth
            growth_rate_qoq=Decimal("0.25"),
            projected_next_month=Decimal("5550"),
            projected_3_months=Decimal("16650"),
            projected_6_months=Decimal("33300")
        )
        
        assert metrics.mrr == Decimal("5000")
        assert metrics.arr == Decimal("60000")
        assert metrics.growth_rate_mom == Decimal("0.11")


class TestEconomicLevelActivation:
    """Test attivazione livelli economici."""
    
    @pytest.mark.asyncio
    async def test_evaluate_level_trigger_revenue_met(self, service):
        """Trigger quando revenue è nella soglia."""
        level_config = {
            "revenue_range": {"min": 450, "max": 799},
            "required_consecutive_months": 1
        }
        
        metrics = RevenueMetrics(
            mrr=Decimal("500"), arr=Decimal("6000"),
            last_month_revenue=Decimal("500"), last_3_months_avg=Decimal("500"),
            last_6_months_avg=Decimal("500"), ytd_revenue=Decimal("500"),
            growth_rate_mom=Decimal("0"), growth_rate_qoq=Decimal("0"),
            projected_next_month=Decimal("500"), projected_3_months=Decimal("1500"),
            projected_6_months=Decimal("3000")
        )
        
        with patch.object(service, '_count_consecutive_months_above', new_callable=AsyncMock) as mock_count:
            mock_count.return_value = 1  # Soddisfa required_consecutive_months
            
            trigger = await service._evaluate_level_trigger(
                level_id="level_1_bootstrap",
                level_config=level_config,
                current_mrr=Decimal("500"),
                metrics=metrics
            )
            
            assert trigger.triggered is True
            assert trigger.confidence == 1.0
            assert "500" in trigger.reason
    
    @pytest.mark.asyncio
    async def test_evaluate_level_trigger_debounce_logic(self, service):
        """Debounce: non attiva se mesi consecutivi insufficienti."""
        level_config = {
            "revenue_range": {"min": 800, "max": 2999},
            "required_consecutive_months": 2
        }
        
        metrics = RevenueMetrics(
            mrr=Decimal("1000"), arr=Decimal("12000"),
            last_month_revenue=Decimal("1000"), last_3_months_avg=Decimal("900"),
            last_6_months_avg=Decimal("850"), ytd_revenue=Decimal("3000"),
            growth_rate_mom=Decimal("0.11"), growth_rate_qoq=Decimal("0.20"),
            projected_next_month=Decimal("1100"), projected_3_months=Decimal("3300"),
            projected_6_months=Decimal("6600")
        )
        
        with patch.object(service, '_count_consecutive_months_above', new_callable=AsyncMock) as mock_count:
            mock_count.return_value = 1  # Solo 1 mese, ne servono 2
            
            trigger = await service._evaluate_level_trigger(
                level_id="level_2_growth",
                level_config=level_config,
                current_mrr=Decimal("1000"),
                metrics=metrics
            )
            
            assert trigger.triggered is False
            assert trigger.confidence == 0.5  # 1/2 mesi
            assert trigger.consecutive_months_met == 1
            assert trigger.recommended_date is not None
    
    @pytest.mark.asyncio
    async def test_evaluate_level_trigger_revenue_too_low(self, service):
        """Non attiva se revenue sotto soglia."""
        level_config = {
            "revenue_range": {"min": 10000},
            "required_consecutive_months": 3
        }
        
        metrics = RevenueMetrics(
            mrr=Decimal("5000"), arr=Decimal("60000"),
            last_month_revenue=Decimal("5000"), last_3_months_avg=Decimal("4500"),
            last_6_months_avg=Decimal("4000"), ytd_revenue=Decimal("25000"),
            growth_rate_mom=Decimal("0.10"), growth_rate_qoq=Decimal("0.20"),
            projected_next_month=Decimal("5500"), projected_3_months=Decimal("16500"),
            projected_6_months=Decimal("33000")
        )
        
        trigger = await service._evaluate_level_trigger(
            level_id="level_4_enterprise",
            level_config=level_config,
            current_mrr=Decimal("5000"),
            metrics=metrics
        )
        
        assert trigger.triggered is False
        assert trigger.confidence == 0.0
        assert "5000" in trigger.reason


class TestSafetyChecks:
    """Test sicurezza e controllo costi."""
    
    @pytest.mark.asyncio
    async def test_activation_blocked_cost_exceeds_90_percent(self, service):
        """Blocco attivazione se costo > 90% revenue."""
        with patch.object(service, '_get_config', new_callable=AsyncMock) as mock_config, \
             patch.object(service, '_calculate_revenue_metrics', new_callable=AsyncMock) as mock_metrics:
            
            mock_config.return_value = {
                "expensive_level": {
                    "revenue_range": {"min": 1000},
                    "max_monthly_burn": 2000,  # > 90% di 1000
                    "auto_enable": ["expensive_component"]
                }
            }
            
            mock_metrics.return_value = RevenueMetrics(
                mrr=Decimal("1000"), arr=Decimal("12000"),
                last_month_revenue=Decimal("1000"), last_3_months_avg=Decimal("1000"),
                last_6_months_avg=Decimal("1000"), ytd_revenue=Decimal("5000"),
                growth_rate_mom=Decimal("0"), growth_rate_qoq=Decimal("0"),
                projected_next_month=Decimal("1000"), projected_3_months=Decimal("3000"),
                projected_6_months=Decimal("6000")
            )
            
            result = await service.activate_level("expensive_level", dry_run=False)
            
            assert result["success"] is False
            assert "exceeds 90%" in result["error"]
            assert result["requires_manual_override"] is True
    
    @pytest.mark.asyncio
    async def test_activation_allowed_within_budget(self, service):
        """Attivazione ok se costo <= 90% revenue."""
        with patch.object(service, '_get_config', new_callable=AsyncMock) as mock_config, \
             patch.object(service, '_calculate_revenue_metrics', new_callable=AsyncMock) as mock_metrics, \
             patch.object(service, '_activate_component', new_callable=AsyncMock) as mock_activate:
            
            mock_config.return_value = {
                "level_1": {
                    "name": "Level 1",
                    "revenue_range": {"min": 500},
                    "max_monthly_burn": 400,  # < 90% di 500 (450)
                    "auto_enable": [{"component_a": {}}]
                }
            }
            
            mock_metrics.return_value = RevenueMetrics(
                mrr=Decimal("500"), arr=Decimal("6000"),
                last_month_revenue=Decimal("500"), last_3_months_avg=Decimal("500"),
                last_6_months_avg=Decimal("500"), ytd_revenue=Decimal("2000"),
                growth_rate_mom=Decimal("0"), growth_rate_qoq=Decimal("0"),
                projected_next_month=Decimal("500"), projected_3_months=Decimal("1500"),
                projected_6_months=Decimal("3000")
            )
            
            mock_activate.return_value = {"name": "component_a", "status": "activated"}
            
            result = await service.activate_level("level_1", dry_run=False)
            
            assert result["success"] is True
            assert result["components_count"] == 1


class TestSimulation:
    """Test simulazione scenari."""
    
    @pytest.mark.asyncio
    async def test_simulate_revenue_level_1(self, service):
        """Simula attivazione livello 1."""
        with patch.object(service, '_get_config', new_callable=AsyncMock) as mock_config:
            mock_config.return_value = {
                "level_0_survival": {"revenue_range": {"min": 0, "max": 449}},
                "level_1_bootstrap": {"revenue_range": {"min": 450, "max": 799}},
                "level_2_growth": {"revenue_range": {"min": 800, "max": 2999}},
                "level_3_scale": {"revenue_range": {"min": 3000, "max": 9999}},
                "level_4_enterprise": {"revenue_range": {"min": 10000}}
            }
            
            scenario = await service.simulate_revenue(Decimal("600"))
            
            assert scenario["simulated_revenue"] == "600"
            assert scenario["simulated_level"] == "level_1_bootstrap"
            assert len(scenario["triggers"]) >= 1
    
    @pytest.mark.asyncio
    async def test_simulate_revenue_level_4(self, service):
        """Simula attivazione livello enterprise."""
        with patch.object(service, '_get_config', new_callable=AsyncMock) as mock_config:
            mock_config.return_value = {
                "level_0_survival": {"revenue_range": {"min": 0, "max": 449}},
                "level_1_bootstrap": {"revenue_range": {"min": 450, "max": 799}},
                "level_2_growth": {"revenue_range": {"min": 800, "max": 2999}},
                "level_3_scale": {"revenue_range": {"min": 3000, "max": 9999}},
                "level_4_enterprise": {"revenue_range": {"min": 10000}}
            }
            
            scenario = await service.simulate_revenue(Decimal("15000"))
            
            assert scenario["simulated_revenue"] == "15000"
            assert scenario["simulated_level"] == "level_4_enterprise"
    
    @pytest.mark.asyncio
    async def test_simulate_does_not_affect_real_state(self, service):
        """Simulazione non cambia stato reale."""
        with patch.object(service, '_get_config', new_callable=AsyncMock) as mock_config:
            mock_config.return_value = {
                "level_0_survival": {"revenue_range": {"min": 0, "max": 449}},
                "level_1_bootstrap": {"revenue_range": {"min": 450, "max": 799}},
            }
            
            original_level = service._current_level
            
            await service.simulate_revenue(Decimal("1000000"))
            
            # Stato non deve cambiare
            assert service._current_level == original_level


class TestDryRun:
    """Test modalità dry run."""
    
    @pytest.mark.asyncio
    async def test_activate_level_dry_run(self, service):
        """Dry run non attiva componenti reali."""
        with patch.object(service, '_get_config', new_callable=AsyncMock) as mock_config, \
             patch.object(service, '_calculate_revenue_metrics', new_callable=AsyncMock) as mock_metrics:
            
            mock_config.return_value = {
                "level_1": {
                    "name": "Test Level",
                    "max_monthly_burn": 500,
                    "auto_enable": [
                        {"component_a": {"setting": "value"}}
                    ]
                }
            }
            
            mock_metrics.return_value = RevenueMetrics(
                mrr=Decimal("1000"), arr=Decimal("12000"),
                last_month_revenue=Decimal("1000"), last_3_months_avg=Decimal("1000"),
                last_6_months_avg=Decimal("1000"), ytd_revenue=Decimal("5000"),
                growth_rate_mom=Decimal("0"), growth_rate_qoq=Decimal("0"),
                projected_next_month=Decimal("1000"), projected_3_months=Decimal("3000"),
                projected_6_months=Decimal("6000")
            )
            
            result = await service.activate_level("level_1", dry_run=True)
            
            assert result["dry_run"] is True
            assert result["success"] is True
            assert result["components"][0]["status"] == "simulated"


class TestPreWarming:
    """Test pre-warming risorse."""
    
    @pytest.mark.asyncio
    async def test_pre_warm_kubernetes_control_plane(self, service):
        """Pre-riscalda K8s control plane."""
        with patch.object(service, '_get_config', new_callable=AsyncMock) as mock_config:
            mock_config.return_value = {
                "pre_warming": {
                    "strategies": {
                        "kubernetes": {
                            "action": "create_cluster_control_plane",
                            "cost_monthly": 75
                        }
                    }
                }
            }
            
            with patch.object(service, '_pre_warm_kubernetes_control_plane', new_callable=AsyncMock) as mock_warm:
                result = await service.pre_warm_resources("level_1_bootstrap")
                
                mock_warm.assert_called_once()
                assert "kubernetes" in result["pre_warmed"]


class TestMonitoringLoop:
    """Test loop monitoraggio."""
    
    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, service):
        """Avvia e ferma monitoring."""
        with patch.object(service, 'check_activation_triggers', new_callable=AsyncMock):
            await service.start_monitoring(interval_minutes=0.1)  # 6 secondi
            
            assert service._running is True
            assert service._monitor_task is not None
            
            await service.stop_monitoring()
            
            assert service._running is False
    
    @pytest.mark.asyncio
    async def test_monitoring_task_cancellation(self, service):
        """Cancellazione task monitoring."""
        with patch.object(service, 'check_activation_triggers', new_callable=AsyncMock) as mock_check:
            mock_check.side_effect = asyncio.CancelledError()
            
            await service.start_monitoring(interval_minutes=0.1)
            
            # Attendi che il task parta
            await asyncio.sleep(0.1)
            
            await service.stop_monitoring()


class TestSingleton:
    """Test singleton pattern."""
    
    def test_get_revenue_monitor_singleton(self):
        """Verifica singleton restituisce stessa istanza."""
        service1 = get_revenue_monitor()
        service2 = get_revenue_monitor()
        
        assert service1 is service2


# Import per asyncio.CancelledError
import asyncio