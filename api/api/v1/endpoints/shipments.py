"""
Shipments API V1
Refactored with Repository Pattern
"""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from services.database import get_db
from core.repositories.shipment_repository import ShipmentRepository
from schemas.dashboard import ShipmentResponse, ShipmentListResponse

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


async def get_shipment_repo(db: AsyncSession = Depends(get_db)) -> ShipmentRepository:
    """Dependency injection for shipment repository"""
    return ShipmentRepository(db)


@router.get("/", response_model=ShipmentListResponse)
@limiter.limit("100/minute")
async def list_shipments(
    status: str = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    repo: ShipmentRepository = Depends(get_shipment_repo)
):
    """
    List all shipments with optional filtering
    
    - **status**: Filter by shipment status
    - **skip**: Pagination offset
    - **limit**: Maximum items to return
    """
    if status:
        shipments = await repo.get_by_status(status, skip, limit)
    else:
        shipments = await repo.list(skip, limit)
    
    return {
        "items": shipments,
        "total": len(shipments),
        "skip": skip,
        "limit": limit
    }


@router.get("/{shipment_id}", response_model=ShipmentResponse)
@limiter.limit("100/minute")
async def get_shipment(
    shipment_id: UUID,
    repo: ShipmentRepository = Depends(get_shipment_repo)
):
    """Get shipment by ID"""
    shipment = await repo.get_by_id(shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return shipment


@router.get("/active/count")
@limiter.limit("60/minute")
async def count_active_shipments(
    repo: ShipmentRepository = Depends(get_shipment_repo)
):
    """Get count of active shipments by status"""
    return await repo.count_by_status()
