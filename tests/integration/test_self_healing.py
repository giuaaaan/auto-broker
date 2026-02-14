"""
AUTO-BROKER: Integration Tests for Self-Healing Supply Chain

Testano:
1. PAOLO: Carrier failover atomico
2. GIULIA: Dispute resolution con AI analysis
3. Orchestrator: Coordinazione PAOLO + GIULIA
4. Atomicità: Rollback se blockchain fallisce
5. Circuit breaker: Fallback quando servizi down
"""
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from uuid import uuid4, UUID

from api.services.agents.paolo_service import (
    PaoloAgent,
    FailoverResult,
    RiskAssessment,
    get_paolo_agent
)
from api.services.agents.giulia_service import (
    GiuliaAgent,
    Resolution,
    ResolutionDecision,
    DisputeEvent,
    get_giulia_agent
)
from api.services.orchestrator_swarm import (
    SwarmOrchestrator,
    get_swarm_orchestrator
)


# ============== Fixtures ==============

@pytest_asyncio.fixture
async def paolo_agent():
    """Fixture per PAOLO agent isolato."""
    agent = PaoloAgent()
    yield agent
    await agent.stop_monitoring()


@pytest_asyncio.fixture
async def giulia_agent():
    """Fixture per GIULIA agent isolato."""
    agent = GiuliaAgent()
    yield agent


@pytest_asyncio.fixture
async def orchestrator():
    """Fixture per Swarm Orchestrator."""
    orch = SwarmOrchestrator()
    yield orch
    await orch.stop()


@pytest_asyncio.fixture
async def mock_shipment():
    """Mock shipment per test."""
    return {
        "id": uuid4(),
        "carrier_id": 1,
        "prezzo_vendita": 5000.0,
        "stato": "in_transit",
        "pod_hash": "QmTest123"
    }


# ============== PAOLO Agent Tests ==============

class TestPaoloAgent:
    """Test suite per PAOLO Carrier Failover Agent."""
    
    @pytest.mark.asyncio
    async def test_paolo_initialization(self, paolo_agent):
        """Test inizializzazione PAOLO."""
        assert paolo_agent.running is False
        assert len(paolo_agent._executed_failovers) == 0
    
    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, paolo_agent):
        """Test avvio e stop monitoring."""
        await paolo_agent.start_monitoring()
        assert paolo_agent.running is True
        
        await paolo_agent.stop_monitoring()
        assert paolo_agent.running is False
    
    @pytest.mark.asyncio
    async def test_calculate_risk_level(self, paolo_agent):
        """Test calcolo livello rischio."""
        assert paolo_agent._calculate_risk_level(95.0) == "low"
        assert paolo_agent._calculate_risk_level(85.0) == "medium"
        assert paolo_agent._calculate_risk_level(75.0) == "high"
        assert paolo_agent._calculate_risk_level(65.0) == "critical"
    
    @pytest.mark.asyncio
    async def test_find_alternative_carrier(self, paolo_agent):
        """Test ricerca carrier alternativo."""
        with patch("api.services.agents.paolo_service.get_db_session") as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
            
            # Mock shipment
            mock_shipment = MagicMock()
            mock_shipment.id = uuid4()
            mock_shipment.carrier_id = 1
            mock_session.get.return_value = mock_shipment
            
            # Mock carriers query
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [
                MagicMock(id=2, nome="Carrier B", on_time_rate=95.0, attivo=True),
                MagicMock(id=3, nome="Carrier C", on_time_rate=92.0, attivo=True),
            ]
            mock_session.execute.return_value = mock_result
            
            alternative = await paolo_agent.find_alternative_carrier(
                shipment_id=mock_shipment.id,
                exclude_carrier_id=1
            )
            
            assert alternative is not None
            assert alternative.carrier_id != 1
            assert alternative.on_time_rate >= 90.0
    
    @pytest.mark.asyncio
    async def test_execute_failover_idempotency(self, paolo_agent):
        """Test idempotenza failover."""
        shipment_id = uuid4()
        
        # Primo failover
        with patch.object(paolo_agent, '_update_database_for_failover', new_callable=AsyncMock):
            with patch.object(paolo_agent, '_update_blockchain_for_failover', new_callable=AsyncMock) as mock_bc:
                mock_bc.return_value = "0xabc123"
                
                result1 = await paolo_agent.execute_failover(
                    shipment_id=shipment_id,
                    reason="Test failover"
                )
                
                # Secondo tentativo (stesso shipment)
                result2 = await paolo_agent.execute_failover(
                    shipment_id=shipment_id,
                    reason="Test failover again"
                )
                
                assert result2.idempotent is True
                assert result2.success is True
    
    @pytest.mark.asyncio
    async def test_failover_human_approval_for_high_value(self, paolo_agent):
        """Test che failover alto valore richiede approvazione umana."""
        shipment_id = uuid4()
        
        with patch("api.services.agents.paolo_service.get_db_session") as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
            
            # Mock shipment con valore alto
            mock_shipment = MagicMock()
            mock_shipment.id = shipment_id
            mock_shipment.carrier_id = 1
            mock_shipment.prezzo_vendita = 50000.0  # > 10k limit
            mock_session.get.return_value = mock_shipment
            
            # Mock carrier
            mock_carrier = MagicMock()
            mock_carrier.id = 1
            mock_carrier.nome = "Carrier A"
            mock_session.get.return_value = mock_carrier
            
            result = await paolo_agent.execute_failover(
                shipment_id=shipment_id,
                reason="High value test"
            )
            
            assert result.success is False
            assert "Human approval required" in result.error_message


