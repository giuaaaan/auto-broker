"""
AUTO-BROKER: Cost Dashboard API Router

Endpoint per monitoraggio costi e proiezioni finanziarie.
"""
from decimal import Decimal
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from api.services.cost_tracker import (
    get_cost_tracker,
    get_financial_model,
    CostTracker,
    FinancialModel,
    DECIMAL_PRECISION
)

router = APIRouter(prefix="/costs", tags=["Cost Tracking"])


# ============== Pydantic Models ==============

class InfrastructureCosts(BaseModel):
    """Costi infrastruttura dettagliati."""
    compute: str = Field(..., description="EKS/GKE compute costs")
    database: str = Field(..., description="RDS PostgreSQL costs")
    cache: str = Field(..., description="Redis/ElastiCache costs")
    total: str = Field(..., description="Total infrastructure costs")


class ExternalAPIsCosts(BaseModel):
    """Costi API esterne."""
    hume_ai: Dict[str, Any] = Field(..., description="Minutes, cost, saved_by_cache")
    retell: Dict[str, Any] = Field(..., description="Calls and cost")
    dat_iq: Dict[str, Any] = Field(..., description="Requests and cost")
    blockchain: Dict[str, Any] = Field(..., description="Transactions and cost")


class TeamCosts(BaseModel):
    """Costi team."""
    ftes: int = Field(..., description="Number of FTEs")
    monthly_cost: str = Field(..., description="Total team cost per month")
    per_shipment_share: str = Field(..., description="Team cost per shipment")


class HiddenCosts(BaseModel):
    """Costi nascosti."""
    data_transfer: str = Field(..., description="AWS data transfer costs")
    backup: str = Field(..., description="Backup storage costs")
    compliance: str = Field(..., description="Compliance audit amortized cost")


class Totals(BaseModel):
    """Totali costi."""
    infrastructure_only: str = Field(..., description="Total without team costs")
    full_burn_rate: str = Field(..., description="Total with team costs")
    per_shipment: str = Field(..., description="Cost per shipment")


class CurrentMonthMetrics(BaseModel):
    """Metriche mese corrente completo."""
    infrastructure: InfrastructureCosts
    external_apis: ExternalAPIsCosts
    team: TeamCosts
    hidden_costs: HiddenCosts
    totals: Totals


class Projections(BaseModel):
    """Proiezioni finanziarie."""
    next_month_estimate: str
    break_even_at: int


class CostsMetricsResponse(BaseModel):
    """Response completo metriche costi."""
    current_month: CurrentMonthMetrics
    projections: Projections
    cache_efficiency: Optional[Dict[str, Any]] = None


class SimulateRequest(BaseModel):
    """Request simulazione scenario."""
    volume_spedizioni: int = Field(..., ge=1, le=1000000, description="Numero spedizioni mensili")
    cache_hit_rate: float = Field(default=0.85, ge=0.0, le=1.0, description="Semantic cache hit rate")
    include_team: bool = Field(default=True, description="Includere costi team (25k/mese)")
    avg_revenue_per_sped: Optional[float] = Field(default=500.0, ge=0, description="Fatturato medio per spedizione")
    margin_percent: Optional[float] = Field(default=0.25, ge=0.0, le=1.0, description="Margine di profitto")


class SimulateResponse(BaseModel):
    """Response simulazione."""
    scenario: Dict[str, Any]
    costs: Dict[str, Any]
    projections: Dict[str, Any]
    break_even_analysis: Dict[str, Any]


class BreakEvenResponse(BaseModel):
    """Response analisi break-even."""
    months_to_break_even: int
    runway_months: int
    cac_payback_months: float
    break_even_spedizioni: int
    monthly_burn_rate: str
    revenue_required: str
    is_profitable: bool


# ============== Endpoints ==============

