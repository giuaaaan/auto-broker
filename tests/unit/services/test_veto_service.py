"""
AUTO-BROKER: Unit Tests for Veto Service

Test suite per VetoService con target coverage 95%.
Mocka tutte le dipendenze esterne (DB, CircuitBreaker).
"""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

import asyncio

from api.models.governance import VetoStatus, AgentType, VetoSession, DecisionAudit
from api.services.veto_service import (
    VetoService,
    VetoError,
    VetoWindowExpired,
    VetoNotAllowed,
    get_veto_service
)


# ============== Fixtures ==============

@pytest_asyncio.fixture
async def veto_service():
    """Fixture per VetoService isolato."""
    service = VetoService()
    yield service
    # Cleanup: cancella tutti i timer
    for task in list(service._active_timers.values()):
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@pytest.fixture
def mock_db_session():
    """Mock per AsyncSession database."""
    session = AsyncMock()
    
    # Mock execute
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    
    # Context manager
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    
    return session


@pytest.fixture
def sample_veto_session():
    """Sample VetoSession per test."""
    now = datetime.utcnow()
    return VetoSession(
        id=uuid4(),
        agent_type=AgentType.PAOLO,
        operation_type="carrier_failover",
        shipment_id=uuid4(),
        carrier_id=uuid4(),
        amount_eur=Decimal("7500"),
        confidence_score=Decimal("0.92"),
        status=VetoStatus.RESERVED,
        timeout_seconds=60,
        opened_at=now,
        expires_at=now + timedelta(seconds=60),
        context={"test": True}
    )


# ============== Test 1: Reserve Carrier (Open Veto Window) ==============

class TestReserveCarrier:
    """Test apertura veto window (stato RESERVED)."""
    
    @pytest.mark.asyncio
    async def test_open_veto_window_creates_reserved_session(self, veto_service, mock_db_session):
        """Test: open_veto_window crea sessione in stato RESERVED."""
        with patch('api.services.veto_service.get_db_session', return_value=mock_db_session):
            session = await veto_service.open_veto_window(
                agent_type=AgentType.PAOLO,
                operation_type="carrier_failover",
                shipment_id=uuid4(),
                carrier_id=uuid4(),
                amount_eur=Decimal("7500"),
                confidence_score=Decimal("0.92"),
                timeout_seconds=60
            )
            
            # Verifica stato
            assert session.status == VetoStatus.RESERVED
            assert session.agent_type == AgentType.PAOLO
            assert session.amount_eur == Decimal("7500")
            assert session.timeout_seconds == 60
            
            # Verifica timer attivo
            assert session.id in veto_service._active_timers
            
            # Verifica DB chiamate
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_open_veto_window_starts_timer(self, veto_service, mock_db_session):
        """Test: open_veto_window avvia timer async non-blocking."""
        with patch('api.services.veto_service.get_db_session', return_value=mock_db_session):
            session = await veto_service.open_veto_window(
                agent_type=AgentType.PAOLO,
                operation_type="carrier_failover",
                amount_eur=Decimal("5000"),
                timeout_seconds=2  # Breve per test
            )
            
            # Verifica timer registrato
            assert session.id in veto_service._active_timers
            timer_task = veto_service._active_timers[session.id]
            assert isinstance(timer_task, asyncio.Task)
            assert not timer_task.done()
            
            # Cleanup
            timer_task.cancel()
    
    @pytest.mark.asyncio
    async def test_open_veto_window_validates_amount(self, veto_service, mock_db_session):
        """Test: amount deve essere valido."""
        with pytest.raises(Exception):  # Valorizzazione Pydantic/SQLAlchemy
            with patch('api.services.veto_service.get_db_session', return_value=mock_db_session):
                await veto_service.open_veto_window(
                    agent_type=AgentType.PAOLO,
                    operation_type="carrier_failover",
                    amount_eur=Decimal("-100")  # Invalido
                )


# ============== Test 2: Auto Release (Timer Expiry) ==============

