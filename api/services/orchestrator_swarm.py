"""
AUTO-BROKER: Swarm Orchestrator

Coordina PAOLO (Carrier Failover) e GIULIA (Dispute Resolution)
per operazioni complesse che richiedono collaborazione multi-agente.

Pattern: Event-Driven Orchestration
- PAOLO failovera carrier → GIULIA monitora dispute aumentate
- GIULIA rileva frode pattern → PAOLO blacklist carrier
"""
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from uuid import UUID

import structlog

from api.services.agents.paolo_service import get_paolo_agent, PaoloAgent
from api.services.agents.giulia_service import get_giulia_agent, GiuliaAgent, DisputeEvent
from api.database import get_db_session

logger = structlog.get_logger()


@dataclass
class SwarmEvent:
    """Evento nel sistema swarm."""
    event_type: str  # "failover", "fraud_detected", "blacklist", etc.
    source_agent: str  # "paolo", "giulia"
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    processed: bool = False


@dataclass
class BlacklistAction:
    """Azione blacklist carrier."""
    carrier_id: int
    carrier_name: str
    reason: str
    affected_shipments: List[UUID]
    failover_results: List[Any]
    permanent: bool
    executed_at: datetime


class SwarmOrchestrator:
    """
    Orchestratore per coordinamento agenti PAOLO e GIULIA.
    
    Responsabilità:
    - Event routing tra agenti
    - Pattern detection (frode, failure)
    - Coordinated actions (blacklist → failover)
    - Audit trail decisioni
    
    Flusso tipico:
    1. PAOLO detecta carrier degradato → Event a Orchestrator
    2. Orchestrator chiede a GIULIA: "Dispute aumentate per carrier X?"
    3. Se sì → Decision: Blacklist carrier
    4. Orchestrator coordina: PAOLO failovera shipment, GIULIA aggiorna rep
    """
    
    def __init__(self):
        self.paolo: PaoloAgent = get_paolo_agent()
        self.giulia: GiuliaAgent = get_giulia_agent()
        
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._event_history: List[SwarmEvent] = []
        self._blacklist_history: List[BlacklistAction] = []
        
        self._running = False
        self._processor_task: Optional[asyncio.Task] = None
        
        # Pattern tracking
        self._carrier_dispute_counts: Dict[int, int] = {}
        self._carrier_failover_counts: Dict[int, int] = {}
        
        # Thresholds
        self._fraud_threshold = 3  # Dispute sospette per blacklist
        self._failover_threshold = 2  # Failover per investigazione
        
        logger.info("swarm_orchestrator_initialized")
    
    async def start(self):
        """Avvia orchestratore."""
        if self._running:
            return
        
        self._running = True
        self._processor_task = asyncio.create_task(self._event_processor())
        
        # Avvia anche PAOLO
        await self.paolo.start_monitoring()
        
        logger.info("swarm_orchestrator_started")
    
    async def stop(self):
        """Ferma orchestratore."""
        self._running = False
        
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        
        await self.paolo.stop_monitoring()
        
        logger.info("swarm_orchestrator_stopped")
    
    async def _event_processor(self):
        """Processa eventi dalla coda."""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0
                )
                
                await self._handle_event(event)
                event.processed = True
                self._event_history.append(event)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("event_processor_error", error=str(e))
    
    async def _handle_event(self, event: SwarmEvent):
        """Gestisce singolo evento."""
        logger.info(
            "handling_swarm_event",
            event_type=event.event_type,
            source=event.source_agent
        )
        
        handlers = {
            "failover_executed": self._on_failover_executed,
            "fraud_pattern_detected": self._on_fraud_detected,
            "dispute_opened": self._on_dispute_opened,
            "carrier_degraded": self._on_carrier_degraded,
        }
        
        handler = handlers.get(event.event_type)
        if handler:
            await handler(event)
        else:
            logger.warning("unknown_event_type", event_type=event.event_type)
    
    async def _on_failover_executed(self, event: SwarmEvent):
        """Handler: PAOLO ha eseguito failover."""
        payload = event.payload
        carrier_id = payload.get("old_carrier_id")
        
        if not carrier_id:
            return
        
        # Track failover count
        self._carrier_failover_counts[carrier_id] = \
            self._carrier_failover_counts.get(carrier_id, 0) + 1
        
        # Se troppi failover, investiga con GIULIA
        if self._carrier_failover_counts[carrier_id] >= self._failover_threshold:
            logger.warning(
                "carrier_repeated_failures",
                carrier_id=carrier_id,
                failover_count=self._carrier_failover_counts[carrier_id]
            )
            
            # Chiedi a GIULIA: dispute recenti per questo carrier?
            await self._investigate_carrier(carrier_id)
    
    async def _on_fraud_detected(self, event: SwarmEvent):
        """Handler: GIULIA ha rilevato frode."""
        payload = event.payload
        carrier_id = payload.get("carrier_id")
        
        if not carrier_id:
            return
        
        # Track dispute count
        self._carrier_dispute_counts[carrier_id] = \
            self._carrier_dispute_counts.get(carrier_id, 0) + 1
        
        # Se pattern ricorrente, blacklist
        if self._carrier_dispute_counts[carrier_id] >= self._fraud_threshold:
            await self.blacklist_carrier(
                carrier_id=carrier_id,
                reason=f"Fraud pattern detected: {self._carrier_dispute_counts[carrier_id]} suspicious disputes",
                permanent=False
            )
    
    async def _on_dispute_opened(self, event: SwarmEvent):
        """Handler: Nuova dispute aperta."""
        payload = event.payload
        shipment_id = payload.get("shipment_id")
        
        # Notifica che monitoreremo
        logger.info(
            "dispute_tracked_by_orchestrator",
            shipment_id=shipment_id
        )
    
    async def _on_carrier_degraded(self, event: SwarmEvent):
        """Handler: Carrier performance degradata."""
        payload = event.payload
        carrier_id = payload.get("carrier_id")
        on_time_rate = payload.get("on_time_rate")
        
        logger.warning(
            "carrier_degraded_detected",
            carrier_id=carrier_id,
            on_time_rate=on_time_rate
        )
        
        # PAOLO già gestisce, ma orchestrator può decidere blacklist preventiva
        if on_time_rate and on_time_rate < 50:
            # Performance molto bassa → considera blacklist
            await self._investigate_carrier(carrier_id)
    
    async def _investigate_carrier(self, carrier_id: int):
        """Investiga carrier con GIULIA."""
        logger.info("investigating_carrier", carrier_id=carrier_id)
        
        # Chiedi a GIULIA stats dispute
        stats = self.giulia.get_resolution_stats()
        
        # Se dispute sospette, proponi blacklist
        dispute_count = self._carrier_dispute_counts.get(carrier_id, 0)
        
        if dispute_count >= 2:
            logger.warning(
                "investigation_recommends_blacklist",
                carrier_id=carrier_id,
                dispute_count=dispute_count
            )
    
    async def blacklist_carrier(
        self,
        carrier_id: int,
        reason: str,
        permanent: bool = False
    ) -> bool:
        """
        Blacklist carrier: azione coordinata PAOLO + GIULIA.
        
        Steps:
        1. PAOLO: Failover di tutte le shipment attive
        2. GIULIA: Aggiorna reputazione carrier
        3. Update database: marca carrier come inattivo
        
        Args:
            carrier_id: ID carrier da blacklistare
            reason: Motivo blacklist
            permanent: Se True, rimuovi definitivamente
            
        Returns:
            True se operazione completata
        """
        logger.error(
            "coordinated_blacklist_initiated",
            carrier_id=carrier_id,
            reason=reason,
            permanent=permanent
        )
        
        try:
            async with get_db_session() as db:
                from api.models import Corriere, Spedizione
                from sqlalchemy import select, update
                
                # Ottieni info carrier
                carrier = await db.get(Corriere, carrier_id)
                if not carrier:
                    logger.error("carrier_not_found", carrier_id=carrier_id)
                    return False
                
                # STEP 1: Trova shipment attive
                query = select(Spedizione).where(
                    Spedizione.carrier_id == carrier_id,
                    Spedizione.stato.notin_(["delivered", "cancelled"])
                )
                result = await db.execute(query)
                active_shipments = result.scalars().all()
                
                affected_ids = [s.id for s in active_shipments]
                
                # STEP 2: PAOLO failovera ogni shipment
                failover_results = []
                for shipment in active_shipments:
                    result = await self.paolo.execute_failover(
                        shipment_id=shipment.id,
                        reason=f"Carrier blacklisted: {reason}",
                        admin_override=True  # Bypass limiti per emergenza
                    )
                    failover_results.append(result)
                    
                    # Notifica orchestratore dell'evento
                    await self.emit_event(
                        event_type="failover_executed",
                        source_agent="orchestrator",
                        payload={
                            "shipment_id": str(shipment.id),
                            "old_carrier_id": carrier_id,
                            "success": result.success
                        }
                    )
                
                # STEP 3: GIULIA aggiorna reputazione (se ci sono dispute aperte)
                # In produzione: chiama metodo specifico
                
                # STEP 4: Disabilita carrier
                carrier.attivo = False
                carrier.affidabilita = 0
                if permanent:
                    carrier.nome = f"[BLACKLISTED] {carrier.nome}"
                
                await db.commit()
                
                # Log azione
                action = BlacklistAction(
                    carrier_id=carrier_id,
                    carrier_name=carrier.nome,
                    reason=reason,
                    affected_shipments=affected_ids,
                    failover_results=failover_results,
                    permanent=permanent,
                    executed_at=datetime.utcnow()
                )
                self._blacklist_history.append(action)
                
                logger.info(
                    "blacklist_completed",
                    carrier_id=carrier_id,
                    affected_shipments=len(affected_ids),
                    successful_failovers=sum(1 for r in failover_results if r.success)
                )
                
                return True
                
        except Exception as e:
            logger.error("blacklist_failed", carrier_id=carrier_id, error=str(e))
            return False
    
    async def emit_event(
        self,
        event_type: str,
        source_agent: str,
        payload: Dict[str, Any]
    ):
        """Emette evento nel sistema swarm."""
        event = SwarmEvent(
            event_type=event_type,
            source_agent=source_agent,
            payload=payload
        )
        
        await self._event_queue.put(event)
        
        logger.debug(
            "event_emitted",
            event_type=event_type,
            source=source_agent
        )
    
    def get_swarm_stats(self) -> Dict[str, Any]:
        """Statistiche sistema swarm."""
        return {
            "running": self._running,
            "events_queued": self._event_queue.qsize(),
            "events_processed": len(self._event_history),
            "blacklist_actions": len(self._blacklist_history),
            "carrier_dispute_counts": self._carrier_dispute_counts,
            "carrier_failover_counts": self._carrier_failover_counts,
            "thresholds": {
                "fraud_threshold": self._fraud_threshold,
                "failover_threshold": self._failover_threshold
            }
        }
    
    def get_blacklist_history(self) -> List[Dict[str, Any]]:
        """Storico azioni blacklist."""
        return [
            {
                "carrier_id": a.carrier_id,
                "carrier_name": a.carrier_name,
                "reason": a.reason,
                "affected_shipments": [str(s) for s in a.affected_shipments],
                "successful_failovers": sum(1 for r in a.failover_results if hasattr(r, 'success') and r.success),
                "permanent": a.permanent,
                "executed_at": a.executed_at.isoformat()
            }
            for a in self._blacklist_history
        ]
    
    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Eventi recenti."""
        events = sorted(
            self._event_history,
            key=lambda e: e.timestamp,
            reverse=True
        )[:limit]
        
        return [
            {
                "event_type": e.event_type,
                "source_agent": e.source_agent,
                "payload": e.payload,
                "timestamp": e.timestamp.isoformat(),
                "processed": e.processed
            }
            for e in events
        ]
    
    async def coordinated_health_check(self) -> Dict[str, Any]:
        """Health check coordinato di tutto il sistema."""
        paolo_status = await self.paolo.get_status()
        giulia_stats = self.giulia.get_resolution_stats()
        
        swarm_ok = self._running and paolo_status["running"]
        
        return {
            "status": "healthy" if swarm_ok else "degraded",
            "orchestrator": {
                "running": self._running,
                "queue_size": self._event_queue.qsize()
            },
            "paolo": paolo_status,
            "giulia": giulia_stats,
            "coordination": {
                "events_tracked": len(self._event_history),
                "blacklists_executed": len(self._blacklist_history),
                "fraud_patterns_detected": len(self._carrier_dispute_counts)
            }
        }


# Singleton
_orchestrator_instance: Optional[SwarmOrchestrator] = None


def get_swarm_orchestrator() -> SwarmOrchestrator:
    """Factory per SwarmOrchestrator singleton."""
    global _orchestrator_instance
    
    if _orchestrator_instance is None:
        _orchestrator_instance = SwarmOrchestrator()
    
    return _orchestrator_instance


# Event helpers per integrazione con altri servizi

async def notify_failover_completed(
    shipment_id: UUID,
    old_carrier_id: int,
    new_carrier_id: int,
    success: bool
):
    """Notifica orchestratore di failover completato."""
    orchestrator = get_swarm_orchestrator()
    await orchestrator.emit_event(
        event_type="failover_executed",
        source_agent="paolo",
        payload={
            "shipment_id": str(shipment_id),
            "old_carrier_id": old_carrier_id,
            "new_carrier_id": new_carrier_id,
            "success": success
        }
    )


async def notify_fraud_detected(
    carrier_id: int,
    shipment_id: UUID,
    confidence: float
):
    """Notifica orchestratore di frode rilevata."""
    orchestrator = get_swarm_orchestrator()
    await orchestrator.emit_event(
        event_type="fraud_pattern_detected",
        source_agent="giulia",
        payload={
            "carrier_id": carrier_id,
            "shipment_id": str(shipment_id),
            "confidence": confidence
        }
    )


async def notify_carrier_degraded(
    carrier_id: int,
    on_time_rate: float
):
    """Notifica orchestratore di carrier degradato."""
    orchestrator = get_swarm_orchestrator()
    await orchestrator.emit_event(
        event_type="carrier_degraded",
        source_agent="paolo",
        payload={
            "carrier_id": carrier_id,
            "on_time_rate": on_time_rate
        }
    )