@router.get("/metrics", response_model=CostsMetricsResponse)
async def get_costs_metrics(
    tracker: CostTracker = Depends(get_cost_tracker),
    financial: FinancialModel = Depends(get_financial_model)
) -> CostsMetricsResponse:
    """
    Dashboard costi mese corrente.
    
    Ritorna breakdown completo:
    - Hume AI: minuti usati, costo, risparmio cache
    - Retell: numero chiamate, costo
    - Infrastructure: EKS, RDS, Redis
    - Proiezioni: prossimo mese, break-even point
    """
    # Force flush per avere dati aggiornati
    await tracker.force_flush()
    
    # Stats cumulative
    stats = tracker.get_cumulative_stats()
    
    # Calcola costi infrastructure (daily allocation)
    infra_daily = financial.infra_base / Decimal("30")
    
    # Simula mese corrente con volume stimato
    estimated_spedizioni = max(100, int(stats.get("retell_calls", 0) * 1.2))
    
    # Calcola costi nascosti (stima)
    data_transfer_cost = Decimal("9.00")  # 100GB @ $0.09/GB
    backup_cost = Decimal("100.00")  # 1TB backup
    compliance_cost = Decimal("800.00")  # €10k/anno ammortizzato
    
    # Totali
    infra_only_total = (
        stats["hume_ai_cost"] + stats["retell_cost"] + 
        stats["dat_iq_cost"] + stats["blockchain_cost"] +
        Decimal("600") +  # Infrastructure base (EKS+RDS+Redis)
        data_transfer_cost + backup_cost + compliance_cost
    )
    full_burn_total = infra_only_total + financial.team_cost
    
    # Cost per shipment
    infra_per_shipment = (infra_only_total / Decimal(estimated_spedizioni)).quantize(DECIMAL_PRECISION)
    full_per_shipment = (full_burn_total / Decimal(estimated_spedizioni)).quantize(DECIMAL_PRECISION)
    team_per_shipment = (financial.team_cost / Decimal(estimated_spedizioni)).quantize(DECIMAL_PRECISION)
    
    # Break-even calcolo corretto
    # Infrastructure only: 31.7k / 125 = ~254 spedizioni
    # Full burn: 56.7k / 125 = ~454 spedizioni
    break_even_infra = int((financial.infra_base / Decimal("125")).quantize(Decimal("1")))
    break_even_full = int(((financial.team_cost + financial.infra_base) / Decimal("125")).quantize(Decimal("1")))
    
    return CostsMetricsResponse(
        current_month=CurrentMonthMetrics(
            infrastructure=InfrastructureCosts(
                compute="400.00",
                database="150.00",
                cache="50.00",
                total="600.00"
            ),
            external_apis=ExternalAPIsCosts(
                hume_ai={
                    "minutes": float(stats["hume_ai_minutes"]),
                    "cost": str(stats["hume_ai_cost"].quantize(DECIMAL_PRECISION)),
                    "saved_by_cache": str(stats["hume_ai_saved"].quantize(DECIMAL_PRECISION))
                },
                retell={
                    "calls": stats["retell_calls"],
                    "cost": str(stats["retell_cost"].quantize(DECIMAL_PRECISION))
                },
                dat_iq={
                    "requests": stats["dat_iq_requests"],
                    "cost": str(stats["dat_iq_cost"].quantize(DECIMAL_PRECISION))
                },
                blockchain={
                    "transactions": stats["blockchain_txs"],
                    "cost": str(stats["blockchain_cost"].quantize(DECIMAL_PRECISION))
                }
            ),
            team=TeamCosts(
                ftes=5,
                monthly_cost=str(financial.team_cost.quantize(DECIMAL_PRECISION)),
                per_shipment_share=str(team_per_shipment)
            ),
            hidden_costs=HiddenCosts(
                data_transfer=str(data_transfer_cost),
                backup=str(backup_cost),
                compliance=str(compliance_cost)
            ),
            totals=Totals(
                infrastructure_only=str(infra_only_total.quantize(DECIMAL_PRECISION)),
                full_burn_rate=str(full_burn_total.quantize(DECIMAL_PRECISION)),
                per_shipment=str(full_per_shipment)
            )
        ),
        projections=Projections(
            next_month_estimate=str((full_burn_total + Decimal("1000")).quantize(DECIMAL_PRECISION)),
            break_even_at=break_even_full  # 454 spedizioni con team
        ),
        cache_efficiency={
            "hit_rate_percent": 85,
            "savings_eur": str(stats["hume_ai_saved"].quantize(DECIMAL_PRECISION)),
            "efficiency_score": "A"
        }
    )


@router.post("/simulate", response_model=SimulateResponse)
async def simulate_costs(
    request: SimulateRequest,
    financial: FinancialModel = Depends(get_financial_model)
) -> SimulateResponse:
    """
    Simula scenario costi con parametri personalizzati.
    
    Utile per:
    - Pianificare scaling
    - Valutare impatto cache hit rate
    - Calcolare break-even con diversi volumi
    """
    # Simula scenario
    scenario = financial.simulate_scenario(
        volume_spedizioni=request.volume_spedizioni,
        cache_hit_rate=request.cache_hit_rate,
        include_team=request.include_team
    )
    
    # Calcola break-even
    avg_revenue = Decimal(str(request.avg_revenue_per_sped or 500.0))
    margin = Decimal(str(request.margin_percent or 0.25))
    
    projection = financial.calculate_break_even(
        spedizioni_mese=request.volume_spedizioni,
        avg_revenue_per_sped=avg_revenue,
        margin_percent=margin,
        include_team=request.include_team
    )
    
    return SimulateResponse(
        scenario={
            "volume_spedizioni": request.volume_spedizioni,
            "cache_hit_rate": request.cache_hit_rate,
            "include_team": request.include_team,
            "avg_revenue_per_sped": request.avg_revenue_per_sped
        },
        costs=scenario["costs"],
        projections={
            "total_monthly": scenario["total_monthly"],
            "cost_per_spedizione": scenario["cost_per_spedizione"]
        },
        break_even_analysis={
            "break_even_spedizioni": projection.break_even_spedizioni,
            "months_to_break_even": projection.months_to_break_even,
            "monthly_burn_rate": str(projection.monthly_burn_rate),
            "revenue_required": str(projection.revenue_required),
            "is_profitable": projection.is_profitable
        }
    )