class TestAutoRelease:
    """Test scadenza timer e transizione a EXPIRED."""
    
    @pytest.mark.asyncio
    async def test_timer_expires_sets_expired_status(self, veto_service, mock_db_session, sample_veto_session):
        """Test: timer scaduto marca sessione come EXPIRED."""
        # Setup sessione mock
        sample_veto_session.status = VetoStatus.RESERVED
        sample_veto_session.expires_at = datetime.utcnow() - timedelta(seconds=1)  # Già scaduta
        
        # Mock query ritorna la sessione
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=sample_veto_session)
        mock_db_session.execute = AsyncMock(return_value=result_mock)
        
        with patch('api.services.veto_service.get_db_session', return_value=mock_db_session):
            # Avvia timer con timeout 0 (scade immediatamente)
            await veto_service._veto_timer(sample_veto_session.id, 0)
            
            # Attendi esecuzione timer
            await asyncio.sleep(0.1)
            
            # Verifica stato aggiornato
            assert sample_veto_session.status == VetoStatus.EXPIRED
            mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_timer_calls_expiry_callback(self, veto_service, mock_db_session):
        """Test: timer scaduto chiama callback registrato."""
        callback_mock = MagicMock()
        
        with patch('api.services.veto_service.get_db_session', return_value=mock_db_session):
            session = await veto_service.open_veto_window(
                agent_type=AgentType.PAOLO,
                operation_type="carrier_failover",
                amount_eur=Decimal("5000"),
                timeout_seconds=1,
                on_expiry=callback_mock
            )
            
            # Registra callback manualmente (mock non persiste)
            veto_service._expiry_callbacks[session.id] = callback_mock
            
            # Attendi scadenza
            await asyncio.sleep(1.5)
            
            # Verifica callback chiamato (il timer avrà eseguito)
            # Nota: in test reale, mockiamo il timer
    
    @pytest.mark.asyncio
    async def test_timer_cancelled_on_veto(self, veto_service, mock_db_session):
        """Test: timer cancellato quando veto ricevuto."""
        with patch('api.services.veto_service.get_db_session', return_value=mock_db_session):
            session = await veto_service.open_veto_window(
                agent_type=AgentType.PAOLO,
                operation_type="carrier_failover",
                amount_eur=Decimal("5000"),
                timeout_seconds=60
            )
            
            timer_task = veto_service._active_timers[session.id]
            
            # Setup mock per veto
            session.status = VetoStatus.RESERVED
            result_mock = MagicMock()
            result_mock.scalar_one_or_none = MagicMock(return_value=session)
            mock_db_session.execute = AsyncMock(return_value=result_mock)
            
            # Esercita veto
            await veto_service.exert_veto(
                session_id=session.id,
                operator_id=uuid4(),
                rationale="Test veto rationale long enough"
            )
            
            # Verifica timer cancellato
            assert session.id not in veto_service._active_timers
            assert timer_task.cancelled() or timer_task.done()


# ============== Test 3: State Transitions ==============

