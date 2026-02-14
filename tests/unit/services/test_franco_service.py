"""
AUTO-BROKER: Unit Tests for FRANCO Retention Service

Test suite per il servizio di retention.
"""
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# Importa i modelli e il servizio da testare
from models import Base, Spedizione, Lead, RetentionAttempt, Contratto
from services.franco_service import FrancoService, AGENT_ID_FRANCO, MAX_CALLS_PER_HOUR


# ==========================================
# FIXTURES
# ==========================================

@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Fixture per database in-memory per i test.
    """
    # Crea engine async con SQLite in-memory
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=NullPool,
        echo=False
    )
    
    # Crea tabelle
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Crea sessione
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def sample_lead(db_session: AsyncSession) -> Lead:
    """Crea un lead di esempio."""
    lead = Lead(
        id=uuid4(),
        nome="Mario",
        cognome="Rossi",
        azienda="Test Company Srl",
        telefono="+393331234567",
        email="mario.rossi@test.com",
        status="attivo"
    )
    db_session.add(lead)
    await db_session.commit()
    await db_session.refresh(lead)
    return lead


@pytest_asyncio.fixture
async def sample_shipment(
    db_session: AsyncSession,
    sample_lead: Lead
) -> Spedizione:
    """Crea una spedizione consegnata 7 giorni fa."""
    shipment = Spedizione(
        id=uuid4(),
        lead_id=sample_lead.id,
        numero_spedizione=f"SPED-{uuid4().hex[:8].upper()}",
        tracking_number="TRACK123456",
        status="consegnata",
        data_consegna_effettiva=datetime.utcnow() - timedelta(days=7),
        peso_effettivo_kg=Decimal("10.5"),
        lane_origine="Milano",
        lane_destinazione="Roma"
    )
    db_session.add(shipment)
    await db_session.commit()
    await db_session.refresh(shipment)
    return shipment


@pytest_asyncio.fixture
async def franco_service(db_session: AsyncSession) -> FrancoService:
    """Crea un'istanza del servizio Franco."""
    return FrancoService(db_session=db_session)


@pytest.fixture
def mock_retell_call():
    """Fixture per mockare le chiamate Retell."""
    with patch(
        "services.franco_service.retell_service.create_call",
        new_callable=AsyncMock
    ) as mock:
        mock.return_value = {
            "call_id": f"call_{uuid4().hex}",
            "status": "queued",
            "agent_id": AGENT_ID_FRANCO
        }
        yield mock


# ==========================================
# TESTS
# ==========================================

