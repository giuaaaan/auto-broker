"""
AUTO-BROKER: Veto Service

Servizio core per gestione veto window in modalità human-on-the-loop.
Implementa stato RESERVED con timer async non-blocking.
"""
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional, Callable, List
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db_session
from api.models.governance import (
    VetoSession, 
    VetoStatus, 
    AgentType, 
    DecisionAudit,
    DecisionMode
)
from api.services.circuit_breaker import CircuitBreaker

logger = structlog.get_logger()


class VetoError(Exception):
    """Eccezione base per errori veto."""
    pass


class VetoWindowExpired(VetoError):
    """Veto window scaduta."""
    pass


class VetoNotAllowed(VetoError):
    """Veto non permesso in questo stato."""
    pass


class VetoService:
    """
    Servizio gestione veto window per governance asimmetrica.
    
    Features:
    - Stato RESERVED con soft lock
    - Timer async non-blocking (60s default)
    - State machine rigorosa
    - Compensation su veto post-commit
    - Circuit breaker per operazioni esterne
    """
    
    def __init__(self):
        self._active_timers: Dict[UUID, asyncio.Task] = {}
        self._circuit_breaker = CircuitBreaker(
            name="veto_service",
            failure_threshold=5,
            recovery_timeout=60
        )
        self._expiry_callbacks: Dict[UUID, Callable] = {}
        
        logger.info("veto_service_initialized")
    
    async def open_veto_window(
        self,
        agent_type: AgentType,
        operation_type: str,
        shipment_id: Optional[UUID],
        carrier_id: Optional[UUID],
        amount_eur: Decimal,
        confidence_score: Optional[Decimal] = None,
        timeout_seconds: int = 60,
        context: Optional[Dict[str, Any]] = None,
        on_expiry: Optional[Callable[[UUID], None]] = None
    ) -> VetoSession:
        """
        Apre una nuova veto window (stato RESERVED).
        
        Args:
            agent_type: Tipo agente (PAOLO/GIULIA)
            operation_type: Tipo operazione (carrier_failover, etc)
            shipment_id: ID spedizione
            carrier_id: ID carrier (per soft lock)
            amount_eur: Importo coinvolto
            confidence_score: Score AI confidence
            timeout_seconds: Durata veto window (default 60)
            context: Contesto aggiuntivo (JSON)
            on_expiry: Callback quando timer scade
            
        Returns:
            VetoSession creata
        """
        session_id = uuid4()
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=timeout_seconds)
        
        async with get_db_session() as db:
            # Crea sessione in stato RESERVED
            session = VetoSession(
                id=session_id,
                agent_type=agent_type,
                operation_type=operation_type,
                shipment_id=shipment_id,
                carrier_id=carrier_id,
                amount_eur=amount_eur,
                confidence_score=confidence_score,
                status=VetoStatus.RESERVED,
                timeout_seconds=timeout_seconds,
                opened_at=now,
                expires_at=expires_at,
                context=context or {}
            )
            
            db.add(session)
            await db.commit()
            
            # Log audit
            await self._log_audit(
                db=db,
                session_id=session_id,
                event_type="window_opened",
                ai_rationale=context.get("ai_rationale") if context else None,
                ai_confidence=confidence_score
            )
        
        # Avvia timer async non-blocking
        timer_task = asyncio.create_task(
            self._veto_timer(session_id, timeout_seconds)
        )
        self._active_timers[session_id] = timer_task
        
        # Registra callback expiry
        if on_expiry:
            self._expiry_callbacks[session_id] = on_expiry
        
        logger.info(
            "veto_window_opened",
            session_id=str(session_id),
            agent_type=agent_type.value,
            amount=str(amount_eur),
            timeout=timeout_seconds
        )
        
        return session
    
    async def exert_veto(
        self,
        session_id: UUID,
        operator_id: UUID,
        rationale: str,
        veto_type: str = "temporary"
    ) -> VetoSession:
        """
        Esercita veto su una sessione RESERVED.
        
        Args:
            session_id: ID sessione veto
            operator_id: ID operatore che veta
            rationale: Motivazione veto (obbligatoria)
            veto_type: Tipo veto (temporary/permanent/pattern)
            
        Returns:
            VetoSession aggiornata
            
        Raises:
            VetoWindowExpired: Se window già scaduta
            VetoNotAllowed: Se stato non permette veto
        """
        if not rationale or len(rationale.strip()) < 10:
            raise ValueError("Rationale required (min 10 chars)")
        
        async with get_db_session() as db:
            # Lock pessimistico per race condition
            result = await db.execute(
                select(VetoSession)
                .where(VetoSession.id == session_id)
                .with_for_update()
            )
            session = result.scalar_one_or_none()
            
            if not session:
                raise VetoError(f"Session {session_id} not found")
            
            # Verifica stato
            if session.status != VetoStatus.RESERVED:
                raise VetoNotAllowed(
                    f"Cannot veto session in status {session.status.value}"
                )
            
            # Verifica scadenza
            if session.is_expired:
                # Cancella timer se ancora attivo
                await self._cancel_timer(session_id)
                
                # Aggiorna stato a EXPIRED
                session.status = VetoStatus.EXPIRED
                await db.commit()
                
                raise VetoWindowExpired(
                    f"Veto window expired at {session.expires_at}"
                )
            
            # Calcola time to decision
            time_to_decision_ms = int(
                (datetime.utcnow() - session.opened_at).total_seconds() * 1000
            )
            
            # Aggiorna stato a VETOED
            session.status = VetoStatus.VETOED
            session.vetoed_at = datetime.utcnow()
            session.operator_id = operator_id
            session.operator_rationale = rationale
            
            await db.commit()
            
            # Log audit
            await self._log_audit(
                db=db,
                session_id=session_id,
                event_type="veto_exerted",
                operator_id=operator_id,
                operator_action="veto",
                operator_rationale=rationale,
                time_to_decision_ms=time_to_decision_ms
            )
        
        # Cancella timer
        await self._cancel_timer(session_id)
        
        # Cleanup callback
        if session_id in self._expiry_callbacks:
            del self._expiry_callbacks[session_id]
        
        logger.info(
            "veto_exerted",
            session_id=str(session_id),
            operator_id=str(operator_id),
            veto_type=veto_type,
            time_to_decision_ms=time_to_decision_ms
        )
        
        return session
    
    async def commit_operation(
        self,
        session_id: UUID,
        blockchain_tx_hash: Optional[str] = None
    ) -> VetoSession:
        """
        Commit dell'operazione (stato COMMITTED).
        
        Da chiamare quando l'operazione è stata eseguita
        (es. failover completato).
        
        Args:
            session_id: ID sessione
            blockchain_tx_hash: Hash transazione blockchain (opzionale)
            
        Returns:
            VetoSession aggiornata
        """
        async with get_db_session() as db:
            result = await db.execute(
                select(VetoSession)
                .where(VetoSession.id == session_id)
                .with_for_update()
            )
            session = result.scalar_one_or_none()
            
            if not session:
                raise VetoError(f"Session {session_id} not found")
            
            if session.status not in [VetoStatus.RESERVED, VetoStatus.EXPIRED]:
                raise VetoNotAllowed(
                    f"Cannot commit from status {session.status.value}"
                )
            
            # Transizione a COMMITTING -> COMMITTED
            session.status = VetoStatus.COMMITTING
            await db.flush()
            
            session.status = VetoStatus.COMMITTED
            session.committed_at = datetime.utcnow()
            session.blockchain_tx_hash = blockchain_tx_hash
            
            await db.commit()
            
            # Log audit
            await self._log_audit(
                db=db,
                session_id=session_id,
                event_type="operation_committed",
                final_state="committed",
                blockchain_tx_hash=blockchain_tx_hash
            )
        
        # Cleanup timer se ancora attivo
        await self._cancel_timer(session_id)
        
        logger.info(
            "operation_committed",
            session_id=str(session_id),
            blockchain_tx_hash=blockchain_tx_hash
        )
        
        return session
    
    async def request_compensation(
        self,
        session_id: UUID,
        operator_id: UUID,
        rationale: str,
        compensation_callback: Callable[[UUID], None]
    ) -> VetoSession:
        """
        Richiede compensazione per veto post-commit.
        
        Quando un operatore veta DOPO che l'operazione è già
        stata committata, si attiva la compensazione.
        
        Args:
            session_id: ID sessione COMMITTED
            operator_id: ID operatore
            rationale: Motivazione
            compensation_callback: Funzione da chiamare per compensare
            
        Returns:
            VetoSession in stato VETOED (compensation pending)
        """
        async with get_db_session() as db:
            result = await db.execute(
                select(VetoSession)
                .where(VetoSession.id == session_id)
                .with_for_update()
            )
            session = result.scalar_one_or_none()
            
            if not session:
                raise VetoError(f"Session {session_id} not found")
            
            if session.status != VetoStatus.COMMITTED:
                raise VetoNotAllowed(
                    f"Compensation only from COMMITTED, not {session.status.value}"
                )
            
            # Aggiorna stato a VETOED
            session.status = VetoStatus.VETOED
            session.vetoed_at = datetime.utcnow()
            session.operator_id = operator_id
            session.operator_rationale = rationale
            
            await db.commit()
            
            # Log audit
            await self._log_audit(
                db=db,
                session_id=session_id,
                event_type="veto_post_commit",
                operator_id=operator_id,
                operator_action="veto",
                operator_rationale=rationale,
                final_state="compensation_pending"
            )
        
        # Esegui compensazione (async)
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, compensation_callback, session_id
            )
            
            logger.info(
                "compensation_executed",
                session_id=str(session_id),
                operator_id=str(operator_id)
            )
        except Exception as e:
            logger.error(
                "compensation_failed",
                session_id=str(session_id),
                error=str(e)
            )
            raise
        
        return session
    
    async def get_session_status(
        self,
        session_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Recupera stato di una sessione veto.
        
        Args:
            session_id: ID sessione
            
        Returns:
            Dict con stato sessione o None
        """
        async with get_db_session() as db:
            result = await db.execute(
                select(VetoSession).where(VetoSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if not session:
                return None
            
            return session.to_dict()
    
    async def list_active_sessions(
        self,
        agent_type: Optional[AgentType] = None
    ) -> List[Dict[str, Any]]:
        """
        Lista sessioni veto attive (RESERVED).
        
        Args:
            agent_type: Filtra per tipo agente
            
        Returns:
            Lista sessioni attive
        """
        async with get_db_session() as db:
            query = select(VetoSession).where(
                VetoSession.status == VetoStatus.RESERVED
            )
            
            if agent_type:
                query = query.where(VetoSession.agent_type == agent_type)
            
            query = query.order_by(VetoSession.expires_at)
            
            result = await db.execute(query)
            sessions = result.scalars().all()
            
            return [s.to_dict() for s in sessions]
    
    async def cancel_session(
        self,
        session_id: UUID,
        reason: str
    ) -> VetoSession:
        """
        Cancella una sessione veto (stato CANCELLED).
        
        Usato per errori o annullamenti manuali.
        
        Args:
            session_id: ID sessione
            reason: Motivazione cancellazione
            
        Returns:
            VetoSession cancellata
        """
        async with get_db_session() as db:
            result = await db.execute(
                select(VetoSession)
                .where(VetoSession.id == session_id)
                .with_for_update()
            )
            session = result.scalar_one_or_none()
            
            if not session:
                raise VetoError(f"Session {session_id} not found")
            
            if session.status not in [VetoStatus.RESERVED, VetoStatus.EXPIRED]:
                raise VetoNotAllowed(
                    f"Cannot cancel from status {session.status.value}"
                )
            
            session.status = VetoStatus.CANCELLED
            await db.commit()
            
            await self._log_audit(
                db=db,
                session_id=session_id,
                event_type="session_cancelled",
                operator_rationale=reason
            )
        
        # Cancella timer
        await self._cancel_timer(session_id)
        
        logger.info(
            "session_cancelled",
            session_id=str(session_id),
            reason=reason
        )
        
        return session
    
    # ============== Metodi privati ==============
    
    async def _veto_timer(self, session_id: UUID, timeout_seconds: int):
        """
        Timer async per veto window.
        
        Attende il timeout, poi verifica se la sessione
        è ancora RESERVED e la marca come EXPIRED.
        """
        try:
            await asyncio.sleep(timeout_seconds)
            
            async with get_db_session() as db:
                result = await db.execute(
                    select(VetoSession)
                    .where(VetoSession.id == session_id)
                    .with_for_update()
                )
                session = result.scalar_one_or_none()
                
                if not session:
                    logger.warning("timer_session_not_found", session_id=str(session_id))
                    return
                
                # Solo se ancora RESERVED
                if session.status == VetoStatus.RESERVED:
                    session.status = VetoStatus.EXPIRED
                    await db.commit()
                    
                    await self._log_audit(
                        db=db,
                        session_id=session_id,
                        event_type="window_expired",
                        final_state="expired"
                    )
                    
                    logger.info(
                        "veto_window_expired",
                        session_id=str(session_id)
                    )
                    
                    # Chiama callback expiry se registrato
                    if session_id in self._expiry_callbacks:
                        callback = self._expiry_callbacks.pop(session_id)
                        try:
                            callback(session_id)
                        except Exception as e:
                            logger.error(
                                "expiry_callback_failed",
                                session_id=str(session_id),
                                error=str(e)
                            )
        
        except asyncio.CancelledError:
            # Timer cancellato (veto ricevuto o altro)
            logger.debug("veto_timer_cancelled", session_id=str(session_id))
        
        except Exception as e:
            logger.error(
                "veto_timer_error",
                session_id=str(session_id),
                error=str(e)
            )
        
        finally:
            # Cleanup
            if session_id in self._active_timers:
                del self._active_timers[session_id]
    
    async def _cancel_timer(self, session_id: UUID):
        """Cancella timer attivo per una sessione."""
        if session_id in self._active_timers:
            timer = self._active_timers.pop(session_id)
            if not timer.done():
                timer.cancel()
                try:
                    await timer
                except asyncio.CancelledError:
                    pass
    
    async def _log_audit(
        self,
        db: AsyncSession,
        session_id: UUID,
        event_type: str,
        operator_id: Optional[UUID] = None,
        operator_action: Optional[str] = None,
        operator_rationale: Optional[str] = None,
        ai_rationale: Optional[Dict] = None,
        ai_confidence: Optional[Decimal] = None,
        time_to_decision_ms: Optional[int] = None,
        final_state: Optional[str] = None,
        blockchain_tx_hash: Optional[str] = None
    ):
        """Log entry audit immutabile."""
        audit = DecisionAudit(
            id=uuid4(),
            veto_session_id=session_id,
            event_type=event_type,
            operator_id=operator_id,
            operator_action=operator_action,
            operator_rationale=operator_rationale,
            ai_rationale=ai_rationale,
            ai_confidence=ai_confidence,
            time_to_decision_ms=time_to_decision_ms,
            final_state=final_state,
            blockchain_tx_hash=blockchain_tx_hash,
            human_supervised=(operator_id is not None),
            gdpr_article22_compliant=True  # Sempre vero con supervisione
        )
        
        db.add(audit)
        await db.flush()


# Singleton
_veto_service_instance: Optional[VetoService] = None


def get_veto_service() -> VetoService:
    """Factory per VetoService singleton."""
    global _veto_service_instance
    
    if _veto_service_instance is None:
        _veto_service_instance = VetoService()
    
    return _veto_service_instance