class TestFailoverAtomicity:
    """Test atomicità operazioni failover (Saga pattern)."""
    
    @pytest.mark.asyncio
    async def test_rollback_on_blockchain_failure(self, paolo_agent):
        """Test rollback DB quando blockchain fallisce."""
        shipment_id = uuid4()
        
        with patch("api.services.agents.paolo_service.get_db_session") as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
            
            # Mock shipment
            mock_shipment = MagicMock()
            mock_shipment.id = shipment_id
            mock_shipment.carrier_id = 1
            mock_shipment.prezzo_vendita = 5000.0
            mock_session.get.return_value = mock_shipment
            
            # Mock alternative carrier
            with patch.object(paolo_agent, 'find_alternative_carrier') as mock_alt:
                mock_alt.return_value = MagicMock(
                    carrier_id=2,
                    carrier_name="Carrier B",
                    on_time_rate=95.0
                )
                
                # Mock blockchain failure
                with patch.object(paolo_agent, '_update_blockchain_for_failover', new_callable=AsyncMock) as mock_bc:
                    with patch.object(paolo_agent, '_rollback_database_failover', new_callable=AsyncMock) as mock_rollback:
                        mock_bc.return_value = None  # Fallimento
                        
                        result = await paolo_agent.execute_failover(
                            shipment_id=shipment_id,
                            reason="Test rollback"
                        )
                        
                        assert result.success is False
                        # Rollback dovrebbe essere chiamato
                        mock_rollback.assert_called_once()


# ============== GIULIA Agent Tests ==============