class TestFrancoService:
    """Test suite per FrancoService."""
    
    @pytest.mark.asyncio
    async def test_get_eligible_shipments(
        self,
        franco_service: FrancoService,
        sample_shipment: Spedizione
    ):
        """
        Test: Recupero spedizioni eleggibili.
        
        Verifica che vengano trovate spedizioni con consegna 7 giorni fa.
        """
        shipments = await franco_service.get_eligible_shipments()
        
        assert len(shipments) == 1
        assert shipments[0].id == sample_shipment.id
        assert shipments[0].status == "consegnata"
    
    @pytest.mark.asyncio
    async def test_get_eligible_shipments_excludes_recent(
        self,
        db_session: AsyncSession,
        sample_lead: Lead,
        franco_service: FrancoService
    ):
        """
        Test: Spedizioni recenti non sono eleggibili.
        
        Verifica che spedizioni consegnate oggi non vengano selezionate.
        """
        # Crea spedizione consegnata oggi
        recent_shipment = Spedizione(
            id=uuid4(),
            lead_id=sample_lead.id,
            numero_spedizione=f"SPED-{uuid4().hex[:8].upper()}",
            status="consegnata",
            data_consegna_effettiva=datetime.utcnow(),  # Oggi, non 7 giorni fa
            lane_origine="Milano",
            lane_destinazione="Roma"
        )
        db_session.add(recent_shipment)
        await db_session.commit()
        
        shipments = await franco_service.get_eligible_shipments()
        
        # Non dovrebbe trovare spedizioni (quella di oggi non conta)
        assert len(shipments) == 0
    
    @pytest.mark.asyncio
    async def test_get_eligible_shipments_excludes_already_attempted(
        self,
        db_session: AsyncSession,
        sample_shipment: Spedizione,
        franco_service: FrancoService
    ):
        """
        Test: Spedizioni già tentate sono escluse.
        
        Verifica idempotenza: non processare spedizioni già chiamate.
        """
        # Crea un tentativo precedente
        attempt = RetentionAttempt(
            spedizione_id=sample_shipment.id,
            attempted_at=datetime.utcnow(),
            call_outcome="success"
        )
        db_session.add(attempt)
        await db_session.commit()
        
        shipments = await franco_service.get_eligible_shipments()
        
        # Non dovrebbe trovare la spedizione perché già tentata
        assert len(shipments) == 0
    
    @pytest.mark.asyncio
    async def test_is_already_attempted_true(
        self,
        db_session: AsyncSession,
        sample_shipment: Spedizione,
        franco_service: FrancoService
    ):
        """
        Test: Verifica idempotenza ritorna True se già tentato.
        """
        # Crea tentativo
        attempt = RetentionAttempt(
            spedizione_id=sample_shipment.id,
            attempted_at=datetime.utcnow(),
            call_outcome="success"
        )
        db_session.add(attempt)
        await db_session.commit()
        
        is_attempted = await franco_service._is_already_attempted(sample_shipment.id)
        
        assert is_attempted is True
    
    @pytest.mark.asyncio
    async def test_is_already_attempted_false(
        self,
        sample_shipment: Spedizione,
        franco_service: FrancoService
    ):
        """
        Test: Verifica idempotenza ritorna False se mai tentato.
        """
        is_attempted = await franco_service._is_already_attempted(sample_shipment.id)
        
        assert is_attempted is False
    
    @pytest.mark.asyncio
    async def test_process_retention_success(
        self,
        franco_service: FrancoService,
        sample_shipment: Spedizione,
        mock_retell_call: AsyncMock
    ):
        """
        Test: Processo retention completo con successo.
        
        Verifica che venga effettuata la chiamata e registrata nel DB.
        """
        result = await franco_service.process_retention()
        
        # Verifica statistiche
        assert result["processed"] == 1
        assert result["successful_calls"] == 1
        assert result["failed_calls"] == 0
        assert result["skipped"] == 0
        
        # Verifica che Retell sia stato chiamato
        mock_retell_call.assert_called_once()
        call_args = mock_retell_call.call_args
        assert call_args.kwargs["agent_id"] == AGENT_ID_FRANCO
        assert call_args.kwargs["phone_number"] == "+393331234567"
    
    @pytest.mark.asyncio
    async def test_process_retention_idempotency(
        self,
        db_session: AsyncSession,
        franco_service: FrancoService,
        sample_shipment: Spedizione,
        mock_retell_call: AsyncMock
    ):
        """
        Test: Idempotenza - non chiama due volte la stessa spedizione.
        
        Verifica che se una spedizione è già stata processata,
        venga saltata nel batch successivo.
        """
        # Primo processo
        result1 = await franco_service.process_retention()
        assert result1["successful_calls"] == 1
        
        # Reset mock per secondo controllo
        mock_retell_call.reset_mock()
        
        # Secondo processo (stessa spedizione)
        result2 = await franco_service.process_retention()
        
        # Dovrebbe essere saltata
        assert result2["processed"] == 1  # Trovata ma saltata
        assert result2["skipped"] == 1
        assert result2["successful_calls"] == 0
        
        # Retell non dovrebbe essere chiamato di nuovo
        mock_retell_call.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_process_retention_continues_on_error(
        self,
        db_session: AsyncSession,
        franco_service: FrancoService,
        sample_lead: Lead,
        sample_shipment: Spedizione,
        mock_retell_call: AsyncMock
    ):
        """
        Test: Se una chiamata fallisce, continua con le altre.
        
        Non bloccare il batch per un singolo errore.
        """
        # Crea seconda spedizione
        shipment2 = Spedizione(
            id=uuid4(),
            lead_id=sample_lead.id,
            numero_spedizione=f"SPED-{uuid4().hex[:8].upper()}",
            tracking_number="TRACK789",
            status="consegnata",
            data_consegna_effettiva=datetime.utcnow() - timedelta(days=7),
            lane_origine="Torino",
            lane_destinazione="Napoli"
        )
        db_session.add(shipment2)
        await db_session.commit()
        
        # Fa fallire la prima chiamata
        mock_retell_call.side_effect = [
            Exception("API Error"),  # Prima chiamata fallisce
            {"call_id": "call_success", "status": "queued"}  # Seconda ok
        ]
        
        result = await franco_service.process_retention()
        
        # Verifica che entrambe siano state processate
        assert result["processed"] == 2
        assert result["successful_calls"] == 1
        assert result["failed_calls"] == 1
        assert len(result["errors"]) == 1
    
    @pytest.mark.asyncio
    async def test_rate_limit_blocks_after_max(
        self,
        franco_service: FrancoService
    ):
        """
        Test: Rate limiting blocca dopo MAX_CALLS_PER_HOUR chiamate.
        """
        # Simula MAX_CALLS_PER_HOUR chiamate
        for _ in range(MAX_CALLS_PER_HOUR):
            franco_service._call_timestamps.append(datetime.utcnow())
        
        # Verifica che il rate limit blocchi
        can_proceed = await franco_service._check_rate_limit()
        assert can_proceed is False
    
    @pytest.mark.asyncio
    async def test_rate_limit_allows_under_max(
        self,
        franco_service: FrancoService
    ):
        """
        Test: Rate limiting permette chiamate sotto il limite.
        """
        # Simula meno del massimo
        for _ in range(MAX_CALLS_PER_HOUR - 1):
            franco_service._call_timestamps.append(datetime.utcnow())
        
        can_proceed = await franco_service._check_rate_limit()
        assert can_proceed is True
    
    @pytest.mark.asyncio
    async def test_rate_limit_resets_after_window(
        self,
        franco_service: FrancoService
    ):
        """
        Test: Rate limiting si resetta dopo la finestra temporale.
        """
        # Simula chiamate vecchie (oltre 1 ora fa)
        old_time = datetime.utcnow() - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS + 60)
        for _ in range(MAX_CALLS_PER_HOUR):
            franco_service._call_timestamps.append(old_time)
        
        # Dovrebbe permettere nuove chiamate perché quelle vecchie scadono
        can_proceed = await franco_service._check_rate_limit()
        assert can_proceed is True
    
    @pytest.mark.asyncio
    async def test_process_retention_respects_rate_limit(
        self,
        db_session: AsyncSession,
        sample_lead: Lead,
        franco_service: FrancoService,
        mock_retell_call: AsyncMock
    ):
        """
        Test: Processo rispetta rate limiting e salta spedizioni se necessario.
        """
        # Crea più spedizioni del limite
        for i in range(MAX_CALLS_PER_HOUR + 5):
            shipment = Spedizione(
                id=uuid4(),
                lead_id=sample_lead.id,
                numero_spedizione=f"SPED-{i}-{uuid4().hex[:4].upper()}",
                status="consegnata",
                data_consegna_effettiva=datetime.utcnow() - timedelta(days=7),
                lane_origine="Milano",
                lane_destinazione="Roma"
            )
            db_session.add(shipment)
        await db_session.commit()
        
        result = await franco_service.process_retention()
        
        # Solo MAX_CALLS_PER_HOUR dovrebbero essere chiamate
        assert result["successful_calls"] <= MAX_CALLS_PER_HOUR
        assert result["skipped"] >= 5  # Almeno 5 saltate per rate limit
    
    @pytest.mark.asyncio
    async def test_hash_identifier_consistency(
        self,
        franco_service: FrancoService
    ):
        """
        Test: Hash genera valori consistenti per stesso input.
        """
        phone = "+393331234567"
        hash1 = franco_service._hash_identifier(phone)
        hash2 = franco_service._hash_identifier(phone)
        
        assert hash1 == hash2
        assert len(hash1) == 16  # SHA-256 truncated
        assert hash1 != phone  # Non è il valore originale
    
    @pytest.mark.asyncio
    async def test_hash_identifier_different_inputs(
        self,
        franco_service: FrancoService
    ):
        """
        Test: Hash diversi per input diversi.
        """
        hash1 = franco_service._hash_identifier("+393331234567")
        hash2 = franco_service._hash_identifier("+393331234568")
        
        assert hash1 != hash2
    
    @pytest.mark.asyncio
    async def test_get_retention_stats_empty(
        self,
        franco_service: FrancoService
    ):
        """
        Test: Statistiche con database vuoto.
        """
        stats = await franco_service.get_retention_stats()
        
        assert stats["total_attempts"] == 0
        assert stats["success_rate_percent"] == 0
        assert stats["rebooking_rate_percent"] == 0
        assert stats["recent_attempts_7d"] == 0
    
    @pytest.mark.asyncio
    async def test_get_retention_stats_with_data(
        self,
        db_session: AsyncSession,
        sample_shipment: Spedizione,
        franco_service: FrancoService
    ):
        """
        Test: Statistiche con dati presenti.
        """
        # Crea tentativi con diversi esiti
        for i in range(10):
            attempt = RetentionAttempt(
                id=uuid4(),
                spedizione_id=sample_shipment.id,
                attempted_at=datetime.utcnow() - timedelta(days=i),
                call_outcome="success" if i < 7 else "failed",
                rebooking_accepted=(i < 3)  # 3 ri-prenotazioni
            )
            db_session.add(attempt)
        await db_session.commit()
        
        stats = await franco_service.get_retention_stats()
        
        assert stats["total_attempts"] == 10
        assert stats["success_rate_percent"] == 70.0  # 7/10
        assert stats["rebooking_rate_percent"] == 30.0  # 3/10
        assert stats["recent_attempts_7d"] >= 7  # Almeno quelli creati
    
    @pytest.mark.asyncio
    async def test_skips_shipment_without_phone(
        self,
        db_session: AsyncSession,
        sample_lead: Lead,
        franco_service: FrancoService,
        mock_retell_call: AsyncMock
    ):
        """
        Test: Salta spedizioni se il lead non ha telefono.
        """
        # Rimuovi telefono dal lead
        sample_lead.telefono = None
        await db_session.commit()
        
        result = await franco_service.process_retention()
        
        assert result["processed"] == 1
        assert result["skipped"] == 1
        assert result["successful_calls"] == 0
        mock_retell_call.assert_not_called()


class TestFrancoServiceCircuitBreaker:
    """Test per il circuit breaker."""
    
    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(
        self,
        franco_service: FrancoService,
        sample_shipment: Spedizione,
    ):
        """
        Test: Circuit breaker si apre dopo threshold fallimenti.
        """
        with patch(
            "services.franco_service.retell_service.create_call",
            new_callable=AsyncMock,
            side_effect=Exception("API Error")
        ) as mock:
            # Prima fallisce threshold volte
            for _ in range(5):
                try:
                    await franco_service.process_retention()
                except:
                    pass
            
            # Il circuit dovrebbe essere aperto ora
            assert franco_service.circuit_breaker._state.value == "open"


# ==========================================
# COSTANTI IMPORTATE PER I TEST
# ==========================================

from services.franco_service import MAX_CALLS_PER_HOUR, RATE_LIMIT_WINDOW_SECONDS
