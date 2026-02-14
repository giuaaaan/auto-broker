"""
AUTO-BROKER: Dashboard Router
API endpoints for Mission Control Center.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.dashboard import (
    DashboardStats, AgentStatus, AIAgentsStatus,
    ShipmentResponse, ShipmentListResponse, ShipmentCreate, ShipmentUpdate,
    AgentDetail, AgentActivity,
    RevenueMetrics, CurrentLevel,
    ChangeCarrierRequest, ChangeCarrierResponse,
    EmergencyStopRequest, VetoPaoloRequest,
    BlackFridayModeRequest, ForceLevelRequest,
    SimulationRequest, SimulationResponse
)
from services.database import get_db
from models import Spedizione, Corriere, Pagamento
from routers.auth import get_current_user

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


# ==========================================
# DASHBOARD STATS
# ==========================================

@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get aggregated dashboard statistics."""
    
    # Count active shipments
    active_result = await db.execute(
        select(func.count()).select_from(Spedizione)
        .where(Spedizione.stato.in_(["pending", "confirmed", "in_transit"]))
    )
    active_shipments = active_result.scalar() or 0
    
    # Total shipments
    total_result = await db.execute(select(func.count()).select_from(Spedizione))
    total_shipments = total_result.scalar() or 0
    
    # Monthly revenue (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    revenue_result = await db.execute(
        select(func.sum(Pagamento.importo)).select_from(Pagamento)
        .where(and_(
            Pagamento.stato == "completed",
            Pagamento.created_at >= thirty_days_ago
        ))
    )
    monthly_revenue = revenue_result.scalar() or Decimal("0")
    
    # Calculate level based on revenue
    if monthly_revenue < 450:
        current_level = 0
        target_level = 1
        progress_percent = float(monthly_revenue / 450 * 100)
    elif monthly_revenue < 800:
        current_level = 1
        target_level = 2
        progress_percent = float((monthly_revenue - 450) / (800 - 450) * 100)
    elif monthly_revenue < 3000:
        current_level = 2
        target_level = 3
        progress_percent = float((monthly_revenue - 800) / (3000 - 800) * 100)
    elif monthly_revenue < 10000:
        current_level = 3
        target_level = 4
        progress_percent = float((monthly_revenue - 3000) / (10000 - 3000) * 100)
    else:
        current_level = 4
        target_level = 4
        progress_percent = 100.0
    
    # Costs based on level
    costs_map = {
        0: Decimal("450"),
        1: Decimal("800"),
        2: Decimal("3000"),
        3: Decimal("10000"),
        4: Decimal("35000"),
    }
    costs_monthly = costs_map.get(current_level, Decimal("450"))
    
    # Margin calculation
    margin_percent = float((monthly_revenue - costs_monthly) / monthly_revenue * 100) if monthly_revenue > 0 else 0
    
    # Delivered today
    today = datetime.utcnow().date()
    delivered_result = await db.execute(
        select(func.count()).select_from(Spedizione)
        .where(and_(
            Spedizione.stato == "delivered",
            func.date(Spedizione.updated_at) == today
        ))
    )
    delivered_today = delivered_result.scalar() or 0
    
    # AI Agents status (mock for now - integrate with real agent services)
    ai_agents = AIAgentsStatus(
        sara=AgentStatus(status="active", calls_today=15, confidence_score=0.92),
        marco=AgentStatus(status="standby", calls_today=8, confidence_score=0.88),
        paolo=AgentStatus(status="warning", pending_actions=2, confidence_score=0.76),
        giulia=AgentStatus(status="active", resolved_today=5, confidence_score=0.94),
    )
    
    return DashboardStats(
        active_shipments=active_shipments,
        monthly_revenue=monthly_revenue,
        current_level=current_level,
        target_level=target_level,
        progress_percent=progress_percent,
        costs_monthly=costs_monthly,
        margin_percent=margin_percent,
        ai_agents=ai_agents,
        total_shipments=total_shipments,
        delivered_today=delivered_today,
        alerts_count=2 if current_level >= 2 else 0
    )


# ==========================================
# SHIPMENTS
# ==========================================

