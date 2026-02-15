"""
Demo Router - Endpoints per DEMO_MODE
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services.database import get_db
from utils.seeders import seed_demo_data, reset_demo_data

router = APIRouter(prefix="/demo", tags=["Demo"])


@router.post("/seed", summary="Auto-seed database with demo data")
async def api_seed_demo_data(db: AsyncSession = Depends(get_db)):
    """Popola il database con dati demo"""
    if not settings.DEMO_MODE:
        raise HTTPException(status_code=403, detail="Only available in DEMO_MODE")
    
    result = await seed_demo_data(db)
    if result["status"] == "error":
        raise HTTPException(status_code=403, detail=result["message"])
    return result


@router.post("/reset", summary="Reset demo database")
async def api_reset_demo_data(db: AsyncSession = Depends(get_db)):
    """Cancella tutti i dati e re-seeda"""
    if not settings.DEMO_MODE:
        raise HTTPException(status_code=403, detail="Only available in DEMO_MODE")
    
    result = await reset_demo_data(db)
    if result["status"] == "error":
        raise HTTPException(status_code=403, detail=result["message"])
    return result
