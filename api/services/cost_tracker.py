"""
AUTO-BROKER: Cost Tracker Service

Implementazione precisione micro-transazioni con Decimal(28,6).
Batch insert per performance, circuit breaker per API esterne.

Costi riferimento (da ADRs):
- Hume AI: 0.15 EUR/minuto (prorata per secondi)
- Retell API: 0.15 EUR/chiamata flat
- DAT iQ: 0.05 EUR/request
- Blockchain Polygon: calcolato da gas_used * gas_price_gwei
"""
import asyncio
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID, uuid4

import httpx
import structlog
from sqlalchemy import select, func, insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db_session
from api.models import CostEvent
from api.services.circuit_breaker import CircuitBreaker

logger = structlog.get_logger()

# Costanti prezzi da ADRs (EUR)
HUME_AI_COST_PER_MINUTE = Decimal("0.15")  # ADR-011
RETELL_COST_PER_CALL = Decimal("0.15")     # ADR-013  
DAT_IQ_COST_PER_REQUEST = Decimal("0.05")  # ADR-010

# Costi infrastruttura mensili (EUR)
TEAM_MONTHLY_COST = Decimal("25000.00")    # 5 FTE
INFRASTRUCTURE_BASE_MONTHLY = Decimal("31700.00")  # Da Executive Summary

# Costi nascosti
AWS_DATA_TRANSFER_COST_PER_GB = Decimal("0.09")  # $0.09/GB
BACKUP_STORAGE_COST_PER_GB = Decimal("0.10")     # ~$0.10/GB
COMPLIANCE_MONTHLY_COST = Decimal("800.00")      # €10k/anno ammortizzato
SSL_CERTIFICATES_MONTHLY = Decimal("0")          # Let's Encrypt = free

# Precisione monetaria
DECIMAL_PRECISION = Decimal("0.000001")  # 6 decimali


@dataclass
class CostBreakdown:
    """Breakdown costi per categoria."""
    hume_ai: Decimal = Decimal("0")
    retell: Decimal = Decimal("0")
    dat_iq: Decimal = Decimal("0")
    blockchain: Decimal = Decimal("0")
    infrastructure: Decimal = Decimal("0")
    data_transfer: Decimal = Decimal("0")
    backup: Decimal = Decimal("0")
    
    @property
    def total(self) -> Decimal:
        return (
            self.hume_ai + self.retell + self.dat_iq + 
            self.blockchain + self.infrastructure + 
            self.data_transfer + self.backup
        ).quantize(DECIMAL_PRECISION)


@dataclass
class FinancialProjection:
    """Proiezione finanziaria."""
    months_to_break_even: int
    runway_months: int
    cac_payback_months: float
    break_even_spedizioni: int
    monthly_burn_rate: Decimal
    revenue_required: Decimal
    is_profitable: bool


@dataclass
class BatchBufferItem:
    """Item in attesa di batch insert."""
    event_type: str
    cost_eur: Decimal
    metadata: Dict[str, Any]
    timestamp: datetime
    shipment_id: Optional[UUID] = None
    customer_id: Optional[UUID] = None