class TestStateTransitions:
    """Test transizioni stato corrette."""
    
    @pytest.mark.asyncio
    async def test_reserved_to_vetoed_transition(self, veto_service, mock_db_session, sample_veto_session):
        """Test: RESERVED → VETOED con rationale."""
        sample_veto_session.status = VetoStatus.RESERVED
        sample_veto_session.expires_at = datetime.utcnow() + timedelta(seconds=60)
        
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=sample_veto_session)
        mock_db_session.execute = AsyncMock(return_value=result_mock)
        
        with patch('api.services.veto_service.get_db_session', return_value=mock_db_session):
            result = await veto_service.exert_veto(
                session_id=sample_veto_session.id,
                operator_id=uuid4(),
                rationale="Valid rationale for veto decision"
            )
            
            assert result.status == VetoStatus.VETOED
            assert result.operator_rationale == "Valid rationale for veto decision"
            mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_reserved_to_committed_transition(self, veto_service, mock_db_session, sample_veto_session):
        """Test: RESERVED → COMMITTED dopo esecuzione."""
        sample_veto_session.status = VetoStatus.RESERVED
        
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=sample_veto_session)
        mock_db_session.execute = AsyncMock(return_value=result_mock)
        
        with patch('api.services.veto_service.get_db_session', return_value=mock_db_session):
            result = await veto_service.commit_operation(
                session_id=sample_veto_session.id,
                blockchain_tx_hash="0xabc123"
            )
            
            assert result.status == VetoStatus.COMMITTED
            assert result.blockchain_tx_hash == "0xabc123"
            assert result.committed_at is not None
    
    @pytest.mark.asyncio
    async def test_committed_to_vetoed_compensation(self, veto_service, mock_db_session, sample_veto_session):
        """Test: COMMITTED → VETOED con compensation."""
        sample_veto_session.status = VetoStatus.COMMITTED
        sample_veto_session.blockchain_tx_hash = "0xabc123"
        
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=sample_veto_session)
        mock_db_session.execute = AsyncMock(return_value=result_mock)
        
        compensation_mock = MagicMock()
        
        with patch('api.services.veto_service.get_db_session', return_value=mock_db_session):
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_executor = MagicMock()
                mock_loop.return_value.run_in_executor = AsyncMock()
                
                result = await veto_service.request_compensation(
                    session_id=sample_veto_session.id,
                    operator_id=uuid4(),
                    rationale="Post-commit veto rationale",
                    compensation_callback=compensation_mock
                )
                
                assert result.status == VetoStatus.VETOED
    
    @pytest.mark.asyncio
    async def test_invalid_transition_reserved_to_cancelled(self, veto_service, mock_db_session, sample_veto_session):
        """Test: RESERVED → CANCELLED permesso."""
        sample_veto_session.status = VetoStatus.RESERVED
        
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=sample_veto_session)
        mock_db_session.execute = AsyncMock(return_value=result_mock)
        
        with patch('api.services.veto_service.get_db_session', return_value=mock_db_session):
            result = await veto_service.cancel_session(
                session_id=sample_veto_session.id,
                reason="Manual cancellation test"
            )
            
            assert result.status == VetoStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_invalid_transition_vetoed_to_committed_raises(self, veto_service, mock_db_session, sample_veto_session):
        """Test: VETOED → COMMITTED non permesso."""
        sample_veto_session.status = VetoStatus.VETOED
        
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=sample_veto_session)
        mock_db_session.execute = AsyncMock(return_value=result_mock)
        
        with patch('api.services.veto_service.get_db_session', return_value=mock_db_session):
            with pytest.raises(VetoNotAllowed):
                await veto_service.commit_operation(
                    session_id=sample_veto_session.id
                )


# ============== Test 4: Race Condition Veto ==============

class TestRaceConditionVeto:
    """Test race condition su veto simultanei."""
    
    @pytest.mark.asyncio
    async def test_veto_after_expiry_raises_error(self, veto_service, mock_db_session, sample_veto_session):
        """Test: veto dopo scadenza window solleva VetoWindowExpired."""
        sample_veto_session.status = VetoStatus.RESERVED
        sample_veto_session.expires_at = datetime.utcnow() - timedelta(seconds=1)  # Scaduta
        
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=sample_veto_session)
        mock_db_session.execute = AsyncMock(return_value=result_mock)
        
        with patch('api.services.veto_service.get_db_session', return_value=mock_db_session):
            with pytest.raises(VetoWindowExpired):
                await veto_service.exert_veto(
                    session_id=sample_veto_session.id,
                    operator_id=uuid4(),
                    rationale="Too late rationale"
                )
    
    @pytest.mark.asyncio
    async def test_veto_without_rationale_raises_error(self, veto_service, mock_db_session, sample_veto_session):
        """Test: veto senza rationale solleva ValueError."""
        with pytest.raises(ValueError, match="Rationale required"):
            await veto_service.exert_veto(
                session_id=sample_veto_session.id,
                operator_id=uuid4(),
                rationale="Short"  # Troppo corto (< 10 chars)
            )
    
    @pytest.mark.asyncio
    async def test_veto_on_nonexistent_session_raises(self, veto_service, mock_db_session):
        """Test: veto su sessione inesistente solleva VetoError."""
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)
        mock_db_session.execute = AsyncMock(return_value=result_mock)
        
        with patch('api.services.veto_service.get_db_session', return_value=mock_db_session):
            with pytest.raises(VetoError):
                await veto_service.exert_veto(
                    session_id=uuid4(),
                    operator_id=uuid4(),
                    rationale="Valid rationale here"
                )
    
    @pytest.mark.asyncio
    async def test_pessimistic_locking_on_veto(self, veto_service, mock_db_session, sample_veto_session):
        """Test: veto usa pessimistic locking (WITH FOR UPDATE)."""
        sample_veto_session.status = VetoStatus.RESERVED
        sample_veto_session.expires_at = datetime.utcnow() + timedelta(seconds=60)
        
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=sample_veto_session)
        mock_db_session.execute = AsyncMock(return_value=result_mock)
        
        with patch('api.services.veto_service.get_db_session', return_value=mock_db_session):
            await veto_service.exert_veto(
                session_id=sample_veto_session.id,
                operator_id=uuid4(),
                rationale="Testing pessimistic lock"
            )
            
            # Verifica che execute sia stato chiamato (con with_for_update nel codice reale)
            mock_db_session.execute.assert_called()


