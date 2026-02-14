"""
AUTO-BROKER: Governance Engine

Decision matrix e health monitoring per governance asimmetrica.
Configurazione dinamica da YAML/DB.
"""
import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

import structlog
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db_session
from api.models.governance import (
    GovernanceConfig, 
    AgentType, 
    DecisionMode,
    OperatorPresence
)

logger = structlog.get_logger()


@dataclass
class DecisionEvaluation:
    """Risultato valutazione decisione."""
    mode: DecisionMode
    reason: str
    threshold_applied: Decimal
    requires_supervision: bool
    timeout_seconds: Optional[int]


@dataclass
class HealthStatus:
    """Stato health check governance."""
    dashboard_healthy: bool
    notifications_healthy: bool
    heartbeat_healthy: bool
    operators_available: int
    overall_healthy: bool
    degraded_reason: Optional[str]


class GovernanceEngine:
    """
    Engine per valutazione decisioni e health monitoring.
    
    Carica configurazione da YAML/DB e determina modalità
    decisionale basata su soglie dinamiche.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "/app/config/governance.yaml"
        self._config_cache: Optional[GovernanceConfig] = None
        self._config_loaded_at: Optional[datetime] = None
        self._cache_ttl_seconds = 60  # Ricarica config ogni 60s
        
        # Stato health
        self._dashboard_last_seen: Optional[datetime] = None
        self._notifications_last_seen: Optional[datetime] = None
        
        logger.info("governance_engine_initialized", config_path=self.config_path)
    
    async def evaluate_decision(
        self,
        agent: AgentType,
        amount: Decimal,
        confidence: Optional[Decimal] = None,
        shipment_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> DecisionEvaluation:
        """
        Valuta una decisione e determina modalità supervisione.
        
        Args:
            agent: Tipo agente (PAOLO/GIULIA)
            amount: Importo in EUR
            confidence: Score AI confidence (0-1)
            shipment_id: ID spedizione (per logging)
            context: Contesto aggiuntivo
            
        Returns:
            DecisionEvaluation con modalità e parametri
        """
        config = await self._get_config()
        
        if not config.governance_enabled:
            return DecisionEvaluation(
                mode=DecisionMode.FULL_AUTO,
                reason="Governance disabled",
                threshold_applied=Decimal("0"),
                requires_supervision=False,
                timeout_seconds=None
            )
        
        # Health check - se degradato, aumenta supervisione
        health = await self.check_health()
        if not health.overall_healthy:
            logger.warning(
                "health_degraded_increasing_supervision",
                reason=health.degraded_reason,
                agent=agent.value
            )
            # Degrado = sempre human-in-the-loop per importi > 1k
            if amount > Decimal("1000"):
                return DecisionEvaluation(
                    mode=DecisionMode.HUMAN_IN_THE_LOOP,
                    reason=f"Health degraded: {health.degraded_reason}",
                    threshold_applied=Decimal("1000"),
                    requires_supervision=True,
                    timeout_seconds=None
                )
        
        # Orario e festività
        time_restriction = self._check_time_restrictions(config)
        if time_restriction:
            return DecisionEvaluation(
                mode=DecisionMode.HUMAN_IN_THE_LOOP,
                reason=f"Time restriction: {time_restriction}",
                threshold_applied=Decimal("0"),
                requires_supervision=True,
                timeout_seconds=None
            )
        
        # Determina modalità basata su soglie
        mode = config.get_threshold_for_agent(agent.value, amount)
        
        # Per GIULIA, considera anche confidence
        if agent == AgentType.GIULIA and confidence is not None:
            mode = self._apply_giulia_confidence_rules(
                config, amount, confidence, mode
            )
        
        # Costruisci risposta
        if mode == DecisionMode.FULL_AUTO:
            return DecisionEvaluation(
                mode=mode,
                reason=f"Amount {amount} <= threshold",
                threshold_applied=self._get_threshold_for_mode(config, agent, mode),
                requires_supervision=False,
                timeout_seconds=None
            )
        
        elif mode == DecisionMode.HUMAN_ON_THE_LOOP:
            return DecisionEvaluation(
                mode=mode,
                reason=f"Amount {amount} in hot-standby range",
                threshold_applied=self._get_threshold_for_mode(config, agent, mode),
                requires_supervision=True,
                timeout_seconds=config.paolo_veto_window_seconds if agent == AgentType.PAOLO else 60
            )
        
        elif mode == DecisionMode.HUMAN_IN_THE_LOOP:
            return DecisionEvaluation(
                mode=mode,
                reason=f"Amount {amount} requires pre-authorization",
                threshold_applied=self._get_threshold_for_mode(config, agent, mode),
                requires_supervision=True,
                timeout_seconds=None
            )
        
        else:  # DUAL_CONTROL
            return DecisionEvaluation(
                mode=mode,
                reason=f"Amount {amount} requires dual approval",
                threshold_applied=self._get_threshold_for_mode(config, agent, mode),
                requires_supervision=True,
                timeout_seconds=None
            )
    
    async def check_health(self) -> HealthStatus:
        """
        Health check completo sistema governance.
        
        Verifica:
        - Dashboard online (heartbeat recente)
        - Notification service operativo
        - Operatori disponibili
        
        Returns:
            HealthStatus con dettagli
        """
        now = datetime.utcnow()
        
        # Check dashboard (ultimo heartbeat < 30s)
        dashboard_healthy = False
        if self._dashboard_last_seen:
            seconds_since = (now - self._dashboard_last_seen).total_seconds()
            dashboard_healthy = seconds_since < 30
        
        # Check notifications (ultimo ping < 60s)
        notifications_healthy = False
        if self._notifications_last_seen:
            seconds_since = (now - self._notifications_last_seen).total_seconds()
            notifications_healthy = seconds_since < 60
        
        # Check operatori disponibili
        operators_available = await self._count_available_operators()
        heartbeat_healthy = operators_available > 0
        
        # Overall health
        overall = dashboard_healthy and notifications_healthy and heartbeat_healthy
        
        # Determina ragione degrado
        degraded_reason = None
        if not overall:
            reasons = []
            if not dashboard_healthy:
                reasons.append("dashboard_down")
            if not notifications_healthy:
                reasons.append("notifications_down")
            if not heartbeat_healthy:
                reasons.append("no_operators_available")
            degraded_reason = "; ".join(reasons)
        
        return HealthStatus(
            dashboard_healthy=dashboard_healthy,
            notifications_healthy=notifications_healthy,
            heartbeat_healthy=heartbeat_healthy,
            operators_available=operators_available,
            overall_healthy=overall,
            degraded_reason=degraded_reason
        )
    
    async def register_dashboard_heartbeat(self):
        """Registra heartbeat da War Room Dashboard."""
        self._dashboard_last_seen = datetime.utcnow()
        logger.debug("dashboard_heartbeat_registered")
    
    async def register_notification_heartbeat(self):
        """Registra heartbeat da Notification Service."""
        self._notifications_last_seen = datetime.utcnow()
        logger.debug("notification_heartbeat_registered")
    
    async def update_operator_presence(
        self,
        operator_id: str,
        is_online: bool,
        dashboard_url: Optional[str] = None,
        can_receive_urgent: bool = True
    ):
        """
        Aggiorna presenza operatore.
        
        Args:
            operator_id: ID operatore
            is_online: Stato online
            dashboard_url: URL sessione attiva
            can_receive_urgent: Può ricevere notifiche urgenti
        """
        async with get_db_session() as db:
            from uuid import UUID
            
            # Cerca presenza esistente
            result = await db.execute(
                select(OperatorPresence).where(
                    OperatorPresence.operator_id == UUID(operator_id)
                )
            )
            presence = result.scalar_one_or_none()
            
            if presence:
                presence.is_online = is_online
                presence.last_heartbeat = datetime.utcnow()
                presence.dashboard_url = dashboard_url
                presence.can_receive_urgent = can_receive_urgent
            else:
                presence = OperatorPresence(
                    operator_id=UUID(operator_id),
                    is_online=is_online,
                    last_heartbeat=datetime.utcnow(),
                    dashboard_url=dashboard_url,
                    can_receive_urgent=can_receive_urgent
                )
                db.add(presence)
            
            await db.commit()
    
    async def reload_config(self) -> GovernanceConfig:
        """
        Forza ricaricamento configurazione.
        
        Prova prima da DB, poi da YAML se DB non disponibile.
        
        Returns:
            GovernanceConfig caricata
        """
        try:
            # Prova da DB
            async with get_db_session() as db:
                result = await db.execute(
                    select(GovernanceConfig).where(
                        GovernanceConfig.environment == "production"
                    )
                )
                config = result.scalar_one_or_none()
                
                if config:
                    self._config_cache = config
                    self._config_loaded_at = datetime.utcnow()
                    logger.info("config_loaded_from_db")
                    return config
        
        except Exception as e:
            logger.warning("db_config_load_failed", error=str(e))
        
        # Fallback a YAML
        try:
            config = self._load_config_from_yaml()
            self._config_cache = config
            self._config_loaded_at = datetime.utcnow()
            logger.info("config_loaded_from_yaml")
            return config
        
        except Exception as e:
            logger.error("yaml_config_load_failed", error=str(e))
            # Fallback a default
            return GovernanceConfig()
    
    # ============== Metodi privati ==============
    
    async def _get_config(self) -> GovernanceConfig:
        """Recupera config con caching."""
        if self._config_cache is None:
            return await self.reload_config()
        
        # Verifica TTL
        if self._config_loaded_at:
            age = (datetime.utcnow() - self._config_loaded_at).total_seconds()
            if age > self._cache_ttl_seconds:
                logger.debug("config_cache_expired_reloading")
                return await self.reload_config()
        
        return self._config_cache
    
    def _load_config_from_yaml(self) -> GovernanceConfig:
        """Carica configurazione da file YAML."""
        path = Path(self.config_path)
        
        if not path.exists():
            logger.warning("yaml_config_not_found_using_defaults", path=str(path))
            return GovernanceConfig()
        
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        
        return GovernanceConfig(
            governance_enabled=data.get('governance_enabled', False),
            paolo_full_auto_max_eur=Decimal(str(data.get('paolo_full_auto_max_eur', 5000))),
            paolo_hot_standby_max_eur=Decimal(str(data.get('paolo_hot_standby_max_eur', 10000))),
            paolo_veto_window_seconds=data.get('paolo_veto_window_seconds', 60),
            giulia_full_auto_max_eur=Decimal(str(data.get('giulia_full_auto_max_eur', 1000))),
            giulia_fast_track_confidence_min=Decimal(str(data.get('giulia_fast_track_confidence_min', 0.95))),
        )
    
    def _check_time_restrictions(self, config: GovernanceConfig) -> Optional[str]:
        """
        Verifica restrizioni orarie.
        
        Returns:
            Motivazione restrizione o None
        """
        now = datetime.utcnow()
        hour = now.hour
        weekday = now.weekday()  # 0=Lunedì, 6=Domenica
        
        # Parse business hours
        start_h, start_m = map(int, config.business_hours_start.split(':'))
        end_h, end_m = map(int, config.business_hours_end.split(':'))
        
        is_business_hours = start_h <= hour < end_h
        is_weekend = weekday >= 5
        
        if is_weekend and config.weekend_policy == "emergency_only":
            return "weekend_emergency_only"
        
        if not is_business_hours and config.holidays_policy == "human_in_loop_for_all":
            return "outside_business_hours"
        
        return None
    
    def _apply_giulia_confidence_rules(
        self,
        config: GovernanceConfig,
        amount: Decimal,
        confidence: Decimal,
        current_mode: str
    ) -> str:
        """
        Applica regole confidence-specifiche per GIULIA.
        
        High confidence + low amount = può passare a human-on-the-loop
        """
        if current_mode == DecisionMode.HUMAN_IN_THE_LOOP:
            # Verifica se qualifica per fast-track
            if (amount <= config.giulia_fast_track_max_eur and 
                confidence >= config.giulia_fast_track_confidence_min):
                return DecisionMode.HUMAN_ON_THE_LOOP
        
        return current_mode
    
    def _get_threshold_for_mode(
        self,
        config: GovernanceConfig,
        agent: AgentType,
        mode: str
    ) -> Decimal:
        """Recupera soglia applicata per modalità."""
        if agent == AgentType.PAOLO:
            if mode == DecisionMode.FULL_AUTO:
                return config.paolo_full_auto_max_eur
            elif mode == DecisionMode.HUMAN_ON_THE_LOOP:
                return config.paolo_hot_standby_max_eur
            else:
                return config.paolo_human_in_loop_max_eur
        else:  # GIULIA
            if mode == DecisionMode.FULL_AUTO:
                return config.giulia_full_auto_max_eur
            elif mode == DecisionMode.HUMAN_ON_THE_LOOP:
                return config.giulia_fast_track_max_eur
            else:
                return config.giulia_human_in_loop_max_eur
    
    async def _count_available_operators(self) -> int:
        """Conta operatori disponibili (online + recent heartbeat)."""
        try:
            async with get_db_session() as db:
                result = await db.execute(
                    select(OperatorPresence).where(
                        OperatorPresence.is_online == True
                    )
                )
                presences = result.scalars().all()
                
                available = sum(1 for p in presences if p.is_available)
                return available
        
        except Exception as e:
            logger.error("operator_count_failed", error=str(e))
            return 0


# Singleton
_governance_engine_instance: Optional[GovernanceEngine] = None


def get_governance_engine(config_path: Optional[str] = None) -> GovernanceEngine:
    """Factory per GovernanceEngine singleton."""
    global _governance_engine_instance
    
    if _governance_engine_instance is None:
        _governance_engine_instance = GovernanceEngine(config_path)
    
    return _governance_engine_instance