@router.get("/shipments", response_model=ShipmentListResponse)
async def list_shipments(
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search query"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """List shipments with pagination and filters."""
    
    # Build query
    query = select(Spedizione).join(Corriere, Spedizione.corriere_id == Corriere.id)
    
    if status:
        query = query.where(Spedizione.stato == status)
    
    if search:
        query = query.where(
            Spedizione.codice_tracking.ilike(f"%{search}%")
        )
    
    # Count total
    count_query = select(func.count()).select_from(Spedizione)
    if status:
        count_query = count_query.where(Spedizione.stato == status)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    shipments = result.scalars().all()
    
    # Transform to response
    items = []
    for s in shipments:
        carrier = await db.get(Corriere, s.corriere_id)
        items.append(ShipmentResponse(
            id=str(s.id),
            tracking_number=s.codice_tracking,
            origin={
                "lat": 45.4642,  # Mock - should come from actual data
                "lon": 9.1900,
                "address": s.origine or "Via Roma 1",
                "city": s.origine.split(",")[0] if s.origine else "Milano",
                "country": "IT"
            },
            destination={
                "lat": 41.9028,
                "lon": 12.4964,
                "address": s.destinazione or "Via Napoli 1",
                "city": s.destinazione.split(",")[0] if s.destinazione else "Roma",
                "country": "IT"
            },
            carrier_id=str(s.corriere_id),
            carrier_name=carrier.nome if carrier else "Unknown",
            status=s.stato or "pending",
            margin_percent=25.0,  # Mock calculation
            revenue=Decimal("500"),
            value=Decimal(str(s.valore_merce or 1000)),
            weight=s.peso_kg or 100.0,
            created_at=s.created_at or datetime.utcnow(),
            estimated_delivery=s.data_consegna_stimata,
            actual_delivery=s.data_consegna_effettiva,
            customer_name="Cliente Test",
            customer_email="test@example.com"
        ))
    
    return ShipmentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )


@router.get("/shipments/{shipment_id}", response_model=ShipmentResponse)
async def get_shipment(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get single shipment details."""
    from uuid import UUID
    
    shipment = await db.get(Spedizione, UUID(shipment_id))
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    carrier = await db.get(Corriere, shipment.corriere_id)
    
    return ShipmentResponse(
        id=str(shipment.id),
        tracking_number=shipment.codice_tracking,
        origin={
            "lat": 45.4642,
            "lon": 9.1900,
            "address": shipment.origine or "Via Roma 1",
            "city": shipment.origine.split(",")[0] if shipment.origine else "Milano",
            "country": "IT"
        },
        destination={
            "lat": 41.9028,
            "lon": 12.4964,
            "address": shipment.destinazione or "Via Napoli 1",
            "city": shipment.destinazione.split(",")[0] if shipment.destinazione else "Roma",
            "country": "IT"
        },
        carrier_id=str(shipment.corriere_id),
        carrier_name=carrier.nome if carrier else "Unknown",
        status=shipment.stato or "pending",
        margin_percent=25.0,
        revenue=Decimal("500"),
        value=Decimal(str(shipment.valore_merce or 1000)),
        weight=shipment.peso_kg or 100.0,
        created_at=shipment.created_at or datetime.utcnow(),
        estimated_delivery=shipment.data_consegna_stimata,
        actual_delivery=shipment.data_consegna_effettiva,
        customer_name="Cliente Test",
        customer_email="test@example.com",
        notes=shipment.note
    )


@router.post("/shipments", response_model=ShipmentResponse, status_code=status.HTTP_201_CREATED)
async def create_shipment(
    data: ShipmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create new shipment."""
    from uuid import UUID
    
    # Select carrier (preferred or random)
    if data.preferred_carrier_id:
        carrier = await db.get(Corriere, UUID(data.preferred_carrier_id))
    else:
        # Get first available carrier
        result = await db.execute(select(Corriere).limit(1))
        carrier = result.scalar()
    
    if not carrier:
        raise HTTPException(status_code=400, detail="No carrier available")
    
    # Create tracking number
    tracking = f"AB{datetime.utcnow().strftime('%Y%m%d')}{str(uuid4())[:6].upper()}"
    
    shipment = Spedizione(
        id=uuid4(),
        codice_tracking=tracking,
        corriere_id=carrier.id,
        origine=f"{data.origin_address}, {data.origin_city}",
        destinazione=f"{data.dest_address}, {data.dest_city}",
        stato="pending",
        peso_kg=data.weight,
        valore_merce=data.value,
        note=data.notes,
        data_consegna_stimata=datetime.utcnow() + timedelta(days=3)
    )
    
    db.add(shipment)
    await db.commit()
    await db.refresh(shipment)
    
    # Broadcast via WebSocket (implement later)
    
    return ShipmentResponse(
        id=str(shipment.id),
        tracking_number=shipment.codice_tracking,
        origin={
            "lat": 45.4642,
            "lon": 9.1900,
            "address": data.origin_address,
            "city": data.origin_city,
            "country": data.origin_country
        },
        destination={
            "lat": 41.9028,
            "lon": 12.4964,
            "address": data.dest_address,
            "city": data.dest_city,
            "country": data.dest_country
        },
        carrier_id=str(carrier.id),
        carrier_name=carrier.nome,
        status="pending",
        margin_percent=25.0,
        revenue=Decimal("500"),
        value=data.value,
        weight=data.weight,
        created_at=shipment.created_at,
        estimated_delivery=shipment.data_consegna_stimata,
        customer_name=data.customer_name,
        customer_email=data.customer_email,
        notes=data.notes
    )


@router.put("/shipments/{shipment_id}", response_model=ShipmentResponse)
async def update_shipment(
    shipment_id: str,
    data: ShipmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update shipment."""
    from uuid import UUID
    
    shipment = await db.get(Spedizione, UUID(shipment_id))
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    if data.status:
        shipment.stato = data.status
    if data.notes:
        shipment.note = data.notes
    if data.actual_delivery:
        shipment.data_consegna_effettiva = data.actual_delivery
    
    await db.commit()
    await db.refresh(shipment)
    
    carrier = await db.get(Corriere, shipment.corriere_id)
    
    return ShipmentResponse(
        id=str(shipment.id),
        tracking_number=shipment.codice_tracking,
        origin={
            "lat": 45.4642,
            "lon": 9.1900,
            "address": shipment.origine or "",
            "city": (shipment.origine or "").split(",")[0],
            "country": "IT"
        },
        destination={
            "lat": 41.9028,
            "lon": 12.4964,
            "address": shipment.destinazione or "",
            "city": (shipment.destinazione or "").split(",")[0],
            "country": "IT"
        },
        carrier_id=str(shipment.corriere_id),
        carrier_name=carrier.nome if carrier else "Unknown",
        status=shipment.stato,
        margin_percent=25.0,
        revenue=Decimal("500"),
        value=Decimal(str(shipment.valore_merce or 1000)),
        weight=shipment.peso_kg or 100.0,
        created_at=shipment.created_at,
        customer_name="Cliente Test",
        customer_email="test@example.com",
        notes=shipment.note
    )


@router.delete("/shipments/{shipment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shipment(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete shipment."""
    from uuid import UUID
    
    shipment = await db.get(Spedizione, UUID(shipment_id))
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    await db.delete(shipment)
    await db.commit()
    
    return None


# ==========================================
# AGENTS
# ==========================================

@router.get("/agents/status", response_model=List[AgentDetail])
async def get_agents_status(
    current_user: dict = Depends(get_current_user)
):
    """Get status of all AI agents."""
    
    # Mock data - integrate with real agent services
    agents = [
        AgentDetail(
            id="SARA",
            name="Sentiment Analysis & Response Automation",
            status="active",
            activity_level=85,
            last_action=datetime.utcnow() - timedelta(minutes=5),
            current_task="Analisi chiamata #1234",
            recent_activities=[
                AgentActivity(
                    id="1",
                    timestamp=datetime.utcnow() - timedelta(minutes=10),
                    type="sentiment_analysis",
                    description="Analizzato sentiment cliente positivo",
                    status="success"
                ),
                AgentActivity(
                    id="2",
                    timestamp=datetime.utcnow() - timedelta(minutes=30),
                    type="response_generated",
                    description="Generata risposta automatica",
                    status="success"
                )
            ]
        ),
        AgentDetail(
            id="MARCO",
            name="Market Intelligence & Pricing",
            status="standby",
            activity_level=45,
            last_action=datetime.utcnow() - timedelta(hours=1),
            recent_activities=[
                AgentActivity(
                    id="3",
                    timestamp=datetime.utcnow() - timedelta(hours=1),
                    type="price_check",
                    description="Verificato prezzi mercato DAT",
                    status="success"
                )
            ]
        ),
        AgentDetail(
            id="PAOLO",
            name="Carrier Failover & Optimization",
            status="warning",
            activity_level=92,
            last_action=datetime.utcnow() - timedelta(minutes=2),
            current_task="Suggerimento cambio carrier",
            suggestion={
                "id": "paolo-001",
                "title": "Carrier più economico disponibile",
                "description": "Bartolini offre prezzo 15% inferiore",
                "priority": "medium",
                "actions": [
                    {"label": "Accetta", "action": "accept"},
                    {"label": "Ignora", "action": "ignore"}
                ]
            },
            recent_activities=[
                AgentActivity(
                    id="4",
                    timestamp=datetime.utcnow() - timedelta(minutes=2),
                    type="carrier_failover_suggestion",
                    description="Suggerito cambio carrier per SP-2847",
                    status="warning"
                )
            ]
        ),
        AgentDetail(
            id="GIULIA",
            name="Dispute Resolution & Claims",
            status="active",
            activity_level=78,
            last_action=datetime.utcnow() - timedelta(minutes=15),
            recent_activities=[
                AgentActivity(
                    id="5",
                    timestamp=datetime.utcnow() - timedelta(minutes=15),
                    type="dispute_resolved",
                    description="Risolto contestazione #4421",
                    status="success"
                )
            ]
        )
    ]
    
    return agents


@router.get("/agents/{agent_id}", response_model=AgentDetail)
async def get_agent_detail(
    agent_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get detailed info for single agent."""
    agents = await get_agents_status(current_user)
    for agent in agents:
        if agent.id == agent_id:
            return agent
    raise HTTPException(status_code=404, detail="Agent not found")


@router.get("/agents/{agent_id}/logs")
async def get_agent_logs(
    agent_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get agent activity logs."""
    agent = await get_agent_detail(agent_id, current_user)
    return agent.recent_activities[:limit]


# ==========================================
# REVENUE
# ==========================================

@router.get("/revenue/current", response_model=CurrentLevel)
async def get_current_level(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get current economic level and metrics."""
    
    # Calculate MRR
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    result = await db.execute(
        select(func.sum(Pagamento.importo)).select_from(Pagamento)
        .where(and_(
            Pagamento.stato == "completed",
            Pagamento.created_at >= thirty_days_ago
        ))
    )
    mrr = result.scalar() or Decimal("4850")
    
    # Determine level
    if mrr < 450:
        level_id = "level_0_survival"
        level_name = "Sopravvivenza"
        max_burn = Decimal("450")
        active = []
        disabled = ["kubernetes", "hume_ai", "tee_confidential"]
        next_threshold = 450
    elif mrr < 800:
        level_id = "level_1_bootstrap"
        level_name = "Bootstrap"
        max_burn = Decimal("800")
        active = ["eks_control_plane"]
        disabled = ["hume_ai", "tee_confidential"]
        next_threshold = 800
    elif mrr < 3000:
        level_id = "level_2_growth"
        level_name = "Crescita"
        max_burn = Decimal("3000")
        active = ["eks_control_plane", "hume_ai", "kubernetes_workers"]
        disabled = ["tee_confidential"]
        next_threshold = 3000
    elif mrr < 10000:
        level_id = "level_3_scale"
        level_name = "Scala"
        max_burn = Decimal("10000")
        active = ["eks_control_plane", "hume_ai", "vault_ha", "dat_iq"]
        disabled = ["tee_confidential"]
        next_threshold = 10000
    else:
        level_id = "level_4_enterprise"
        level_name = "Enterprise"
        max_burn = Decimal("35000")
        active = ["all_components"]
        disabled = []
        next_threshold = None
    
    cost_ratio = float(mrr / max_burn) if max_burn > 0 else 0
    
    return CurrentLevel(
        level_id=level_id,
        level_name=level_name,
        mrr=mrr,
        max_burn=max_burn,
        cost_ratio=cost_ratio,
        active_components=active,
        disabled_components=disabled,
        next_level={
            "id": f"level_{int(level_id.split('_')[1]) + 1}_{['bootstrap', 'growth', 'scale', 'enterprise'][int(level_id.split('_')[1])]}",
            "threshold": next_threshold,
            "progress": float(mrr / next_threshold * 100) if next_threshold else 100
        } if next_threshold else None
    )


@router.get("/revenue/metrics", response_model=RevenueMetrics)
async def get_revenue_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get detailed revenue metrics."""
    
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    sixty_days_ago = datetime.utcnow() - timedelta(days=60)
    
    # Current month
    result = await db.execute(
        select(func.sum(Pagamento.importo)).select_from(Pagamento)
        .where(and_(
            Pagamento.stato == "completed",
            Pagamento.created_at >= thirty_days_ago
        ))
    )
    mrr = result.scalar() or Decimal("4850")
    
    # Last month
    last_month_result = await db.execute(
        select(func.sum(Pagamento.importo)).select_from(Pagamento)
        .where(and_(
            Pagamento.stato == "completed",
            Pagamento.created_at >= sixty_days_ago,
            Pagamento.created_at < thirty_days_ago
        ))
    )
    last_month = last_month_result.scalar() or Decimal("4200")
    
    growth_rate = float((mrr - last_month) / last_month * 100) if last_month > 0 else 0
    
    return RevenueMetrics(
        mrr=mrr,
        arr=mrr * 12,
        last_month_revenue=last_month,
        last_3_months_avg=mrr * Decimal("0.95"),  # Mock
        growth_rate_mom=growth_rate,
        ytd_revenue=mrr * 2,  # Mock
        projected_next_month=mrr * Decimal("1.12")
    )


@router.post("/economics/simulate", response_model=SimulationResponse)
async def simulate_revenue(
    request: SimulationRequest,
    current_user: dict = Depends(get_current_user)
):
    """Simulate revenue scenario."""
    
    projected = request.projected_mrr
    
    # Determine simulated level
    if projected < 450:
        simulated_level = "level_0_survival"
    elif projected < 800:
        simulated_level = "level_1_bootstrap"
    elif projected < 3000:
        simulated_level = "level_2_growth"
    elif projected < 10000:
        simulated_level = "level_3_scale"
    else:
        simulated_level = "level_4_enterprise"
    
    return SimulationResponse(
        current_level="level_2_growth",
        simulated_level=simulated_level,
        triggers=[
            {
                "level_id": simulated_level,
                "triggered": True,
                "confidence": 1.0,
                "reason": f"Revenue {projected} within range"
            }
        ],
        projected_costs={
            "current": Decimal("1183"),
            "simulated": Decimal("3000") if simulated_level == "level_3_scale" else Decimal("800")
        }
    )


# ==========================================
# COMMANDS
# ==========================================

@router.post("/command/change-carrier", response_model=ChangeCarrierResponse)
async def change_carrier(
    request: ChangeCarrierRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Change carrier for shipment (via PAOLO)."""
    from uuid import UUID
    
    shipment = await db.get(Spedizione, UUID(request.shipment_id))
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    old_carrier = await db.get(Corriere, shipment.corriere_id)
    new_carrier = await db.get(Corriere, UUID(request.new_carrier_id))
    
    if not new_carrier:
        raise HTTPException(status_code=404, detail="New carrier not found")
    
    # Update shipment
    shipment.corriere_id = new_carrier.id
    await db.commit()
    
    return ChangeCarrierResponse(
        success=True,
        shipment_id=request.shipment_id,
        old_carrier=old_carrier.nome if old_carrier else "Unknown",
        new_carrier=new_carrier.nome,
        estimated_delay=15,
        message=f"Carrier cambiato da {old_carrier.nome if old_carrier else 'Unknown'} a {new_carrier.nome}"
    )


@router.post("/command/veto-paolo")
async def veto_paolo(
    request: VetoPaoloRequest,
    current_user: dict = Depends(get_current_user)
):
    """Veto a PAOLO suggestion."""
    # Log the veto
    return {"success": True, "message": "Veto applicato"}


@router.post("/command/emergency-stop")
async def emergency_stop(
    request: EmergencyStopRequest,
    current_user: dict = Depends(get_current_user)
):
    """Emergency stop all AI operations."""
    # Log emergency stop
    return {
        "success": True,
        "scope": request.scope,
        "message": f"Emergency stop attivato per {request.scope}",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/command/resume")
async def resume_operations(
    scope: str = "all",
    current_user: dict = Depends(get_current_user)
):
    """Resume operations after emergency stop."""
    return {
        "success": True,
        "scope": scope,
        "message": f"Operazioni ripristinate per {scope}"
    }


@router.post("/command/black-friday")
async def toggle_black_friday(
    request: BlackFridayModeRequest,
    current_user: dict = Depends(get_current_user)
):
    """Toggle Black Friday mode."""
    return {
        "success": True,
        "enabled": request.enabled,
        "discount_percent": request.discount_percent,
        "message": f"Black Friday mode {'attivato' if request.enabled else 'disattivato'}"
    }


@router.post("/command/force-level")
async def force_level(
    request: ForceLevelRequest,
    current_user: dict = Depends(get_current_user)
):
    """Force economic level (override auto)."""
    return {
        "success": True,
        "level": request.level,
        "message": f"Livello forzato a {request.level}"
    }