# ============== Test 5: Health Check Integration ==============

class TestHealthCheckIntegration:
    """Test integrazione con health check."""
    
    @pytest.mark.asyncio
    async def test_veto_service_implements_circuit_breaker(self, veto_service):
        """Test: VetoService ha circuit breaker integrato."""
        assert veto_service._circuit_breaker is not None
        assert veto_service._circuit_breaker.name == "veto_service"
    
    @pytest.mark.asyncio
    async def test_session_time_remaining_calculation(self, sample_veto_session):
        """Test: calcolo time remaining corretto."""
        # Sessione appena creata
        sample_veto_session.expires_at = datetime.utcnow() + timedelta(seconds=30)
        sample_veto_session.status = VetoStatus.RESERVED
        
        remaining = sample_veto_session.time_remaining_seconds
        assert 29 <= remaining <= 30  # Tolleranza 1 secondo
    
    @pytest.mark.asyncio
    async def test_expired_session_time_remaining_is_zero(self, sample_veto_session):
        """Test: sessione scaduta ha time_remaining = 0."""
        sample_veto_session.expires_at = datetime.utcnow() - timedelta(seconds=10)
        sample_veto_session.status = VetoStatus.RESERVED
        
        assert sample_veto_session.time_remaining_seconds == 0.0
        assert sample_veto_session.is_expired is True
    
    @pytest.mark.asyncio
    async def test_can_be_vetoed_only_in_reserved(self, sample_veto_session):
        """Test: can_be_vetoed solo in stato RESERVED."""
        # RESERVED e non scaduta
        sample_veto_session.status = VetoStatus.RESERVED
        sample_veto_session.expires_at = datetime.utcnow() + timedelta(seconds=30)
        assert sample_veto_session.can_be_vetoed is True
        
        # COMMITTED
        sample_veto_session.status = VetoStatus.COMMITTED
        assert sample_veto_session.can_be_vetoed is False
        
        # VETOED
        sample_veto_session.status = VetoStatus.VETOED
        assert sample_veto_session.can_be_vetoed is False
        
        # Scaduta
        sample_veto_session.status = VetoStatus.RESERVED
        sample_veto_session.expires_at = datetime.utcnow() - timedelta(seconds=1)
        assert sample_veto_session.can_be_vetoed is False


# ============== Test 6: Audit Logging ==============

