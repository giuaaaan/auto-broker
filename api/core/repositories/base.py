"""
Base Repository Pattern
Following Clean Architecture principles
"""
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """Abstract base repository for all entities"""
    
    def __init__(self, db: AsyncSession, model_class: type):
        self.db = db
        self.model_class = model_class
    
    @abstractmethod
    async def get_by_id(self, id: UUID) -> Optional[T]:
        """Get entity by ID"""
        pass
    
    @abstractmethod
    async def list(self, skip: int = 0, limit: int = 100) -> List[T]:
        """List all entities with pagination"""
        pass
    
    @abstractmethod
    async def create(self, entity: T) -> T:
        """Create new entity"""
        pass
    
    @abstractmethod
    async def update(self, id: UUID, entity_data: dict) -> Optional[T]:
        """Update existing entity"""
        pass
    
    @abstractmethod
    async def delete(self, id: UUID) -> bool:
        """Delete entity by ID"""
        pass


class SQLAlchemyRepository(BaseRepository[T]):
    """Concrete implementation using SQLAlchemy"""
    
    async def get_by_id(self, id: UUID) -> Optional[T]:
        result = await self.db.execute(
            select(self.model_class).where(self.model_class.id == id)
        )
        return result.scalar_one_or_none()
    
    async def list(self, skip: int = 0, limit: int = 100) -> List[T]:
        result = await self.db.execute(
            select(self.model_class).offset(skip).limit(limit)
        )
        return result.scalars().all()
    
    async def create(self, entity: T) -> T:
        self.db.add(entity)
        await self.db.commit()
        await self.db.refresh(entity)
        return entity
    
    async def update(self, id: UUID, entity_data: dict) -> Optional[T]:
        entity = await self.get_by_id(id)
        if not entity:
            return None
        
        for key, value in entity_data.items():
            setattr(entity, key, value)
        
        await self.db.commit()
        await self.db.refresh(entity)
        return entity
    
    async def delete(self, id: UUID) -> bool:
        result = await self.db.execute(
            delete(self.model_class).where(self.model_class.id == id)
        )
        await self.db.commit()
        return result.rowcount > 0