class TestGiuliaAgent:
    """Test suite per GIULIA Dispute Resolution Agent."""
    
    @pytest.mark.asyncio
    async def test_giulia_initialization(self, giulia_agent):
        """Test inizializzazione GIULIA."""
        assert len(giulia_agent._resolutions) == 0
    
    @pytest.mark.asyncio
    async def test_gather_evidence(self, giulia_agent):
        """Test raccolta evidence."""
        shipment_id = uuid4()
        
        evidence = await giulia_agent._gather_evidence(shipment_id)
        
        assert evidence is not None
        assert hasattr(evidence, 'tracking_history')
        assert hasattr(evidence, 'signatures')
        assert hasattr(evidence, 'gps_data')
    
    @pytest.mark.asyncio
    async def test_analyze_signature_authenticity(self, giulia_agent):
        """Test analisi firma."""
        from api.services.agents.giulia_service import Evidence
        
        evidence = Evidence(
            pod_document_url="https://ipfs.io/ipfs/test",
            pod_ipfs_hash="QmTest",
            tracking_history=[],
            photos=[],
            signatures=[{"type": "consignee", "timestamp": "2024-01-15T18:45:00Z"}],
            gps_data=[]
        )
        
        with patch.object(giulia_agent, '_call_llm', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = 85.0
            
            score = await giulia_agent._analyze_signature_authenticity(evidence)
            
            assert 0 <= score <= 100
    
    @pytest.mark.asyncio
    async def test_verify_delivery_tracking(self, giulia_agent):
        """Test verifica tracking."""
        from api.services.agents.giulia_service import Evidence
        
        evidence = Evidence(
            pod_document_url=None,
            pod_ipfs_hash=None,
            tracking_history=[
                {"timestamp": "2024-01-15T10:00:00Z", "status": "picked_up"},
                {"timestamp": "2024-01-15T18:45:00Z", "status": "delivered"},
            ],
            photos=[],
            signatures=[],
            gps_data=[
                {"lat": 45.46, "lng": 9.19, "timestamp": "2024-01-15T10:00:00Z"},
            ]
        )
        
        dispute = DisputeEvent(
            dispute_id=uuid4(),
            shipment_id=uuid4(),
            initiator="0x123",
            reason="Not delivered",
            claimed_amount=1000.0,
            created_at=datetime.utcnow()
        )
        
        score = await giulia_agent._verify_delivery_tracking(evidence, dispute)
        
        assert 0 <= score <= 100
    
    @pytest.mark.asyncio
    async def test_make_decision_high_confidence(self, giulia_agent):
        """Test decisione con confidence alta."""
        from api.services.agents.giulia_service import AIAnalysisResult
        
        analysis = AIAnalysisResult(
            signature_authentic=90.0,
            delivery_verified=88.0,
            damage_visible=10.0,
            overall_confidence=90.0,
            reasoning="All checks passed",
            flags=[]
        )
        
        decision = giulia_agent._make_decision(analysis, claimed_amount=1000.0)
        
        assert decision in [
            ResolutionDecision.AUTO_RESOLVE_CARRIER_WINS,
            ResolutionDecision.AUTO_RESOLVE_CUSTOMER_WINS
        ]
    
    @pytest.mark.asyncio
    async def test_make_decision_human_escalation(self, giulia_agent):
        """Test escalation umana per confidence media."""
        from api.services.agents.giulia_service import AIAnalysisResult
        
        analysis = AIAnalysisResult(
            signature_authentic=60.0,
            delivery_verified=65.0,
            damage_visible=50.0,
            overall_confidence=60.0,
            reasoning="Uncertain",
            flags=["suspicious_signature"]
        )
        
        decision = giulia_agent._make_decision(analysis, claimed_amount=1000.0)
        
        assert decision == ResolutionDecision.ESCALATE_HUMAN
    
    @pytest.mark.asyncio
    async def test_make_decision_high_value(self, giulia_agent):
        """Test escalation umana per importo alto."""
        from api.services.agents.giulia_service import AIAnalysisResult
        
        analysis = AIAnalysisResult(
            signature_authentic=95.0,
            delivery_verified=95.0,
            damage_visible=0.0,
            overall_confidence=95.0,
            reasoning="All good",
            flags=[]
        )
        
        # Importo alto (> 5k EUR)
        decision = giulia_agent._make_decision(analysis, claimed_amount=10000.0)
        
        assert decision == ResolutionDecision.ESCALATE_HUMAN
    
    @pytest.mark.asyncio
    async def test_handle_dispute_fraud_detection(self, giulia_agent):
        """Test rilevamento frode in dispute."""
        dispute = DisputeEvent(
            dispute_id=uuid4(),
            shipment_id=uuid4(),
            initiator="0x123",
            reason="Fake signature",
            claimed_amount=5000.0,
            created_at=datetime.utcnow()
        )
        
        with patch.object(giulia_agent, '_gather_evidence', new_callable=AsyncMock):
            with patch.object(giulia_agent, '_analyze_evidence', new_callable=AsyncMock) as mock_analysis:
                with patch.object(giulia_agent, '_submit_to_blockchain', new_callable=AsyncMock) as mock_bc:
                    mock_bc.return_value = "0xabc123"
                    
                    # Simula analisi che rileva frode
                    mock_analysis.return_value = MagicMock(
                        signature_authentic=20.0,  # Molto basso = frode
                        delivery_verified=30.0,
                        damage_visible=0.0,
                        overall_confidence=25.0,
                        reasoning="Suspicious",
                        flags=["suspicious_signature"]
                    )
                    
                    with patch.object(giulia_agent, '_flag_carrier_fraud', new_callable=AsyncMock) as mock_flag:
                        result = await giulia_agent.handle_dispute_webhook(dispute)
                        
                        # Dovrebbe flaggare carrier
                        mock_flag.assert_called_once()


# ============== Orchestrator Tests ==============

class TestSwarmOrchestrator:
    """Test suite per Swarm Orchestrator."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self, orchestrator):
        """Test inizializzazione orchestratore."""
        assert orchestrator._running is False
        assert orchestrator._event_queue.qsize() == 0
    
    @pytest.mark.asyncio
    async def test_start_stop_orchestrator(self, orchestrator):
        """Test avvio e stop orchestratore."""
        await orchestrator.start()
        assert orchestrator._running is True
        
        await orchestrator.stop()
        assert orchestrator._running is False
    
    @pytest.mark.asyncio
    async def test_emit_and_process_event(self, orchestrator):
        """Test emissione e processing evento."""
        await orchestrator.start()
        
        await orchestrator.emit_event(
            event_type="test_event",
            source_agent="test",
            payload={"test": "data"}
        )
        
        # Attendi processing
        await asyncio.sleep(0.5)
        
        assert len(orchestrator._event_history) == 1
        assert orchestrator._event_history[0].event_type == "test_event"
    
    @pytest.mark.asyncio
    async def test_failover_triggers_investigation(self, orchestrator):
        """Test che failover ripetuti triggerano investigazione."""
        await orchestrator.start()
        
        # Simula 3 failover per stesso carrier
        for i in range(3):
            await orchestrator.emit_event(
                event_type="failover_executed",
                source_agent="paolo",
                payload={
                    "shipment_id": str(uuid4()),
                    "old_carrier_id": 1,
                    "success": True
                }
            )
        
        await asyncio.sleep(0.5)
        
        # Dovrebbe aver tracciato i failover
        assert orchestrator._carrier_failover_counts.get(1, 0) == 3
    
    @pytest.mark.asyncio
    async def test_fraud_triggers_blacklist(self, orchestrator):
        """Test che frode pattern triggera blacklist."""
        await orchestrator.start()
        
        with patch.object(orchestrator, 'blacklist_carrier', new_callable=AsyncMock) as mock_blacklist:
            # Simula 3 dispute sospette
            for i in range(3):
                await orchestrator.emit_event(
                    event_type="fraud_pattern_detected",
                    source_agent="giulia",
                    payload={
                        "carrier_id": 1,
                        "shipment_id": str(uuid4()),
                        "confidence": 90.0
                    }
                )
            
            await asyncio.sleep(0.5)
            
            # Dovrebbe chiamare blacklist
            mock_blacklist.assert_called_once()


# ============== End-to-End Tests ==============

class TestEndToEndSelfHealing:
    """Test end-to-end del sistema self-healing."""
    
    @pytest.mark.asyncio
    async def test_full_failover_flow(self):
        """Test flusso completo failover."""
        # Setup
        paolo = get_paolo_agent()
        
        shipment_id = uuid4()
        
        with patch("api.services.agents.paolo_service.get_db_session") as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
            
            # Mock shipment
            mock_shipment = MagicMock()
            mock_shipment.id = shipment_id
            mock_shipment.carrier_id = 1
            mock_shipment.prezzo_vendita = 3000.0
            mock_session.get.return_value = mock_shipment
            
            # Mock carriers
            mock_carrier = MagicMock()
            mock_carrier.id = 1
            mock_carrier.nome = "Old Carrier"
            mock_carrier.wallet_address = "0xOLD"
            
            # Esegui failover
            with patch.object(paolo, 'find_alternative_carrier') as mock_alt:
                mock_alt.return_value = MagicMock(
                    carrier_id=2,
                    carrier_name="New Carrier",
                    on_time_rate=95.0
                )
                
                with patch.object(paolo, '_update_blockchain_for_failover', new_callable=AsyncMock) as mock_bc:
                    mock_bc.return_value = "0xabc123"
                    
                    result = await paolo.execute_failover(
                        shipment_id=shipment_id,
                        reason="Test E2E"
                    )
                    
                    assert result.success is True
                    assert result.old_carrier_id == 1
                    assert result.new_carrier_id == 2
                    assert result.tx_hash is not None
    
    @pytest.mark.asyncio
    async def test_full_dispute_resolution_flow(self):
        """Test flusso completo dispute resolution."""
        giulia = get_giulia_agent()
        
        dispute = DisputeEvent(
            dispute_id=uuid4(),
            shipment_id=uuid4(),
            initiator="0x123",
            reason="Not delivered",
            claimed_amount=2000.0,
            created_at=datetime.utcnow()
        )
        
        with patch.object(giulia, '_gather_evidence', new_callable=AsyncMock) as mock_evidence:
            from api.services.agents.giulia_service import Evidence
            mock_evidence.return_value = Evidence(
                pod_document_url="ipfs://test",
                pod_ipfs_hash="QmTest",
                tracking_history=[{"status": "delivered"}],
                photos=[],
                signatures=[{"type": "consignee"}],
                gps_data=[]
            )
            
            with patch.object(giulia, '_analyze_evidence', new_callable=AsyncMock) as mock_analysis:
                from api.services.agents.giulia_service import AIAnalysisResult
                mock_analysis.return_value = AIAnalysisResult(
                    signature_authentic=90.0,
                    delivery_verified=95.0,
                    damage_visible=0.0,
                    overall_confidence=92.0,
                    reasoning="All good",
                    flags=[]
                )
                
                with patch.object(giulia, '_submit_to_blockchain', new_callable=AsyncMock) as mock_bc:
                    mock_bc.return_value = "0xdef456"
                    
                    resolution = await giulia.handle_dispute_webhook(dispute)
                    
                    assert resolution is not None
                    assert resolution.confidence == 92.0
                    assert resolution.carrier_wins is True
                    assert resolution.tx_hash is not None


# ============== Circuit Breaker Tests ==============

class TestCircuitBreaker:
    """Test circuit breaker per resilienza."""
    
    @pytest.mark.asyncio
    async def test_paolo_circuit_breaker(self, paolo_agent):
        """Test circuit breaker PAOLO."""
        # Simula 5 fallimenti
        paolo_agent._circuit_breaker_failures = 5
        
        # Circuit breaker dovrebbe essere aperto
        assert paolo_agent._circuit_breaker_failures >= paolo_agent._circuit_breaker_threshold


# ============== Performance Tests ==============

class TestPerformance:
    """Test performance sistema."""
    
    @pytest.mark.asyncio
    async def test_failover_execution_time(self, paolo_agent):
        """Test che failover è eseguito in tempi ragionevoli."""
        import time
        
        shipment_id = uuid4()
        
        start = time.time()
        
        with patch("api.services.agents.paolo_service.get_db_session") as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
            
            mock_shipment = MagicMock()
            mock_shipment.id = shipment_id
            mock_shipment.carrier_id = 1
            mock_shipment.prezzo_vendita = 3000.0
            mock_session.get.return_value = mock_shipment
            
            with patch.object(paolo_agent, 'find_alternative_carrier') as mock_alt:
                mock_alt.return_value = MagicMock(
                    carrier_id=2,
                    carrier_name="New Carrier",
                    on_time_rate=95.0
                )
                
                with patch.object(paolo_agent, '_update_blockchain_for_failover', new_callable=AsyncMock) as mock_bc:
                    mock_bc.return_value = "0xabc123"
                    
                    await paolo_agent.execute_failover(
                        shipment_id=shipment_id,
                        reason="Performance test"
                    )
        
        elapsed = time.time() - start
        
        # Dovrebbe completare in meno di 5 secondi (con mock)
        assert elapsed < 5.0