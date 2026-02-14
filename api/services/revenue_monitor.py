"""
AUTO-BROKER: Revenue Monitor Service

Traccia fatturato in tempo reale, calcola MRR/ARR,
attiva componenti in base alle soglie revenue.
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID

import structlog
import yaml
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db_session
from api.models import Spedizione, Pagamento
from api.services.cost_tracker import get_cost_tracker

logger = structlog.get_logger()


@dataclass
class RevenueMetrics:
    """Metriche revenue calcolate."""
    mrr: Decimal  # Monthly Recurring Revenue
    arr: Decimal  # Annual Recurring Revenue
    last_month_revenue: Decimal
    last_3_months_avg: Decimal
    last_6_months_avg: Decimal
    ytd_revenue: Decimal
    growth_rate_mom: Decimal  # Month-over-month
    growth_rate_qoq: Decimal  # Quarter-over-quarter
    
    # Proiezioni
    projected_next_month: Decimal
    projected_3_months: Decimal
    projected_6_months: Decimal


@dataclass
class EconomicLevel:
    """Livello economico attuale o target."""
    level_id: str  # level_0_survival, level_1_bootstrap, etc
    name: str
    revenue_min: Decimal
    revenue_max: Optional[Decimal]
    max_monthly_burn: Decimal
    active_components: List[str]
    disabled_components: List[str]


@dataclass
class ActivationTrigger:
    """Trigger per attivazione livello."""
    level_id: str
    triggered: bool
    reason: str
    confidence: float  # 0-1 probabilità
    recommended_date: Optional[datetime]
    required_months: int
    consecutive_months_met: int


class RevenueMonitorService:
    """
    Servizio monitoraggio revenue e attivazione progressiva.
    
    Features:
    - Tracciamento MRR/ARR in tempo reale
    - Calcolo trend e proiezioni
    - Attivazione automatica componenti basata su soglie
    - Debounce logic (richiede mesi consecutivi)
    - Pre-warming risorse
    """
    
    def __init__(self, config_path: str = "/app/config/revenue_thresholds.yaml"):
        self.config_path = config_path
        self._config: Optional[Dict] = None
        self._config_loaded_at: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5 minuti
        
        # Stato interno
        self._current_level: Optional[str] = "level_0_survival"
        self._revenue_history: List[Tuple[datetime, Decimal]] = []
        self._activation_in_progress: bool = False
        
        # Task ricorrente
        self._monitor_task: Optional[asyncio.Task] = None
        self._running: bool = False
        
        logger.info("revenue_monitor_initialized", config_path=config_path)
    
    async def start_monitoring(self, interval_minutes: int = 60):
        """
        Avvia monitoraggio continuo.
        
        Args:
            interval_minutes: Intervallo check in minuti
        """
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(
            self._monitoring_loop(interval_minutes)
        )
        logger.info("revenue_monitor_started", interval_minutes=interval_minutes)
    
    async def stop_monitoring(self):
        """Ferma monitoraggio."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("revenue_monitor_stopped")
    
    async def _monitoring_loop(self, interval_minutes: int):
        """Loop principale monitoraggio."""
        while self._running:
            try:
                await self.check_activation_triggers()
                await asyncio.sleep(interval_minutes * 60)
            except Exception as e:
                logger.error("monitoring_loop_error", error=str(e))
                await asyncio.sleep(60)  # Retry dopo 1 minuto
    
    async def check_activation_triggers(self) -> List[ActivationTrigger]:
        """
        Verifica trigger per attivazione nuovi livelli.
        
        Returns:
            Lista trigger attivati o in prossimità
        """
        triggers = []
        config = await self._get_config()
        
        # Ottieni metriche attuali
        metrics = await self._calculate_revenue_metrics()
        current_mrr = metrics.mrr
        
        # Verifica ogni livello
        levels = [
            ("level_1_bootstrap", config.get("level_1_bootstrap", {})),
            ("level_2_growth", config.get("level_2_growth", {})),
            ("level_3_scale", config.get("level_3_scale", {})),
            ("level_4_enterprise", config.get("level_4_enterprise", {})),
        ]
        
        for level_id, level_config in levels:
            if not level_config:
                continue
            
            trigger = await self._evaluate_level_trigger(
                level_id=level_id,
                level_config=level_config,
                current_mrr=current_mrr,
                metrics=metrics
            )
            
            if trigger.triggered:
                triggers.append(trigger)
                
                # Notifica pre-activation se necessario
                await self._notify_pre_activation(trigger)
        
        return triggers
    
    async def _evaluate_level_trigger(
        self,
        level_id: str,
        level_config: Dict,
        current_mrr: Decimal,
        metrics: RevenueMetrics
    ) -> ActivationTrigger:
        """
        Valuta se un livello dovrebbe essere attivato.
        
        Implementa debounce logic: richiede mesi consecutivi.
        """
        revenue_range = level_config.get("revenue_range", {})
        min_revenue = Decimal(str(revenue_range.get("min", 0)))
        max_revenue = Decimal(str(revenue_range.get("max", 999999999)))
        
        required_months = level_config.get("required_consecutive_months", 1)
        
        # Verifica soglia revenue
        revenue_met = min_revenue <= current_mrr <= max_revenue
        
        if not revenue_met:
            return ActivationTrigger(
                level_id=level_id,
                triggered=False,
                reason=f"Revenue {current_mrr} not in range [{min_revenue}, {max_revenue}]",
                confidence=0.0,
                recommended_date=None,
                required_months=required_months,
                consecutive_months_met=0
            )
        
        # Calcola mesi consecutivi sopra soglia
        consecutive_months = await self._count_consecutive_months_above(min_revenue)
        
        # Verifica debounce
        if consecutive_months < required_months:
            # Calcola data stimata attivazione
            months_needed = required_months - consecutive_months
            estimated_date = datetime.utcnow() + timedelta(days=30 * months_needed)
            
            return ActivationTrigger(
                level_id=level_id,
                triggered=False,
                reason=f"Need {required_months} consecutive months, have {consecutive_months}",
                confidence=consecutive_months / required_months,
                recommended_date=estimated_date,
                required_months=required_months,
                consecutive_months_met=consecutive_months
            )
        
        # Trigger attivato!
        return ActivationTrigger(
            level_id=level_id,
            triggered=True,
            reason=f"Revenue {current_mrr} >= {min_revenue} for {consecutive_months} consecutive months",
            confidence=1.0,
            recommended_date=datetime.utcnow(),
            required_months=required_months,
            consecutive_months_met=consecutive_months
        )
    
    async def activate_level(
        self,
        level_id: str,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Attiva un livello economico.
        
        Args:
            level_id: ID livello da attivare
            dry_run: Se True, simula senza eseguire
            
        Returns:
            Risultato attivazione
        """
        if self._activation_in_progress:
            return {
                "success": False,
                "error": "Another activation in progress"
            }
        
        self._activation_in_progress = True
        
        try:
            config = await self._get_config()
            level_config = config.get(level_id, {})
            
            if not level_config:
                return {
                    "success": False,
                    "error": f"Level {level_id} not found"
                }
            
            # Calcola costo
            max_burn = Decimal(str(level_config.get("max_monthly_burn", 0)))
            current_metrics = await self._calculate_revenue_metrics()
            
            # Safety check: costo < 90% fatturato
            if max_burn > current_metrics.mrr * Decimal("0.90"):
                logger.error(
                    "activation_blocked_cost_too_high",
                    level_id=level_id,
                    max_burn=str(max_burn),
                    mrr=str(current_metrics.mrr)
                )
                return {
                    "success": False,
                    "error": f"Level cost {max_burn} exceeds 90% of revenue {current_metrics.mrr}",
                    "requires_manual_override": True
                }
            
            # Ottieni componenti da attivare
            components = level_config.get("auto_enable", [])
            
            result = {
                "success": True,
                "level_id": level_id,
                "dry_run": dry_run,
                "components_count": len(components),
                "components": [],
                "estimated_monthly_cost": str(max_burn)
            }
            
            if dry_run:
                # Simulazione
                for comp in components:
                    if isinstance(comp, dict):
                        comp_name = list(comp.keys())[0]
                        comp_config = comp[comp_name]
                    else:
                        comp_name = comp
                        comp_config = {}
                    
                    result["components"].append({
                        "name": comp_name,
                        "config": comp_config,
                        "status": "simulated"
                    })
            else:
                # Attivazione reale
                for comp in components:
                    try:
                        activation_result = await self._activate_component(comp)
                        result["components"].append(activation_result)
                    except Exception as e:
                        logger.error("component_activation_failed", component=comp, error=str(e))
                        result["components"].append({
                            "name": comp,
                            "status": "failed",
                            "error": str(e)
                        })
                
                # Aggiorna livello corrente
                self._current_level = level_id
                
                # Log attivazione
                await self._log_activation(level_id, result)
            
            return result
        
        finally:
            self._activation_in_progress = False
    
    async def pre_warm_resources(self, next_level: str) -> Dict[str, Any]:
        """
        Pre-riscalda risorse per prossimo livello.
        
        Crea risorse in stato "warm" (pronte ma non attive).
        
        Args:
            next_level: ID livello target
            
        Returns:
            Stato pre-warming
        """
        config = await self._get_config()
        pre_warming_config = config.get("pre_warming", {})
        strategies = pre_warming_config.get("strategies", {})
        
        results = {
            "level_id": next_level,
            "pre_warmed": [],
            "failed": []
        }
        
        for component, strategy in strategies.items():
            try:
                action = strategy.get("action")
                
                if action == "create_cluster_control_plane":
                    # Crea EKS control plane (costo ~$75/mese)
                    await self._pre_warm_kubernetes_control_plane()
                
                elif action == "label_nodes_confidential":
                    # Etichetta nodi per TEE
                    await self._pre_warm_tee_nodes()
                
                elif action == "deploy_pods_replicas_0":
                    # Deploy Vault con 0 repliche
                    await self._pre_warm_vault_pods()
                
                results["pre_warmed"].append(component)
            
            except Exception as e:
                logger.error("pre_warm_failed", component=component, error=str(e))
                results["failed"].append({"component": component, "error": str(e)})
        
        return results
    
    async def get_current_economic_level(self) -> EconomicLevel:
        """
        Ottiene livello economico attuale.
        
        Returns:
            EconomicLevel corrente
        """
        config = await self._get_config()
        
        # Default a livello 0
        level_config = config.get("level_0_survival", {})
        level_id = "level_0_survival"
        
        # Trova livello basato su revenue
        metrics = await self._calculate_revenue_metrics()
        current_mrr = metrics.mrr
        
        levels = [
            ("level_4_enterprise", config.get("level_4_enterprise", {})),
            ("level_3_scale", config.get("level_3_scale", {})),
            ("level_2_growth", config.get("level_2_growth", {})),
            ("level_1_bootstrap", config.get("level_1_bootstrap", {})),
        ]
        
        for lid, lconfig in levels:
            if not lconfig:
                continue
            
            revenue_range = lconfig.get("revenue_range", {})
            min_rev = Decimal(str(revenue_range.get("min", 0)))
            max_rev = revenue_range.get("max")
            
            if current_mrr >= min_rev:
                if max_rev is None or current_mrr <= Decimal(str(max_rev)):
                    level_config = lconfig
                    level_id = lid
                    break
        
        return EconomicLevel(
            level_id=level_id,
            name=level_config.get("name", "Unknown"),
            revenue_min=Decimal(str(level_config.get("revenue_range", {}).get("min", 0))),
            revenue_max=Decimal(str(level_config.get("revenue_range", {}).get("max", 0))) if level_config.get("revenue_range", {}).get("max") else None,
            max_monthly_burn=Decimal(str(level_config.get("max_monthly_burn", 0))),
            active_components=level_config.get("active_components", []),
            disabled_components=level_config.get("disabled_components", [])
        )
    
    async def simulate_revenue(self, revenue_amount: Decimal) -> Dict[str, Any]:
        """
        Simula cosa succederebbe con revenue X.
        
        Utile per testare soglie senza aspettare mesi reali.
        
        Args:
            revenue_amount: Revenue da simulare
            
        Returns:
            Scenario simulato
        """
        # Salva revenue reale
        real_metrics = await self._calculate_revenue_metrics()
        
        # Sovrascrivi temporaneamente
        simulated_metrics = RevenueMetrics(
            mrr=revenue_amount,
            arr=revenue_amount * 12,
            last_month_revenue=revenue_amount,
            last_3_months_avg=revenue_amount,
            last_6_months_avg=revenue_amount,
            ytd_revenue=revenue_amount,
            growth_rate_mom=Decimal("0"),
            growth_rate_qoq=Decimal("0"),
            projected_next_month=revenue_amount,
            projected_3_months=revenue_amount,
            projected_6_months=revenue_amount
        )
        
        # Trova livello corrispondente
        config = await self._get_config()
        
        level_id = "level_0_survival"
        for lid in ["level_4_enterprise", "level_3_scale", "level_2_growth", "level_1_bootstrap"]:
            lconfig = config.get(lid, {})
            revenue_range = lconfig.get("revenue_range", {})
            min_rev = Decimal(str(revenue_range.get("min", 0)))
            max_rev = revenue_range.get("max")
            
            if revenue_amount >= min_rev:
                if max_rev is None or revenue_amount <= Decimal(str(max_rev)):
                    level_id = lid
                    break
        
        # Calcola trigger
        triggers = []
        for lid in ["level_1_bootstrap", "level_2_growth", "level_3_scale", "level_4_enterprise"]:
            lconfig = config.get(lid, {})
            trigger = await self._evaluate_level_trigger(
                level_id=lid,
                level_config=lconfig,
                current_mrr=revenue_amount,
                metrics=simulated_metrics
            )
            triggers.append(trigger)
        
        return {
            "simulated_revenue": str(revenue_amount),
            "current_level": self._current_level,
            "simulated_level": level_id,
            "triggers": [
                {
                    "level_id": t.level_id,
                    "triggered": t.triggered,
                    "reason": t.reason,
                    "confidence": t.confidence
                }
                for t in triggers
            ],
            "real_metrics": {
                "mrr": str(real_metrics.mrr),
                "arr": str(real_metrics.arr)
            }
        }
    
    # ============== Metodi privati ==============
    
    async def _get_config(self) -> Dict:
        """Carica configurazione con caching."""
        if self._config is None or self._config_expired():
            try:
                with open(self.config_path, 'r') as f:
                    self._config = yaml.safe_load(f)
                self._config_loaded_at = datetime.utcnow()
            except Exception as e:
                logger.error("config_load_failed", error=str(e))
                self._config = {}
        
        return self._config
    
    def _config_expired(self) -> bool:
        """Verifica se config cache è scaduta."""
        if self._config_loaded_at is None:
            return True
        age = (datetime.utcnow() - self._config_loaded_at).total_seconds()
        return age > self._cache_ttl_seconds
    
    async def _calculate_revenue_metrics(self) -> RevenueMetrics:
        """
        Calcola metriche revenue da database.
        
        Legge pagamenti completati e calcola MRR/ARR.
        """
        async with get_db_session() as db:
            now = datetime.utcnow()
            
            # Query pagamenti ultimi 6 mesi
            six_months_ago = now - timedelta(days=180)
            
            result = await db.execute(
                select(
                    func.date_trunc('month', Pagamento.created_at).label('month'),
                    func.sum(Pagamento.amount_eur).label('revenue')
                )
                .where(
                    and_(
                        Pagamento.created_at >= six_months_ago,
                        Pagamento.status == 'completed'
                    )
                )
                .group_by(func.date_trunc('month', Pagamento.created_at))
                .order_by(func.date_trunc('month', Pagamento.created_at))
            )
            
            monthly_revenues = [(row.month, Decimal(str(row.revenue))) for row in result]
            
            if not monthly_revenues:
                return RevenueMetrics(
                    mrr=Decimal("0"),
                    arr=Decimal("0"),
                    last_month_revenue=Decimal("0"),
                    last_3_months_avg=Decimal("0"),
                    last_6_months_avg=Decimal("0"),
                    ytd_revenue=Decimal("0"),
                    growth_rate_mom=Decimal("0"),
                    growth_rate_qoq=Decimal("0"),
                    projected_next_month=Decimal("0"),
                    projected_3_months=Decimal("0"),
                    projected_6_months=Decimal("0")
                )
            
            # Calcola metriche
            last_month = monthly_revenues[-1][1] if monthly_revenues else Decimal("0")
            
            # Media 3 mesi
            last_3 = monthly_revenues[-3:] if len(monthly_revenues) >= 3 else monthly_revenues
            avg_3 = sum(r for _, r in last_3) / len(last_3) if last_3 else Decimal("0")
            
            # Media 6 mesi
            avg_6 = sum(r for _, r in monthly_revenues) / len(monthly_revenues)
            
            # YTD
            ytd_start = datetime(now.year, 1, 1)
            ytd_revenue = sum(
                r for d, r in monthly_revenues 
                if d >= ytd_start
            )
            
            # Growth rates
            if len(monthly_revenues) >= 2:
                prev_month = monthly_revenues[-2][1]
                mom_growth = (last_month - prev_month) / prev_month if prev_month > 0 else Decimal("0")
            else:
                mom_growth = Decimal("0")
            
            # Proiezioni (semplice trend lineare)
            projected_next = last_month * (Decimal("1") + mom_growth)
            projected_3 = projected_next * Decimal("3")
            projected_6 = projected_next * Decimal("6")
            
            return RevenueMetrics(
                mrr=last_month,
                arr=last_month * 12,
                last_month_revenue=last_month,
                last_3_months_avg=avg_3,
                last_6_months_avg=avg_6,
                ytd_revenue=ytd_revenue,
                growth_rate_mom=mom_growth,
                growth_rate_qoq=Decimal("0"),  # TODO: calcolare
                projected_next_month=projected_next,
                projected_3_months=projected_3,
                projected_6_months=projected_6
            )
    
    async def _count_consecutive_months_above(self, threshold: Decimal) -> int:
        """Conta mesi consecutivi sopra soglia."""
        async with get_db_session() as db:
            result = await db.execute(
                select(
                    func.date_trunc('month', Pagamento.created_at).label('month'),
                    func.sum(Pagamento.amount_eur).label('revenue')
                )
                .where(Pagamento.status == 'completed')
                .group_by(func.date_trunc('month', Pagamento.created_at))
                .order_by(func.date_trunc('month', Pagamento.created_at).desc())
            )
            
            months = [(row.month, Decimal(str(row.revenue))) for row in result]
            
            consecutive = 0
            for _, revenue in months:
                if revenue >= threshold:
                    consecutive += 1
                else:
                    break
            
            return consecutive
    
    async def _activate_component(self, component: Any) -> Dict[str, Any]:
        """Attiva un singolo componente."""
        if isinstance(component, dict):
            name = list(component.keys())[0]
            config = component[name]
        else:
            name = component
            config = {}
        
        # Qui integreremmo con ProvisioningOrchestrator
        # Per ora, log e placeholder
        logger.info("activating_component", component=name, config=config)
        
        return {
            "name": name,
            "status": "activated",
            "config": config
        }
    
    async def _pre_warm_kubernetes_control_plane(self):
        """Pre-riscalda K8s control plane."""
        logger.info("pre_warming_kubernetes_control_plane")
        # Implementazione: crea EKS cluster con 0 nodi
    
    async def _pre_warm_tee_nodes(self):
        """Pre-riscalda nodi TEE."""
        logger.info("pre_warming_tee_nodes")
        # Implementazione: etichetta nodi esistenti
    
    async def _pre_warm_vault_pods(self):
        """Pre-riscalda Vault pods."""
        logger.info("pre_warming_vault_pods")
        # Implementazione: deploy con replicas=0
    
    async def _notify_pre_activation(self, trigger: ActivationTrigger):
        """Notifica pre-activation."""
        logger.info(
            "pre_activation_notification",
            level_id=trigger.level_id,
            recommended_date=trigger.recommended_date.isoformat() if trigger.recommended_date else None
        )
    
    async def _log_activation(self, level_id: str, result: Dict):
        """Log attivazione nel database."""
        # Implementazione: scrive su tabella economic_scaling_log
        pass


# Singleton
_revenue_monitor_instance: Optional[RevenueMonitorService] = None


def get_revenue_monitor() -> RevenueMonitorService:
    """Factory per RevenueMonitorService singleton."""
    global _revenue_monitor_instance
    
    if _revenue_monitor_instance is None:
        _revenue_monitor_instance = RevenueMonitorService()
    
    return _revenue_monitor_instance