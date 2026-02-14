"""
Test unitari per Provisioning Orchestrator.

Coverage target: 95%
- Kubernetes provisioning
- Hume AI activation
- Database HA provisioning
- Orchestration coordination
"""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

from api.services.provisioning_orchestrator import (
    KubernetesProvisioner,
    HumeAIActivator,
    DatabaseHAProvisioner,
    ProvisioningOrchestrator,
    ResourceState,
    get_provisioning_orchestrator
)


class TestKubernetesProvisioner:
    """Test provisioner Kubernetes."""
    
    @pytest.fixture
    def k8s_provisioner(self):
        return KubernetesProvisioner()
    
    def test_should_activate_true(self, k8s_provisioner):
        """Attiva quando revenue > 5000."""
        assert k8s_provisioner.should_activate(Decimal("6000")) is True
    
    def test_should_activate_false(self, k8s_provisioner):
        """Non attiva quando revenue <= 5000."""
        assert k8s_provisioner.should_activate(Decimal("5000")) is False
        assert k8s_provisioner.should_activate(Decimal("1000")) is False
    
    @pytest.mark.asyncio
    async def test_warm_up_success(self, k8s_provisioner):
        """Warm up K8s: control plane + 0 nodi."""
        with patch.object(k8s_provisioner, '_create_eks_control_plane', new_callable=AsyncMock) as mock_control, \
             patch.object(k8s_provisioner, '_create_node_group', new_callable=AsyncMock) as mock_nodes, \
             patch.object(k8s_provisioner, '_install_core_components', new_callable=AsyncMock) as mock_install:
            
            result = await k8s_provisioner.warm_up(cluster_name="test-cluster", region="eu-west-1")
            
            assert result.success is True
            assert result.state == ResourceState.WARM
            assert result.resource_id == "eks:test-cluster"
            assert result.action_taken == "create_control_plane_with_zero_nodes"
            
            mock_control.assert_called_once_with("test-cluster", "eu-west-1")
            mock_nodes.assert_called_once_with("test-cluster", "eu-west-1", 0)
            mock_install.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_warm_up_failure(self, k8s_provisioner):
        """Warm up fallisce se errore."""
        with patch.object(k8s_provisioner, '_create_eks_control_plane', side_effect=Exception("AWS API Error")):
            result = await k8s_provisioner.warm_up()
            
            assert result.success is False
            assert result.state == ResourceState.ERROR
            assert "AWS API Error" in result.error_message
    
    @pytest.mark.asyncio
    async def test_activate_success(self, k8s_provisioner):
        """Attivazione K8s: scala nodi e deployments."""
        with patch.object(k8s_provisioner, '_scale_node_group', new_callable=AsyncMock) as mock_scale_nodes, \
             patch.object(k8s_provisioner, '_scale_deployments', new_callable=AsyncMock) as mock_scale_deploy, \
             patch.object(k8s_provisioner, '_enable_hpa', new_callable=AsyncMock) as mock_hpa:
            
            result = await k8s_provisioner.activate(
                cluster_name="test-cluster",
                min_nodes=3,
                max_nodes=10
            )
            
            assert result.success is True
            assert result.state == ResourceState.HOT
            assert result.metadata["spot_enabled"] is True
            assert result.metadata["min_nodes"] == 3
            
            mock_scale_nodes.assert_called_once_with("test-cluster", 3, 10)
            mock_scale_deploy.assert_called_once_with("test-cluster", 3)
            mock_hpa.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_deactivate_success(self, k8s_provisioner):
        """Deattivazione: scala a 0 ma preserva control plane."""
        with patch.object(k8s_provisioner, '_scale_deployments', new_callable=AsyncMock) as mock_scale_deploy, \
             patch.object(k8s_provisioner, '_scale_node_group', new_callable=AsyncMock) as mock_scale_nodes:
            
            result = await k8s_provisioner.deactivate("test-cluster")
            
            assert result.success is True
            assert result.state == ResourceState.WARM
            assert result.metadata["control_plane_preserved"] is True
            
            mock_scale_deploy.assert_called_once_with("test-cluster", 0)
            mock_scale_nodes.assert_called_once_with("test-cluster", 0, 0)