@router.get("/break-even", response_model=BreakEvenResponse)
async def get_break_even_analysis(
    spedizioni_mese: int = Query(..., ge=1, description="Volume attuale spedizioni/mese"),
    avg_revenue_per_sped: float = Query(500.0, ge=0, description="Fatturato medio per spedizione"),
    margin_percent: float = Query(0.25, ge=0.0, le=1.0, description="Margine profitto (0-1)"),
    include_team: bool = Query(True, description="Includere costi team"),
    financial: FinancialModel = Depends(get_financial_model)
) -> BreakEvenResponse:
    """
    Analisi break-even con parametri attuali.
    
    Calcola:
    - Quante spedizioni servono per break-even
    - Mesi necessari per raggiungere profitto
    - Runway (quanti mesi di cash rimanenti)
    - CAC payback period
    """
    revenue = Decimal(str(avg_revenue_per_sped))
    margin = Decimal(str(margin_percent))
    
    projection = financial.calculate_break_even(
        spedizioni_mese=spedizioni_mese,
        avg_revenue_per_sped=revenue,
        margin_percent=margin,
        include_team=include_team
    )
    
    return BreakEvenResponse(
        months_to_break_even=projection.months_to_break_even,
        runway_months=projection.runway_months,
        cac_payback_months=projection.cac_payback_months,
        break_even_spedizioni=projection.break_even_spedizioni,
        monthly_burn_rate=str(projection.monthly_burn_rate),
        revenue_required=str(projection.revenue_required),
        is_profitable=projection.is_profitable
    )


@router.get("/monthly/{year}/{month}")
async def get_monthly_costs(
    year: int,
    month: int,
    tracker: CostTracker = Depends(get_cost_tracker)
) -> Dict[str, Any]:
    """
    Recupera costi storici per mese specifico.
    
    Esempio: /costs/monthly/2026/01
    """
    metrics = await tracker.get_monthly_metrics(year=year, month=month)
    return metrics


@router.get("/providers/{provider}")
async def get_provider_costs(
    provider: str,
    days: int = Query(30, ge=1, le=365),
    tracker: CostTracker = Depends(get_cost_tracker)
) -> Dict[str, Any]:
    """
    Dettaglio costi per provider specifico.
    
    Providers: hume, retell, dat_iq, blockchain, infrastructure
    """
    # Force flush
    await tracker.force_flush()
    
    # Recupera stats specifiche per provider
    stats = tracker.get_cumulative_stats()
    
    provider_mapping = {
        "hume": {
            "name": "Hume AI",
            "cost": stats["hume_ai_cost"],
            "usage": f"{stats['hume_ai_minutes']:.2f} min"
        },
        "retell": {
            "name": "Retell API",
            "cost": stats["retell_cost"],
            "usage": f"{stats['retell_calls']} calls"
        },
        "dat_iq": {
            "name": "DAT iQ",
            "cost": stats["dat_iq_cost"],
            "usage": f"{stats['dat_iq_requests']} requests"
        },
        "blockchain": {
            "name": "Polygon Blockchain",
            "cost": stats["blockchain_cost"],
            "usage": f"{stats['blockchain_txs']} txs"
        }
    }
    
    if provider not in provider_mapping:
        return {
            "error": f"Unknown provider: {provider}",
            "available": list(provider_mapping.keys())
        }
    
    info = provider_mapping[provider]
    return {
        "provider": info["name"],
        "period_days": days,
        "cost_eur": str(info["cost"].quantize(DECIMAL_PRECISION)),
        "usage": info["usage"],
        "avg_daily_cost": str((info["cost"] / Decimal(days)).quantize(DECIMAL_PRECISION))
    }


@router.post("/flush")
async def force_flush_buffer(
    tracker: CostTracker = Depends(get_cost_tracker)
) -> Dict[str, str]:
    """
    Forza flush immediato del buffer costi nel database.
    
    Utile per garantire che tutti i costi siano persistiti
    prima di generare report.
    """
    await tracker.force_flush()
    return {"status": "flushed", "timestamp": "success"}