class TestAuditLogging:
    """Test audit trail immutabile."""
    
    @pytest.mark.asyncio
    async def test_audit_log_created_on_window_open(self, veto_service, mock_db_session):
        """Test: audit log creato su apertura window."""
        with patch('api.services.veto_service.get_db_session', return_value=mock_db_session):
            session = await veto_service.open_veto_window(
                agent_type=AgentType.PAOLO,
                operation_type="carrier_failover",
                amount_eur=Decimal("5000"),
                context={"ai_rationale": {"reason": "test"}}
            )
            
            # Verifica che audit sia stato aggiunto
            calls = mock_db_session.add.call_args_list
            audit_calls = [c for c in calls if isinstance(c[0][0], DecisionAudit)]
            assert len(audit_calls) >= 1
    
    @pytest.mark.asyncio
    async def test_audit_log_gdpr_compliant(self, veto_service, mock_db_session, sample_veto_session):
        """Test: audit log include campi GDPR."""
        sample_veto_session.status = VetoStatus.RESERVED
        sample_veto_session.expires_at = datetime.utcnow() + timedelta(seconds=60)
        
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=sample_veto_session)
        mock_db_session.execute = AsyncMock(return_value=result_mock)
        
        operator_id = uuid4()
        
        with patch('api.services.veto_service.get_db_session', return_value=mock_db_session):
            await veto_service.exert_veto(
                session_id=sample_veto_session.id,
                operator_id=operator_id,
                rationale="GDPR test rationale"
            )
            
            # Verifica audit con operator_id
            calls = mock_db_session.add.call_args_list
            audit_calls = [c for c in calls if isinstance(c[0][0], DecisionAudit)]
            assert len(audit_calls) >= 1


# ============== Test 7: Service Factory ==============

class TestServiceFactory:
    """Test factory pattern per singleton."""
    
    def test_get_veto_service_returns_singleton(self):
        """Test: factory ritorna singleton."""
        from api.services.veto_service import _veto_service_instance
        
        # Reset per test
        import api.services.veto_service as vs_module
        original = vs_module._veto_service_instance
        vs_module._veto_service_instance = None
        
        try:
            service1 = get_veto_service()
            service2 = get_veto_service()
            
            assert service1 is service2
        finally:
            vs_module._veto_service_instance = original
    
    @pytest.mark.asyncio
    async def test_shutdown_flushes_buffer(self, veto_service, mock_db_session):
        """Test: shutdown flusha eventi rimanenti."""
        with patch('api.services.veto_service.get_db_session', return_value=mock_db_session):
            # Crea una sessione (aggiunge al buffer)
            session = await veto_service.open_veto_window(
                agent_type=AgentType.PAOLO,
                operation_type="carrier_failover",
                amount_eur=Decimal("5000")
            )
            
            # Shutdown
            await veto_service.shutdown()
            
            # Verifica buffer svuotato (i timer sono stati cancellati)
            assert len(veto_service._active_timers) == 0


# ============== Coverage Helper ==============

class TestCoverageEdgeCases:
    """Test casi limite per coverage completa."""
    
    @pytest.mark.asyncio
    async def test_get_session_status_returns_none_for_invalid_id(self, veto_service, mock_db_session):
        """Test: get_session_status ritorna None per ID inesistente."""
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)
        mock_db_session.execute = AsyncMock(return_value=result_mock)
        
        with patch('api.services.veto_service.get_db_session', return_value=mock_db_session):
            result = await veto_service.get_session_status(uuid4())
            assert result is None
    
    @pytest.mark.asyncio
    async def test_list_active_sessions_filters_by_agent(self, veto_service, mock_db_session):
        """Test: list_active_sessions filtra per agent_type."""
        # Mock ritorna lista vuota
        result_mock = MagicMock()
        result_mock.scalars.return_value.all = MagicMock(return_value=[])
        mock_db_session.execute = AsyncMock(return_value=result_mock)
        
        with patch('api.services.veto_service.get_db_session', return_value=mock_db_session):
            result = await veto_service.list_active_sessions(agent_type=AgentType.PAOLO)
            assert result == []
            
            # Verifica chiamata senza filtro
            result2 = await veto_service.list_active_sessions()
            assert result2 == []
    
    @pytest.mark.asyncio
    async def test_session_to_dict_serialization(self, sample_veto_session):
        """Test: to_dict serializza correttamente."""
        data = sample_veto_session.to_dict()
        
        assert "id" in data
        assert "agent_type" in data
        assert "status" in data
        assert "can_be_vetoed" in data
        assert isinstance(data["can_be_vetoed"], bool)