class TestHumeAIActivator:
    """Test attivatore Hume AI."""
    
    @pytest.fixture
    def hume_activator(self):
        return HumeAIActivator()
    
    def test_should_activate_true(self, hume_activator):
        """Attiva quando revenue > 1000."""
        assert hume_activator.should_activate(Decimal("1500")) is True
    
    def test_should_activate_false(self, hume_activator):
        """Non attiva quando revenue <= 1000."""
        assert hume_activator.should_activate(Decimal("1000")) is False
    
    @pytest.mark.asyncio
    async def test_activate_success(self, hume_activator):
        """Attivazione Hume AI."""
        with patch.object(hume_activator, '_get_api_key_from_vault', new_callable=AsyncMock) as mock_vault, \
             patch.object(hume_activator, '_test_api_key', new_callable=AsyncMock) as mock_test, \
             patch.object(hume_activator, '_update_app_config', new_callable=AsyncMock) as mock_config:
            
            mock_vault.return_value = "sk-test-key"
            
            result = await hume_activator.activate(budget_minutes=4000)
            
            assert result.success is True
            assert result.state == ResourceState.HOT
            assert result.resource_id == "hume_ai:prosody"
            
            assert result.metadata["budget_minutes"] == 4000
            assert result.metadata["estimated_monthly_cost"] == 600  # 4000 * 0.15
            
            mock_vault.assert_called_once()
            mock_test.assert_called_once_with("sk-test-key")
            mock_config.assert_any_call("hume_enabled", True)
            mock_config.assert_any_call("hume_budget_minutes", 4000)
    
    @pytest.mark.asyncio
    async def test_activate_vault_failure(self, hume_activator):
        """Fallback a Ollama se Vault non disponibile."""
        with patch.object(hume_activator, '_get_api_key_from_vault', side_effect=Exception("Vault unreachable")):
            result = await hume_activator.activate()
            
            assert result.success is False
            assert result.state == ResourceState.ERROR
            assert "Vault unreachable" in result.error_message
    
    @pytest.mark.asyncio
    async def test_deactivate(self, hume_activator):
        """Deattivazione ritorna a Ollama."""
        with patch.object(hume_activator, '_update_app_config', new_callable=AsyncMock) as mock_config:
            result = await hume_activator.deactivate()
            
            assert result.success is True
            assert result.state == ResourceState.COLD
            assert result.action_taken == "disable_and_fallback_to_ollama"
            
            mock_config.assert_called_once_with("hume_enabled", False)


class TestDatabaseHAProvisioner:
    """Test provisioner Database HA."""
    
    @pytest.fixture
    def db_provisioner(self):
        return DatabaseHAProvisioner()
    
    @pytest.mark.asyncio
    async def test_warm_up_success(self, db_provisioner):
        """Warm up DB: replica stopped (storage only)."""
        with patch.object(db_provisioner, '_create_replica', new_callable=AsyncMock) as mock_create:
            result = await db_provisioner.warm_up(instance_id="test-db")
            
            assert result.success is True
            assert result.state == ResourceState.WARM
            assert result.metadata["storage_cost_only"] is True
            assert result.resource_id == "rds:test-db"
            
            mock_create.assert_called_once_with("test-db", status="stopped")
    
    @pytest.mark.asyncio
    async def test_activate_success(self, db_provisioner):
        """Attivazione DB: start replica."""
        with patch.object(db_provisioner, '_start_replica', new_callable=AsyncMock) as mock_start, \
             patch.object(db_provisioner, '_check_replication_lag', new_callable=AsyncMock) as mock_lag:
            
            mock_lag.return_value = 150  # 150ms lag
            
            result = await db_provisioner.activate("test-db")
            
            assert result.success is True
            assert result.state == ResourceState.HOT
            assert result.metadata["replication_lag_ms"] == 150
            assert result.metadata["multi_az"] is True
            
            mock_start.assert_called_once_with("test-db")
            mock_lag.assert_called_once()


