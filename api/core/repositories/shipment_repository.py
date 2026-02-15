"""
Shipment Repository
Specific repository for Spedizione entity
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models import Spedizione
from .base import SQLAlchemyRepository


class ShipmentRepository(SQLAlchemyRepository[Spedizione]):
    """Repository for Shipment (Spedizione) entity"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(db, Spedizione)
    
    async def get_active_shipments(self, skip: int = 0, limit: int = 100) -> List[Spedizione]:
        """Get all active shipments (not delivered or cancelled)"""
        from sqlalchemy import select
        result = await self.db.execute(
            select(Spedizione)
            .where(Spedizione.stato.in_(["in_preparazione", "in_transito", "ritirata"]))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_by_status(self, status: str, skip: int = 0, limit: int = 100) -> List[Spedizione]:
        """Get shipments by status"""
        result = await self.db.execute(
            select(Spedizione)
            .where(Spedizione.stato == status)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_by_tracking(self, tracking_number: str) -> Optional[Spedizione]:
        """Get shipment by tracking number"""
        result = await self.db.execute(
            select(Spedizione).where(Spedizione.numero_tracking == tracking_number)
        )
        return result.scalar_one_or_none()
    
    async def count_by_status(self) -> dict:
        """Count shipments grouped by status"""
        from sqlalchemy import func
        result = await self.db.execute(
            select(Spedizione.stato, func.count().label("count"))
            .group_by(Spedizione.stato)
        )
        return {row.stato: row.count for row in result.all()}
