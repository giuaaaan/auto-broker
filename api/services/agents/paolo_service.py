"""
AUTO-BROKER: PAOLO Agent - Carrier Failover Specialist

PAOLO (Preventive Automated Operations & Logistics Orchestrator)
monitora carrier performance ed esegue failover atomici quando necessario.

Responsabilità:
- Monitoraggio continuo on_time_rate (ogni 5 min)
- Identificazione shipment a rischio
- Failover atomico (DB + Blockchain)
- Notifiche automatiche clienti

Architettura:
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Monitor   │───→│   Analyze   │───→│   Execute   │
│ (5min cron) │    │   Risk?     │    │  Failover   │
└─────────────┘    └─────────────┘    └─────────────┘
"""
import asyncio
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID

import structlog
from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db_session
from api.models import Spedizione, Corriere, CarrierChange

logger = structlog.get_logger()

# Config
FAILOVER_THRESHOLD = float(os.getenv("FAILOVER_THRESHOLD", "90.0"))  # on_time_rate %
CHECK_INTERVAL_SECONDS = int(os.getenv("PAOLO_CHECK_INTERVAL", "300"))  # 5 min
FAILOVER_TIMEOUT_MINUTES = int(os.getenv("FAILOVER_TIMEOUT", "30"))
AUTO_FAILOVER_LIMIT_EUR = int(os.getenv("AUTO_FAILOVER_LIMIT", "10000"))


@dataclass
class RiskAssessment:
    """Valutazione rischio carrier."""
    carrier_id: int
    carrier_name: str
    on_time_rate: float
    risk_level: str  # "low", "medium", "high", "critical"
    affected_shipments: List[UUID]
    reason: str


@dataclass
class FailoverResult:
    """Risultato operazione failover."""
    success: bool
    shipment_id: UUID
    old_carrier_id: int
    new_carrier_id: int
    old_carrier_name: str
    new_carrier_name: str
    tx_hash: Optional[str]
    error_message: Optional[str]
    executed_at: datetime
    idempotent: bool = False  # True se già eseguito


@dataclass
class AlternativeCarrier:
    """Carrier alternativo candidato."""
    carrier_id: int
    carrier_name: str
    on_time_rate: float
    cost_multiplier: float
    available_in_hours: float
    score: float