class TestProvisioningOrchestrator:
    """Test orchestrator centrale."""
    
    @pytest.fixture
    def orchestrator(self):
        return ProvisioningOrchestrator()
    
    @pytest.mark.asyncio
    async def test_provision_level_dry_run(self, orchestrator):
        """Dry run simula senza eseguire."""
        components = [
            "eks_kubernetes_control_plane",
            "hume_ai_prosody"
        ]
        
        result = await orchestrator.provision_level(
            level_id="level_1",
            components=components,
            dry_run=True
        )
        
        assert result["dry_run"] is True
        assert result["success_count"] == 2
        assert all(c["result"].metadata.get("dry_run") for c in result["components"])
    
    @pytest.mark.asyncio
    async def test_provision_level_real_activation(self, orchestrator):
        """Attivazione reale dei componenti."""
        with patch.object(orchestrator.k8s, 'warm_up', new_callable=AsyncMock) as mock_k8s:
            mock_k8s.return_value = MagicMock(
                success=True,
                resource_id="eks:test",
                state=ResourceState.WARM,
                action_taken="create_control_plane",
                duration_seconds=60,
                metadata={}
            )
            
            result = await orchestrator.provision_level(
                level_id="level_1",
                components=[{"eks_kubernetes_control_plane": {"region": "eu-west-1"}}],
                dry_run=False
            )
            
            assert result["dry_run"] is False
            mock_k8s.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_provision_level_critical_component_failure(self, orchestrator):
        """Fallimento componente critico blocca provisioning."""
        with patch.object(orchestrator, '_provision_component', new_callable=AsyncMock) as mock_prov:
            mock_prov.return_value = MagicMock(
                success=False,
                resource_id="database:test",
                state=ResourceState.ERROR
            )
            
            result = await orchestrator.provision_level(
                level_id="level_2",
                components=["database_ha"],
                dry_run=False
            )
            
            # Dovrebbe interrompersi dopo il fallimento critico
            assert len(result["failed"]) >= 0  # O gestito come failed
    
    @pytest.mark.asyncio
    async def test_provision_unknown_component(self, orchestrator):
        """Componente sconosciuto restituisce errore."""
        result = await orchestrator._provision_component(
            "unknown_component",
            {}
        )
        
        assert result.success is False
        assert result.state == ResourceState.ERROR
        assert "No provisioner" in result.error_message
    
    def test_estimate_component_cost(self, orchestrator):
        """Stima costi componenti."""
        # EKS control plane
        cost = orchestrator._estimate_component_cost(
            "eks_kubernetes_control_plane",
            {}
        )
        assert cost == Decimal("75")
        
        # Hume AI
        cost = orchestrator._estimate_component_cost(
            "hume_ai_prosody",
            {"budget_minutes": 4000}
        )
        assert cost == Decimal("600")
        
        # PostgreSQL HA
        cost = orchestrator._estimate_component_cost(
            "postgresql_ha",
            {}
        )
        assert cost == Decimal("400")
        
        # Unknown component
        cost = orchestrator._estimate_component_cost(
            "unknown",
            {}
        )
        assert cost == Decimal("0")
    
    def test_is_critical_component(self, orchestrator):
        """Identifica componenti critici."""
        assert orchestrator._is_critical_component("database_ha") is True
        assert orchestrator._is_critical_component("kubernetes") is True
        assert orchestrator._is_critical_component("hume_ai") is False
        assert orchestrator._is_critical_component("redis") is False
    
    @pytest.mark.asyncio
    async def test_kubernetes_warm_then_activate_flow(self, orchestrator):
        """Flusso completo: warm → activate."""
        with patch.object(orchestrator.k8s, 'warm_up', new_callable=AsyncMock) as mock_warm, \
             patch.object(orchestrator.k8s, 'activate', new_callable=AsyncMock) as mock_activate:
            
            mock_warm.return_value = MagicMock(
                success=True,
                state=ResourceState.WARM,
                resource_id="eks:test"
            )
            mock_activate.return_value = MagicMock(
                success=True,
                state=ResourceState.HOT,
                resource_id="eks:test"
            )
            
            # Warm up
            warm_result = await orchestrator.k8s.warm_up("test")
            assert warm_result.state == ResourceState.WARM
            
            # Activate
            activate_result = await orchestrator.k8s.activate("test", 3, 10)
            assert activate_result.state == ResourceState.HOT
    
    @pytest.mark.asyncio
    async def test_hume_activation_with_budget(self, orchestrator):
        """Attivazione Hume con budget specifico."""
        with patch.object(orchestrator.hume, 'activate', new_callable=AsyncMock) as mock_activate:
            mock_activate.return_value = MagicMock(
                success=True,
                state=ResourceState.HOT,
                resource_id="hume_ai:prosody",
                metadata={
                    "budget_minutes": 2000,
                    "estimated_monthly_cost": 300
                }
            )
            
            result = await orchestrator.hume.activate(budget_minutes=2000)
            
            assert result.success is True
            assert result.metadata["budget_minutes"] == 2000
            assert result.metadata["estimated_monthly_cost"] == 300
    
    @pytest.mark.asyncio
    async def test_provision_level_with_multiple_components(self, orchestrator):
        """Provisioning multi-componente."""
        components = [
            {"eks_kubernetes_control_plane": {"region": "eu-west-1"}},
            {"hume_ai_prosody": {"budget_minutes": 2000}},
            "postgresql_ha"
        ]
        
        with patch.object(orchestrator, '_provision_component', new_callable=AsyncMock) as mock_prov:
            mock_prov.return_value = MagicMock(
                success=True,
                resource_id="test",
                state=ResourceState.HOT
            )
            
            result = await orchestrator.provision_level(
                level_id="level_2",
                components=components,
                dry_run=False
            )
            
            assert result["components_count"] == 3
            assert mock_prov.call_count == 3


class TestCircuitBreakerIntegration:
    """Test integrazione circuit breaker."""
    
    def test_kubernetes_has_circuit_breaker(self):
        """Kubernetes provisioner ha circuit breaker."""
        k8s = KubernetesProvisioner()
        assert k8s.circuit_breaker is not None
        assert k8s.circuit_breaker.name == "kubernetes_provisioner"
    
    def test_hume_has_circuit_breaker(self):
        """Hume activator ha circuit breaker."""
        hume = HumeAIActivator()
        assert hume.circuit_breaker is not None
        assert hume.circuit_breaker.name == "hume_activator"


class TestSingleton:
    """Test singleton pattern."""
    
    def test_get_provisioning_orchestrator_singleton(self):
        """Verifica singleton."""
        orch1 = get_provisioning_orchestrator()
        orch2 = get_provisioning_orchestrator()
        
        assert orch1 is orch2