class CostTracker:
    """
    Tracker costi con precisione micro-transazioni.
    
    Features:
    - Decimal(28,6) per tutti i calcoli
    - Batch insert ogni 10 eventi
    - Circuit breaker per API esterne
    - Cache hit tracking per Hume AI savings
    """
    
    def __init__(self, batch_size: int = 10):
        self.batch_size = batch_size
        self._buffer: List[BatchBufferItem] = []
        self._buffer_lock = asyncio.Lock()
        self._circuit_breaker = CircuitBreaker(
            name="cost_tracker",
            failure_threshold=5,
            recovery_timeout=30
        )
        
        # Metriche cumulative
        self._cumulative_stats = {
            "hume_ai_minutes": Decimal("0"),
            "hume_ai_cost": Decimal("0"),
            "hume_ai_saved": Decimal("0"),  # Risparmio cache
            "retell_calls": 0,
            "retell_cost": Decimal("0"),
            "dat_iq_requests": 0,
            "dat_iq_cost": Decimal("0"),
            "blockchain_txs": 0,
            "blockchain_cost": Decimal("0"),
        }
        
        logger.info("cost_tracker_initialized", batch_size=batch_size)
    
    async def shutdown(self) -> None:
        """
        Flush rimanenti eventi su shutdown.
        
        Da chiamare quando l'applicazione si ferma per garantire
        che tutti i costi siano persistiti.
        """
        logger.info("cost_tracker_shutdown_started", buffer_size=len(self._buffer))
        await self.force_flush()
        logger.info("cost_tracker_shutdown_completed")
    
    async def track_hume_api_call(
        self,
        duration_seconds: float,
        shipment_id: Optional[UUID] = None,
        customer_id: Optional[UUID] = None,
        cache_hit: bool = False
    ) -> Decimal:
        """
        Traccia costo Hume AI con prorata per secondi.
        
        Args:
            duration_seconds: Durata chiamata in secondi
            cache_hit: Se True, costo è 0 (cache hit)
            
        Returns:
            Costo in EUR (0 se cache hit)
        """
        if cache_hit:
            # Calcola quanto avremmo speso senza cache
            potential_cost = (
                Decimal(str(duration_seconds)) / Decimal("60") * 
                HUME_AI_COST_PER_MINUTE
            ).quantize(DECIMAL_PRECISION)
            
            self._cumulative_stats["hume_ai_saved"] += potential_cost
            
            logger.debug(
                "hume_cache_hit",
                duration_sec=duration_seconds,
                saved_eur=str(potential_cost)
            )
            return Decimal("0")
        
        # Calcolo prorata: (secondi / 60) * 0.15 EUR
        duration_decimal = Decimal(str(duration_seconds))
        cost = (duration_decimal / Decimal("60") * HUME_AI_COST_PER_MINUTE)
        cost = cost.quantize(DECIMAL_PRECISION, rounding=ROUND_HALF_UP)
        
        # Aggiorna stats
        minutes_used = duration_decimal / Decimal("60")
        self._cumulative_stats["hume_ai_minutes"] += minutes_used
        self._cumulative_stats["hume_ai_cost"] += cost
        
        # Buffer per batch insert
        await self._add_to_buffer(
            event_type="hume_api_call",
            cost_eur=cost,
            metadata={
                "duration_seconds": duration_seconds,
                "minutes_prorated": float(minutes_used),
                "cache_hit": False
            },
            shipment_id=shipment_id,
            customer_id=customer_id
        )
        
        logger.debug(
            "hume_api_tracked",
            duration_sec=duration_seconds,
            cost_eur=str(cost),
            shipment_id=str(shipment_id) if shipment_id else None
        )
        
        return cost
    
    async def track_retell_call(
        self,
        shipment_id: Optional[UUID] = None,
        customer_id: Optional[UUID] = None,
        agent_type: str = "unknown"
    ) -> Decimal:
        """
        Traccia costo Retell API (flat 0.15 EUR/chiamata).
        
        Args:
            agent_type: Tipo agente (sara, marco, luigi, franco)
            
        Returns:
            Costo 0.15 EUR
        """
        cost = RETELL_COST_PER_CALL
        
        self._cumulative_stats["retell_calls"] += 1
        self._cumulative_stats["retell_cost"] += cost
        
        await self._add_to_buffer(
            event_type="retell_call",
            cost_eur=cost,
            metadata={"agent_type": agent_type},
            shipment_id=shipment_id,
            customer_id=customer_id
        )
        
        logger.debug(
            "retell_call_tracked",
            agent_type=agent_type,
            cost_eur=str(cost)
        )
        
        return cost
    
    async def track_dat_iq_request(
        self,
        shipment_id: Optional[UUID] = None,
        customer_id: Optional[UUID] = None,
        request_type: str = "market_data"
    ) -> Decimal:
        """
        Traccia costo DAT iQ (0.05 EUR/request).
        
        Args:
            request_type: Tipo di richiesta (market_data, lane_rate, etc)
            
        Returns:
            Costo 0.05 EUR
        """
        cost = DAT_IQ_COST_PER_REQUEST
        
        self._cumulative_stats["dat_iq_requests"] += 1
        self._cumulative_stats["dat_iq_cost"] += cost
        
        await self._add_to_buffer(
            event_type="dat_iq_request",
            cost_eur=cost,
            metadata={"request_type": request_type},
            shipment_id=shipment_id,
            customer_id=customer_id
        )
        
        return cost
    
    async def track_blockchain_tx(
        self,
        gas_used: int,
        gas_price_gwei: int,
        shipment_id: Optional[UUID] = None,
        tx_type: str = "unknown"
    ) -> Decimal:
        """
        Traccia costo transazione blockchain Polygon.
        
        Formula: (gas_used * gas_price_gwei) / 10^9 * MATIC_price_EUR
        Assumendo MATIC ~0.50 EUR per semplicità
        
        Args:
            gas_used: Gas consumato dalla tx
            gas_price_gwei: Prezzo gas in gwei
            tx_type: Tipo transazione (delivery, dispute, etc)
            
        Returns:
            Costo in EUR
        """
        # Calcolo costo MATIC
        gas_cost_matic = (
            Decimal(gas_used) * Decimal(gas_price_gwei)
        ) / Decimal("1000000000")  # 10^9
        
        # Converzione EUR (assumendo MATIC = 0.50 EUR)
        MATIC_PRICE_EUR = Decimal("0.50")
        cost = (gas_cost_matic * MATIC_PRICE_EUR).quantize(DECIMAL_PRECISION)
        
        self._cumulative_stats["blockchain_txs"] += 1
        self._cumulative_stats["blockchain_cost"] += cost
        
        await self._add_to_buffer(
            event_type="blockchain_tx",
            cost_eur=cost,
            metadata={
                "gas_used": gas_used,
                "gas_price_gwei": gas_price_gwei,
                "tx_type": tx_type,
                "matic_cost": float(gas_cost_matic)
            },
            shipment_id=shipment_id
        )
        
        logger.debug(
            "blockchain_tx_tracked",
            gas_used=gas_used,
            gas_price_gwei=gas_price_gwei,
            cost_eur=str(cost)
        )
        
        return cost
    
    async def track_infrastructure_cost(
        self,
        category: str,
        cost_eur: Decimal,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Traccia costo infrastruttura (EKS, RDS, Redis, etc).
        
        Usato per tracking costi fissi mensili allocati per giorno.
        """
        await self._add_to_buffer(
            event_type=f"infrastructure_{category}",
            cost_eur=cost_eur,
            metadata=metadata or {}
        )
    
    async def track_data_transfer(
        self,
        gb_transferred: float,
        direction: str = "egress"
    ) -> Decimal:
        """
        Traccia costo data transfer AWS.
        
        Args:
            gb_transferred: GB trasferiti
            direction: 'egress' o 'ingress'
            
        Returns:
            Costo in EUR
        """
        if direction == "ingress":
            return Decimal("0")  # Ingress gratuito
        
        cost = (
            Decimal(str(gb_transferred)) * AWS_DATA_TRANSFER_COST_PER_GB
        ).quantize(DECIMAL_PRECISION)
        
        await self._add_to_buffer(
            event_type="data_transfer",
            cost_eur=cost,
            metadata={
                "gb_transferred": gb_transferred,
                "direction": direction
            }
        )
        
        return cost
    
    async def _add_to_buffer(
        self,
        event_type: str,
        cost_eur: Decimal,
        metadata: Dict[str, Any],
        shipment_id: Optional[UUID] = None,
        customer_id: Optional[UUID] = None
    ) -> None:
        """Aggiunge evento al buffer e flusha se necessario."""
        async with self._buffer_lock:
            item = BatchBufferItem(
                event_type=event_type,
                cost_eur=cost_eur,
                metadata=metadata,
                timestamp=datetime.utcnow(),
                shipment_id=shipment_id,
                customer_id=customer_id
            )
            self._buffer.append(item)
            
            if len(self._buffer) >= self.batch_size:
                await self._flush_buffer()
    
    async def _flush_buffer(self) -> None:
        """Flush buffer nel database con batch insert."""
        if not self._buffer:
            return
        
        items_to_insert = self._buffer[:]
        self._buffer = []
        
        try:
            async with get_db_session() as db:
                values = []
                for item in items_to_insert:
                    values.append({
                        "id": uuid4(),
                        "timestamp": item.timestamp,
                        "event_type": item.event_type,
                        "shipment_id": item.shipment_id,
                        "customer_id": item.customer_id,
                        "cost_eur": item.cost_eur,
                        "provider": item.event_type.split("_")[0],
                        "metadata": item.metadata
                    })
                
                await db.execute(insert(CostEvent), values)
                await db.commit()
                
                logger.info(
                    "cost_events_batch_inserted",
                    count=len(items_to_insert)
                )
                
        except Exception as e:
            logger.error("cost_batch_insert_failed", error=str(e))
            # Re-queue items
            async with self._buffer_lock:
                self._buffer = items_to_insert + self._buffer
    
    async def force_flush(self) -> None:
        """Forza flush immediato del buffer."""
        async with self._buffer_lock:
            await self._flush_buffer()
    
    def get_cumulative_stats(self) -> Dict[str, Any]:
        """Ritorna statistiche cumulative."""
        return {
            **self._cumulative_stats,
            "total_api_costs": (
                self._cumulative_stats["hume_ai_cost"] +
                self._cumulative_stats["retell_cost"] +
                self._cumulative_stats["dat_iq_cost"] +
                self._cumulative_stats["blockchain_cost"]
            )
        }
    
    async def get_monthly_metrics(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Recupera metriche mensili dal database.
        
        Se year/month non specificati, usa mese corrente.
        """
        now = datetime.utcnow()
        year = year or now.year
        month = month or now.month
        
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        async with get_db_session() as db:
            # Query aggregata per provider
            result = await db.execute(
                select(
                    CostEvent.provider,
                    func.count().label("count"),
                    func.sum(CostEvent.cost_eur).label("total_cost")
                )
                .where(
                    CostEvent.timestamp >= start_date,
                    CostEvent.timestamp < end_date
                )
                .group_by(CostEvent.provider)
            )
            
            by_provider = {
                row.provider: {
                    "count": row.count,
                    "cost_eur": str(row.total_cost.quantize(DECIMAL_PRECISION))
                }
                for row in result
            }
            
            # Calcola totale
            total_cost = sum(
                Decimal(row.total_cost) for row in result
            ) if result else Decimal("0")
            
            return {
                "period": f"{year}-{month:02d}",
                "by_provider": by_provider,
                "total_cost_eur": str(total_cost.quantize(DECIMAL_PRECISION))
            }


class FinancialModel:
    """
    Modello finanziario per proiezioni e break-even analysis.
    
    Assunzioni:
    - Team fisso: €25k/mese (5 FTE)
    - Infrastructure base: €31.7k/mese
    - Margine medio: 25% (default)
    """
    
    def __init__(
        self,
        team_monthly_cost: Decimal = TEAM_MONTHLY_COST,
        infrastructure_base: Decimal = INFRASTRUCTURE_BASE_MONTHLY,
        default_margin: Decimal = Decimal("0.25")
    ):
        self.team_cost = team_monthly_cost
        self.infra_base = infrastructure_base
        self.default_margin = default_margin
        
        # Assunzioni scaling
        self.cost_per_100_spedizioni = Decimal("650")  # Variabile
    
    def calculate_break_even(
        self,
        spedizioni_mese: int,
        avg_revenue_per_sped: Decimal,
        margin_percent: Optional[Decimal] = None,
        include_team: bool = True
    ) -> FinancialProjection:
        """
        Calcola proiezioni break-even.
        
        Args:
            spedizioni_mese: Volume attuale
            avg_revenue_per_sped: Fatturato medio per spedizione
            margin_percent: Margine di profitto (default 25%)
            include_team: Se includere costi team nel calcolo
            
        Returns:
            FinancialProjection con tutte le metriche
        """
        margin = margin_percent or self.default_margin
        
        # Calcola costi mensili
        variable_cost = (
            Decimal(spedizioni_mese) / Decimal("100") * 
            self.cost_per_100_spedizioni
        )
        
        if include_team:
            fixed_cost = self.team_cost + self.infra_base
        else:
            fixed_cost = self.infra_base  # Solo infrastructure
        
        monthly_burn = fixed_cost + variable_cost
        
        # Calcola revenue e profitto
        monthly_revenue = Decimal(spedizioni_mese) * avg_revenue_per_sped
        monthly_profit = (monthly_revenue * margin) - monthly_burn
        
        # Break-even point (spedizioni necessarie)
        if margin > 0:
            profit_per_sped = avg_revenue_per_sped * margin
            break_even_sped = int((fixed_cost / profit_per_sped).quantize(Decimal("1")))
        else:
            break_even_sped = 999999
        
        # Mesi per break-even (assumendo crescita 10% mese/mese)
        if monthly_profit > 0:
            months_to_be = 1  # Già profittevole
        else:
            # Stima semplificata: quanti mesi per raggiungere break_even_sped
            current = spedizioni_mese
            months = 0
            growth_rate = Decimal("1.10")  # 10% growth
            
            while current < break_even_sped and months < 36:
                current = int(current * growth_rate)
                months += 1
            
            months_to_be = months if months < 36 else 999
        
        # Runway (assumendo cash iniziale 6 mesi burn)
        initial_cash = monthly_burn * Decimal("6")
        if monthly_profit < 0:
            runway = int((initial_cash / abs(monthly_profit)).quantize(Decimal("1")))
        else:
            runway = 999  # Infinito
        
        # CAC Payback (assumendo CAC = €4,800 da Executive Summary)
        CAC = Decimal("4800")
        ltv_per_customer = avg_revenue_per_sped * margin * Decimal("12")  # 12 mesi
        if ltv_per_customer > 0:
            cac_payback = float((CAC / ltv_per_customer * 12))
        else:
            cac_payback = 999.0
        
        return FinancialProjection(
            months_to_break_even=months_to_be,
            runway_months=runway,
            cac_payback_months=cac_payback,
            break_even_spedizioni=break_even_sped,
            monthly_burn_rate=monthly_burn.quantize(DECIMAL_PRECISION),
            revenue_required=(break_even_sped * avg_revenue_per_sped).quantize(DECIMAL_PRECISION),
            is_profitable=monthly_profit > 0
        )
    
    def simulate_scenario(
        self,
        volume_spedizioni: int,
        cache_hit_rate: float = 0.85,
        include_team: bool = True
    ) -> Dict[str, Any]:
        """
        Simula scenario con parametri specifici.
        
        Args:
            volume_spedizioni: Volume mensile
            cache_hit_rate: Hit rate semantic cache (0-1)
            include_team: Se includere costi team
            
        Returns:
            Dict con breakdown completo
        """
        # Costi variabili basati su volume
        hume_minutes = volume_spedizioni * Decimal("2")  # 2 min per spedizione
        hume_cost_without_cache = (hume_minutes * HUME_AI_COST_PER_MINUTE)
        
        # Applica cache hit rate
        cache_savings = hume_cost_without_cache * Decimal(str(cache_hit_rate))
        hume_actual_cost = hume_cost_without_cache - cache_savings
        
        retell_cost = Decimal(volume_spedizioni) * RETELL_COST_PER_CALL
        dat_iq_cost = Decimal(volume_spedizioni) * DAT_IQ_COST_PER_REQUEST
        blockchain_cost = Decimal(volume_spedizioni) * Decimal("0.50")  # Assunto
        
        variable_total = hume_actual_cost + retell_cost + dat_iq_cost + blockchain_cost
        
        # Costi fissi
        if include_team:
            fixed_total = self.team_cost + self.infra_base
        else:
            fixed_total = self.infra_base
        
        total = variable_total + fixed_total
        
        return {
            "volume_spedizioni": volume_spedizioni,
            "cache_hit_rate": cache_hit_rate,
            "include_team": include_team,
            "costs": {
                "hume_ai": {
                    "minutes": float(hume_minutes),
                    "cost_without_cache": str(hume_cost_without_cache.quantize(DECIMAL_PRECISION)),
                    "cache_savings": str(cache_savings.quantize(DECIMAL_PRECISION)),
                    "actual_cost": str(hume_actual_cost.quantize(DECIMAL_PRECISION))
                },
                "retell": {
                    "calls": volume_spedizioni,
                    "cost": str(retell_cost.quantize(DECIMAL_PRECISION))
                },
                "dat_iq": {
                    "requests": volume_spedizioni,
                    "cost": str(dat_iq_cost.quantize(DECIMAL_PRECISION))
                },
                "blockchain": str(blockchain_cost.quantize(DECIMAL_PRECISION)),
                "fixed": str(fixed_total.quantize(DECIMAL_PRECISION))
            },
            "total_monthly": str(total.quantize(DECIMAL_PRECISION)),
            "cost_per_spedizione": str((total / Decimal(volume_spedizioni)).quantize(DECIMAL_PRECISION))
        }


# Singleton per uso globale
_cost_tracker_instance: Optional[CostTracker] = None
_financial_model_instance: Optional[FinancialModel] = None


def get_cost_tracker() -> CostTracker:
    """Factory per CostTracker singleton."""
    global _cost_tracker_instance
    if _cost_tracker_instance is None:
        _cost_tracker_instance = CostTracker()
    return _cost_tracker_instance


def get_financial_model() -> FinancialModel:
    """Factory per FinancialModel singleton."""
    global _financial_model_instance
    if _financial_model_instance is None:
        _financial_model_instance = FinancialModel()
    return _financial_model_instance