class PaoloAgent:
    """
    Agent autonomo per carrier failover.
    
    Flusso:
    1. Monitor → Controlla metriche carrier ogni 5 min
    2. Analyze → Identifica shipment a rischio
    3. Source → Trova carrier alternativo (< 2h disponibilità)
    4. Execute → Failover atomico (DB + Blockchain)
    5. Notify → Informa cliente
    """
    
    def __init__(self):
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._executed_failovers: Dict[UUID, FailoverResult] = {}  # Per idempotenza
        self._circuit_breaker_failures = 0
        self._circuit_breaker_threshold = 5
        
        logger.info("paolo_agent_initialized")
    
    async def start_monitoring(self):
        """Avvia loop monitoraggio continuo."""
        if self.running:
            logger.warning("paolo_monitoring_already_running")
            return
        
        self.running = True
        self._task = asyncio.create_task(self._monitoring_loop())
        logger.info("paolo_monitoring_started", interval_sec=CHECK_INTERVAL_SECONDS)
    
    async def stop_monitoring(self):
        """Ferma loop monitoraggio."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("paolo_monitoring_stopped")
    
    async def _monitoring_loop(self):
        """Loop principale monitoraggio."""
        while self.running:
            try:
                # Circuit breaker check
                if self._circuit_breaker_failures >= self._circuit_breaker_threshold:
                    logger.error("paolo_circuit_breaker_open")
                    await asyncio.sleep(60)  # Attesa prima retry
                    continue
                
                await self.check_carrier_performance()
                self._circuit_breaker_failures = 0  # Reset su successo
                
            except Exception as e:
                logger.error("paolo_monitoring_error", error=str(e))
                self._circuit_breaker_failures += 1
            
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
    
    async def check_carrier_performance(self) -> List[RiskAssessment]:
        """
        Controlla performance carrier e identifica rischi.
        
        Returns:
            Lista carrier a rischio con shipment interessate
        """
        async with get_db_session() as db:
            # Trova carrier con performance degradata
            query = select(Corriere).where(
                and_(
                    Corriere.on_time_rate < FAILOVER_THRESHOLD,
                    Corriere.attivo == True
                )
            )
            result = await db.execute(query)
            at_risk_carriers = result.scalars().all()
            
            risk_assessments = []
            
            for carrier in at_risk_carriers:
                # Trova shipment attive con questo carrier
                shipments_query = select(Spedizione).where(
                    and_(
                        Spedizione.carrier_id == carrier.id,
                        Spedizione.stato.notin_(["delivered", "cancelled"])
                    )
                )
                shipments_result = await db.execute(shipments_query)
                shipments = shipments_result.scalars().all()
                
                if shipments:
                    # Calcola risk level
                    risk_level = self._calculate_risk_level(carrier.on_time_rate)
                    
                    assessment = RiskAssessment(
                        carrier_id=carrier.id,
                        carrier_name=carrier.nome,
                        on_time_rate=float(carrier.on_time_rate or 0),
                        risk_level=risk_level,
                        affected_shipments=[s.id for s in shipments],
                        reason=f"on_time_rate {carrier.on_time_rate}% < threshold {FAILOVER_THRESHOLD}%"
                    )
                    
                    risk_assessments.append(assessment)
                    
                    logger.warning(
                        "paolo_carrier_risk_detected",
                        carrier_id=carrier.id,
                        carrier_name=carrier.nome,
                        on_time_rate=carrier.on_time_rate,
                        affected_count=len(shipments)
                    )
                    
                    # Esegui failover per shipment critiche
                    if risk_level in ["high", "critical"]:
                        for shipment in shipments:
                            await self.execute_failover(
                                shipment_id=shipment.id,
                                reason=f"Carrier performance degraded: {carrier.on_time_rate}% on-time"
                            )
            
            return risk_assessments
    
    def _calculate_risk_level(self, on_time_rate: float) -> str:
        """Calcola livello rischio da on_time_rate."""
        if on_time_rate < 70:
            return "critical"
        elif on_time_rate < 80:
            return "high"
        elif on_time_rate < 90:
            return "medium"
        return "low"
    
    async def find_alternative_carrier(
        self,
        shipment_id: UUID,
        max_response_hours: float = 2.0,
        exclude_carrier_id: Optional[int] = None
    ) -> Optional[AlternativeCarrier]:
        """
        Trova carrier alternativo disponibile.
        
        Args:
            shipment_id: ID shipment da spostare
            max_response_hours: Massimo tempo attesa
            exclude_carrier_id: Carrier da escludere
            
        Returns:
            Miglior carrier alternativo o None
        """
        async with get_db_session() as db:
            # Ottieni dettagli shipment
            shipment = await db.get(Spedizione, shipment_id)
            if not shipment:
                logger.error("shipment_not_found", shipment_id=str(shipment_id))
                return None
            
            # Trova carrier disponibili
            query = select(Corriere).where(
                and_(
                    Corriere.attivo == True,
                    Corriere.on_time_rate >= FAILOVER_THRESHOLD,
                    Corriere.id != exclude_carrier_id if exclude_carrier_id else True
                )
            )
            result = await db.execute(query)
            available_carriers = result.scalars().all()
            
            if not available_carriers:
                logger.warning("no_alternative_carriers_available")
                return None
            
            # Score e rank carrier
            candidates = []
            for carrier in available_carriers:
                # Simula disponibilità (in produzione: API carrier real-time)
                available_in = await self._check_carrier_availability(carrier.id)
                
                if available_in <= max_response_hours:
                    # Calcola score (on_time_rate pesato per disponibilità)
                    score = carrier.on_time_rate * (1 - (available_in / 24))
                    
                    candidates.append(AlternativeCarrier(
                        carrier_id=carrier.id,
                        carrier_name=carrier.nome,
                        on_time_rate=float(carrier.on_time_rate),
                        cost_multiplier=1.0,  # TODO: calcola da pricing
                        available_in_hours=available_in,
                        score=score
                    ))
            
            if not candidates:
                logger.warning("no_carriers_available_in_timeframe", max_hours=max_response_hours)
                return None
            
            # Ritorna miglior candidato
            best = max(candidates, key=lambda c: c.score)
            
            logger.info(
                "alternative_carrier_found",
                shipment_id=str(shipment_id),
                carrier_id=best.carrier_id,
                carrier_name=best.carrier_name,
                available_in=best.available_in_hours
            )
            
            return best
    
    async def _check_carrier_availability(self, carrier_id: int) -> float:
        """Controlla disponibilità carrier (ore). In produzione: API reale."""
        # Simulazione: random tra 0.5 e 4 ore
        import random
        return random.uniform(0.5, 4.0)
    
    async def execute_failover(
        self,
        shipment_id: UUID,
        reason: str,
        admin_override: bool = False
    ) -> FailoverResult:
        """
        Esegue failover atomico a nuovo carrier.
        
        Pattern Saga:
        1. Trova carrier alternativo
        2. Update database (con rollback capability)
        3. Update blockchain
        4. Se blockchain fallisce → rollback DB
        5. Notifica cliente
        
        Args:
            shipment_id: ID shipment
            reason: Motivo failover
            admin_override: Se True, bypass limiti auto-failover
            
        Returns:
            FailoverResult con esito
        """
        # Check idempotenza
        if shipment_id in self._executed_failovers:
            existing = self._executed_failovers[shipment_id]
            logger.info("failover_already_executed", shipment_id=str(shipment_id))
            return FailoverResult(
                success=True,
                shipment_id=shipment_id,
                old_carrier_id=existing.old_carrier_id,
                new_carrier_id=existing.new_carrier_id,
                old_carrier_name=existing.old_carrier_name,
                new_carrier_name=existing.new_carrier_name,
                tx_hash=existing.tx_hash,
                error_message=None,
                executed_at=existing.executed_at,
                idempotent=True
            )
        
        async with get_db_session() as db:
            # Ottieni shipment
            shipment = await db.get(Spedizione, shipment_id)
            if not shipment:
                return FailoverResult(
                    success=False,
                    shipment_id=shipment_id,
                    old_carrier_id=0,
                    new_carrier_id=0,
                    old_carrier_name="",
                    new_carrier_name="",
                    tx_hash=None,
                    error_message="Shipment not found",
                    executed_at=datetime.utcnow()
                )
            
            old_carrier_id = shipment.carrier_id
            old_carrier = await db.get(Corriere, old_carrier_id)
            
            # Human-in-the-loop per importi alti
            shipment_value = float(shipment.prezzo_vendita or 0)
            if shipment_value > AUTO_FAILOVER_LIMIT_EUR and not admin_override:
                logger.warning(
                    "failover_requires_human_approval",
                    shipment_id=str(shipment_id),
                    value=shipment_value
                )
                await self._notify_human_approval_required(shipment_id, shipment_value)
                
                return FailoverResult(
                    success=False,
                    shipment_id=shipment_id,
                    old_carrier_id=old_carrier_id,
                    new_carrier_id=0,
                    old_carrier_name=old_carrier.nome if old_carrier else "",
                    new_carrier_name="",
                    tx_hash=None,
                    error_message=f"Human approval required for value > {AUTO_FAILOVER_LIMIT_EUR} EUR",
                    executed_at=datetime.utcnow()
                )
            
            # Trova carrier alternativo
            alternative = await self.find_alternative_carrier(
                shipment_id=shipment_id,
                exclude_carrier_id=old_carrier_id
            )
            
            if not alternative:
                # Timeout: escalation a human
                await self._escalate_to_human(shipment_id, "No alternative carrier found within 30min")
                
                return FailoverResult(
                    success=False,
                    shipment_id=shipment_id,
                    old_carrier_id=old_carrier_id,
                    new_carrier_id=0,
                    old_carrier_name=old_carrier.nome if old_carrier else "",
                    new_carrier_name="",
                    tx_hash=None,
                    error_message="No alternative carrier found within timeout",
                    executed_at=datetime.utcnow()
                )
            
            # Inizia transazione Saga
            db_success = False
            blockchain_success = False
            
            try:
                # STEP 1: Update database
                await self._update_database_for_failover(
                    db, shipment_id, old_carrier_id, alternative.carrier_id, reason
                )
                await db.commit()
                db_success = True
                
                # STEP 2: Update blockchain
                tx_hash = await self._update_blockchain_for_failover(
                    shipment_id=str(shipment_id),
                    old_carrier_wallet=old_carrier.wallet_address if old_carrier else "",
                    new_carrier_wallet="0xNEWCARRIER",  # TODO: get from DB
                    reason=reason
                )
                
                if tx_hash:
                    blockchain_success = True
                else:
                    raise Exception("Blockchain transaction failed")
                
                # STEP 3: Notifica cliente
                await self._notify_customer_of_failover(
                    shipment_id=shipment_id,
                    old_carrier_name=old_carrier.nome if old_carrier else "",
                    new_carrier_name=alternative.carrier_name
                )
                
                # Successo
                result = FailoverResult(
                    success=True,
                    shipment_id=shipment_id,
                    old_carrier_id=old_carrier_id,
                    new_carrier_id=alternative.carrier_id,
                    old_carrier_name=old_carrier.nome if old_carrier else "",
                    new_carrier_name=alternative.carrier_name,
                    tx_hash=tx_hash,
                    error_message=None,
                    executed_at=datetime.utcnow()
                )
                
                self._executed_failovers[shipment_id] = result
                
                logger.info(
                    "failover_executed_successfully",
                    shipment_id=str(shipment_id),
                    old_carrier=old_carrier.nome if old_carrier else "",
                    new_carrier=alternative.carrier_name,
                    tx_hash=tx_hash
                )
                
                return result
                
            except Exception as e:
                # Rollback se necessario
                if db_success and not blockchain_success:
                    logger.error("blockchain_failed_rollback_db", error=str(e))
                    await self._rollback_database_failover(db, shipment_id, old_carrier_id)
                
                logger.error("failover_failed", shipment_id=str(shipment_id), error=str(e))
                
                return FailoverResult(
                    success=False,
                    shipment_id=shipment_id,
                    old_carrier_id=old_carrier_id,
                    new_carrier_id=alternative.carrier_id if alternative else 0,
                    old_carrier_name=old_carrier.nome if old_carrier else "",
                    new_carrier_name=alternative.carrier_name if alternative else "",
                    tx_hash=None,
                    error_message=str(e),
                    executed_at=datetime.utcnow()
                )
    
    async def _update_database_for_failover(
        self,
        db: AsyncSession,
        shipment_id: UUID,
        old_carrier_id: int,
        new_carrier_id: int,
        reason: str
    ):
        """Update database per failover."""
        # Update shipment
        await db.execute(
            update(Spedizione)
            .where(Spedizione.id == shipment_id)
            .values(
                carrier_id=new_carrier_id,
                stato="carrier_changed",
                updated_at=datetime.utcnow()
            )
        )
        
        # Log carrier change
        change = CarrierChange(
            spedizione_id=shipment_id,
            vecchio_carrier_id=old_carrier_id,
            nuovo_carrier_id=new_carrier_id,
            motivo=reason,
            eseguito_da="paolo_agent",
            created_at=datetime.utcnow()
        )
        db.add(change)
    
    async def _rollback_database_failover(
        self,
        db: AsyncSession,
        shipment_id: UUID,
        original_carrier_id: int
    ):
        """Rollback database in caso di fallimento blockchain."""
        await db.execute(
            update(Spedizione)
            .where(Spedizione.id == shipment_id)
            .values(
                carrier_id=original_carrier_id,
                stato="failover_rollback"
            )
        )
        await db.commit()
        
        logger.warning("database_rollback_executed", shipment_id=str(shipment_id))
    
    async def _update_blockchain_for_failover(
        self,
        shipment_id: str,
        old_carrier_wallet: str,
        new_carrier_wallet: str,
        reason: str
    ) -> Optional[str]:
        """Update blockchain con nuovo carrier. Ritorna tx hash."""
        try:
            # In produzione: chiama CarrierEscrow smart contract
            # Per ora: simulazione
            
            # Simula delay blockchain
            await asyncio.sleep(0.5)
            
            # Genera fake tx hash
            tx_hash = "0x" + hashlib.sha256(
                f"{shipment_id}{new_carrier_wallet}{datetime.utcnow()}".encode()
            ).hexdigest()[:64]
            
            logger.info("blockchain_failover_simulated", tx_hash=tx_hash[:16])
            return tx_hash
            
        except Exception as e:
            logger.error("blockchain_failover_failed", error=str(e))
            return None
    
    async def _notify_customer_of_failover(
        self,
        shipment_id: UUID,
        old_carrier_name: str,
        new_carrier_name: str
    ):
        """Notifica cliente del cambio carrier."""
        # In produzione: invia email via Resend
        logger.info(
            "customer_notification_sent",
            shipment_id=str(shipment_id),
            message=f"Carrier cambiato da {old_carrier_name} a {new_carrier_name}. Nessun costo aggiuntivo."
        )
    
    async def _notify_human_approval_required(self, shipment_id: UUID, value: float):
        """Notifica che approvazione umana è richiesta."""
        logger.warning(
            "human_approval_required",
            shipment_id=str(shipment_id),
            value=value,
            channel="slack/teams"
        )
        # TODO: invia notifica Slack/Teams
    
    async def _escalate_to_human(self, shipment_id: UUID, reason: str):
        """Escalation a operatore umano."""
        logger.error(
            "escalation_to_human",
            shipment_id=str(shipment_id),
            reason=reason
        )
        # TODO: crea ticket, invia alert
    
    async def get_status(self) -> Dict[str, Any]:
        """Stato operativo di PAOLO."""
        return {
            "running": self.running,
            "check_interval_seconds": CHECK_INTERVAL_SECONDS,
            "failover_threshold": FAILOVER_THRESHOLD,
            "executed_failovers": len(self._executed_failovers),
            "circuit_breaker_failures": self._circuit_breaker_failures,
            "auto_failover_limit_eur": AUTO_FAILOVER_LIMIT_EUR
        }
    
    def get_executed_failovers(self) -> List[FailoverResult]:
        """Lista failover eseguiti."""
        return list(self._executed_failovers.values())


# Singleton
_paolo_instance: Optional[PaoloAgent] = None


def get_paolo_agent() -> PaoloAgent:
    """Factory per PaoloAgent singleton."""
    global _paolo_instance
    
    if _paolo_instance is None:
        _paolo_instance = PaoloAgent()
    
    return _paolo_instance