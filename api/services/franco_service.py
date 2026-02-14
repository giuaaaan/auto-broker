"""
AUTO-BROKER: FRANCO (Retention Agent) Service

Servizio per la gestione delle chiamate di retention ai clienti
7 giorni dopo la consegna della spedizione.
"""
import asyncio
import hashlib
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import UUID

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models import Spedizione, Lead, RetentionAttempt
from services.circuit_breaker import CircuitBreaker
from services.retell_service import retell_service

logger = structlog.get_logger()

# Constants
AGENT_ID_FRANCO = os.getenv("RETELL_AGENT_ID_FRANCO", "agent_franco")
MAX_CALLS_PER_HOUR = 10
RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 hour


class FrancoService:
    """
    Servizio per la gestione delle chiamate di retention.
    
    Responsabilità:
    - Identificare spedizioni consegnate 7 giorni fa
    - Chiamare i clienti tramite agente FRANCO su Retell
    - Gestire rate limiting (max 10 chiamate/ora)
    - Assicurare idempotenza (non chiamare due volte)
    - Tracciare esiti e sentiment
    
    PII Protection:
    - I numeri di telefono non vengono mai loggati in chiaro
    - Vengono usati hash SHA-256 per identificare i clienti nei log
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.circuit_breaker = CircuitBreaker(
            name="franco_retell",
            failure_threshold=5,
            recovery_timeout=60
        )
        # Semaphore per rate limiting in-memory (usare Redis in produzione)
        self._call_semaphore = asyncio.Semaphore(MAX_CALLS_PER_HOUR)
        self._call_timestamps: List[datetime] = []
    
    def _hash_identifier(self, identifier: str) -> str:
        """
        Genera hash SHA-256 per proteggere PII nei log.
        
        Args:
            identifier: Stringa da hashashare (es. telefono, email)
            
        Returns:
            Hash esadecimale dei primi 16 caratteri
        """
        return hashlib.sha256(identifier.encode()).hexdigest()[:16]
    
    async def _check_rate_limit(self) -> bool:
        """
        Verifica se il rate limit è rispettato.
        
        Returns:
            True se possiamo procedere, False se siamo sopra il limite
        """
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
        
        # Rimuovi timestamp vecchi
        self._call_timestamps = [
            ts for ts in self._call_timestamps if ts > window_start
        ]
        
        if len(self._call_timestamps) >= MAX_CALLS_PER_HOUR:
            logger.warning(
                "franco_rate_limit_exceeded",
                calls_in_window=len(self._call_timestamps),
                max_allowed=MAX_CALLS_PER_HOUR
            )
            return False
        
        return True
    
    async def _record_call_attempt(self):
        """Registra un tentativo di chiamata per il rate limiting."""
        self._call_timestamps.append(datetime.utcnow())
    
    async def _is_already_attempted(self, spedizione_id: UUID) -> bool:
        """
        Verifica se è già stato fatto un tentativo di retention per questa spedizione.
        
        Args:
            spedizione_id: ID della spedizione
            
        Returns:
            True se esiste già un tentativo, False altrimenti
        """
        result = await self.db.execute(
            select(func.count(RetentionAttempt.id)).where(
                RetentionAttempt.spedizione_id == spedizione_id
            )
        )
        count = result.scalar()
        return count > 0
    
    async def get_eligible_shipments(self) -> List[Spedizione]:
        """
        Recupera le spedizioni eleggibili per la retention.
        
        Criteri:
        - Stato 'consegnata'
        - Data consegna esattamente 7 giorni fa
        - Nessun tentativo di retention precedente
        
        Returns:
            Lista di spedizioni eleggibili
        """
        target_date = datetime.utcnow().date() - timedelta(days=7)
        day_start = datetime.combine(target_date, datetime.min.time())
        day_end = datetime.combine(target_date, datetime.max.time())
        
        # Subquery per trovare spedizioni già tentate
        subquery = select(RetentionAttempt.spedizione_id).subquery()
        
        result = await self.db.execute(
            select(Spedizione)
            .join(Lead)
            .where(Spedizione.status == "consegnata")
            .where(Spedizione.data_consegna_effettiva >= day_start)
            .where(Spedizione.data_consegna_effettiva <= day_end)
            .where(Spedizione.id.notin_(subquery))
            .where(Lead.telefono.isnot(None))  # Serve un telefono per chiamare
        )
        
        shipments = result.scalars().all()
        logger.info(
            "franco_eligible_shipments_found",
            count=len(shipments),
            target_date=target_date.isoformat()
        )
        return shipments
    
    async def process_retention(self) -> Dict[str, Any]:
        """
        Elabora le chiamate di retention per tutte le spedizioni eleggibili.
        
        Processo:
        1. Query spedizioni con consegna 7 giorni fa
        2. Per ogni spedizione, verifica idempotenza
        3. Verifica rate limiting
        4. Chiama Retell con agente FRANCO
        5. Registra il tentativo nel database
        
        Returns:
            Dict con statistiche del processo:
            - processed: numero di spedizioni elaborate
            - successful_calls: chiamate avviate con successo
            - failed_calls: chiamate fallite
            - skipped: saltate (già tentate o rate limit)
            - errors: lista errori (se presenti)
        """
        stats = {
            "processed": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "skipped": 0,
            "errors": []
        }
        
        try:
            shipments = await self.get_eligible_shipments()
            
            if not shipments:
                logger.info("franco_no_eligible_shipments")
                return stats
            
            for shipment in shipments:
                stats["processed"] += 1
                
                try:
                    # Verifica idempotenza
                    if await self._is_already_attempted(shipment.id):
                        logger.info(
                            "franco_skipped_already_attempted",
                            shipment_id=str(shipment.id)
                        )
                        stats["skipped"] += 1
                        continue
                    
                    # Verifica rate limiting
                    if not await self._check_rate_limit():
                        logger.warning(
                            "franco_skipped_rate_limit",
                            shipment_id=str(shipment.id)
                        )
                        stats["skipped"] += 1
                        continue
                    
                    # Ottieni lead associato
                    result = await self.db.execute(
                        select(Lead).where(Lead.id == shipment.lead_id)
                    )
                    lead = result.scalar_one_or_none()
                    
                    if not lead or not lead.telefono:
                        logger.warning(
                            "franco_skipped_no_phone",
                            shipment_id=str(shipment.id),
                            lead_id=str(shipment.lead_id) if shipment.lead_id else None
                        )
                        stats["skipped"] += 1
                        continue
                    
                    # Crea record tentativo
                    attempt = RetentionAttempt(
                        spedizione_id=shipment.id,
                        attempted_at=datetime.utcnow(),
                        call_outcome="pending"
                    )
                    self.db.add(attempt)
                    await self.db.commit()
                    
                    # Hash del telefono per i log
                    phone_hash = self._hash_identifier(lead.telefono)
                    
                    logger.info(
                        "franco_retention_triggered",
                        shipment_id=str(shipment.id),
                        lead_id_hash=self._hash_identifier(str(lead.id)),
                        phone_hash=phone_hash,
                        agent="franco"
                    )
                    
                    # Chiama Retell con circuit breaker
                    call_result = await self.circuit_breaker.call(
                        self._make_retention_call,
                        lead=lead,
                        shipment=shipment
                    )
                    
                    # Aggiorna record con esito
                    attempt.call_outcome = "success"
                    await self.db.commit()
                    
                    # Registra chiamata per rate limiting
                    await self._record_call_attempt()
                    
                    stats["successful_calls"] += 1
                    
                    logger.info(
                        "franco_call_initiated",
                        shipment_id=str(shipment.id),
                        call_id=call_result.get("call_id"),
                        agent="franco"
                    )
                    
                except Exception as e:
                    # Gestione errore: logga e continua con le altre
                    stats["failed_calls"] += 1
                    stats["errors"].append({
                        "shipment_id": str(shipment.id),
                        "error": str(e)
                    })
                    
                    logger.error(
                        "franco_call_failed",
                        shipment_id=str(shipment.id),
                        error=str(e),
                        error_type=type(e).__name__
                    )
                    
                    # Aggiorna record con esito fallito se esiste
                    try:
                        result = await self.db.execute(
                            select(RetentionAttempt).where(
                                RetentionAttempt.spedizione_id == shipment.id
                            )
                        )
                        attempt = result.scalar_one_or_none()
                        if attempt:
                            attempt.call_outcome = "failed"
                            await self.db.commit()
                    except Exception as db_error:
                        logger.error(
                            "franco_failed_to_update_attempt",
                            shipment_id=str(shipment.id),
                            error=str(db_error)
                        )
                    
                    continue  # Procedi con la prossima spedizione
            
            logger.info(
                "franco_retention_batch_completed",
                **stats
            )
            
        except Exception as e:
            logger.error(
                "franco_retention_batch_error",
                error=str(e),
                error_type=type(e).__name__
            )
            stats["errors"].append({"batch_error": str(e)})
        
        return stats
    
    async def _make_retention_call(
        self,
        lead: Lead,
        shipment: Spedizione
    ) -> Dict[str, Any]:
        """
        Esegue la chiamata Retell per la retention.
        
        Args:
            lead: Lead da chiamare
            shipment: Spedizione di riferimento
            
        Returns:
            Risultato della chiamata Retell
        """
        return await retell_service.create_call(
            phone_number=lead.telefono,
            agent_id=AGENT_ID_FRANCO,
            lead_id=str(lead.id),
            metadata={
                "shipment_id": str(shipment.id),
                "tracking_number": shipment.tracking_number,
                "azienda": lead.azienda,
                "nome": lead.nome,
                "agent_name": "Franco",
                "call_type": "retention"
            }
        )
    
    async def get_retention_stats(self) -> Dict[str, Any]:
        """
        Recupera statistiche sulle chiamate di retention.
        
        Returns:
            Dict con metriche:
            - total_attempts: tentativi totali
            - success_rate: tasso di successo
            - rebooking_rate: tasso di ri-prenotazione
            - recent_attempts: tentativi recenti (ultimi 7 giorni)
        """
        # Totale tentativi
        result = await self.db.execute(
            select(func.count(RetentionAttempt.id))
        )
        total_attempts = result.scalar() or 0
        
        # Per esito
        result = await self.db.execute(
            select(
                RetentionAttempt.call_outcome,
                func.count(RetentionAttempt.id)
            ).group_by(RetentionAttempt.call_outcome)
        )
        outcome_counts = {row[0]: row[1] for row in result.all()}
        
        # Tentativi con ri-prenotazione
        result = await self.db.execute(
            select(func.count(RetentionAttempt.id)).where(
                RetentionAttempt.rebooking_accepted == True
            )
        )
        rebooking_count = result.scalar() or 0
        
        # Tentativi recenti (ultimi 7 giorni)
        week_ago = datetime.utcnow() - timedelta(days=7)
        result = await self.db.execute(
            select(func.count(RetentionAttempt.id)).where(
                RetentionAttempt.created_at >= week_ago
            )
        )
        recent_attempts = result.scalar() or 0
        
        # Calcola tassi
        successful = outcome_counts.get("success", 0)
        success_rate = (successful / total_attempts * 100) if total_attempts > 0 else 0
        rebooking_rate = (rebooking_count / total_attempts * 100) if total_attempts > 0 else 0
        
        return {
            "total_attempts": total_attempts,
            "outcome_breakdown": outcome_counts,
            "success_rate_percent": round(success_rate, 2),
            "rebooking_count": rebooking_count,
            "rebooking_rate_percent": round(rebooking_rate, 2),
            "recent_attempts_7d": recent_attempts,
            "rate_limit": {
                "max_per_hour": MAX_CALLS_PER_HOUR,
                "current_window_calls": len(self._call_timestamps)
            }
        }
