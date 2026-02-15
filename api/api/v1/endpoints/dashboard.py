"""
Dashboard API V1
Clean Architecture with dependency injection
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from services.database import get_db
from core.repositories.shipment_repository import ShipmentRepository
from schemas.dashboard import DashboardStats

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


async def get_shipment_repo(db: AsyncSession = Depends(get_db)) -> ShipmentRepository:
    """Dependency injection for shipment repository"""
    return ShipmentRepository(db)


@router.get("/stats", response_model=DashboardStats)
@limiter.limit("100/minute")
async def get_dashboard_stats(
    repo: ShipmentRepository = Depends(get_shipment_repo)
):
    """
    Get aggregated dashboard statistics
    
    Returns:
    - Active shipments count
    - Total shipments count
    - Monthly revenue
    - Current level and progress
    """
    from sqlalchemy import func, select, and_
    from datetime import timedelta
    from models import Spedizione, Pagamento
    
    # Count active shipments
    active_shipments = len(await repo.get_active_shipments())
    
    # Total shipments
    total_shipments = len(await repo.list())
    
    # Monthly revenue
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    # This would be calculated from payments
    monthly_revenue = Decimal("4850.00")  # Demo value
    
    # Calculate level
    if monthly_revenue < 450:
        current_level = 0
        progress_percent = float(monthly_revenue / 450 * 100)
    elif monthly_revenue < 800:
        current_level = 1
        progress_percent = float((monthly_revenue - 450) / (800 - 450) * 100)
    elif monthly_revenue < 3000:
        current_level = 2
        progress_percent = float((monthly_revenue - 800) / (3000 - 800) * 100)
    elif monthly_revenue < 10000:
        current_level = 3
        progress_percent = float((monthly_revenue - 3000) / (10000 - 3000) * 100)
    else:
        current_level = 4
        progress_percent = 100.0
    
    costs_map = {0: 450, 1: 800, 2: 3000, 3: 10000, 4: 35000}
    costs_monthly = costs_map.get(current_level, 450)
    
    margin_percent = float((monthly_revenue - costs_monthly) / monthly_revenue * 100) if monthly_revenue > 0 else 0
    
    return DashboardStats(
        active_shipments=active_shipments,
        total_shipments=total_shipments,
        monthly_revenue=float(monthly_revenue),
        current_level=current_level,
        progress_percent=round(progress_percent, 1),
        costs_monthly=costs_monthly,
        margin_percent=round(margin_percent, 1),
        delivered_today=random.randint(0, 5),  # Demo value
        pending_alerts=random.randint(0, 3)     # Demo value
    )


import random  # For demo values
