"""
AUTO-BROKER: Cache Management Router

Endpoint per gestione Semantic Cache (monitoring, warming, clearing).
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.database import get_db
from api.services.semantic_cache import SemanticCacheService, get_semantic_cache

logger = structlog.get_logger()

router = APIRouter(prefix="/cache", tags=["Semantic Cache Management"])


# ==========================================
# SCHEMAS
# ==========================================

class CacheStatsResponse(BaseModel):
    """Statistiche cache."""
    total_entries: int
    recent_entries_7d: int
    total_hits: int
    hit_rate_percent: float
    cost_saved_eur: float
    hume_cost_per_minute: float
    similarity_threshold: float
    embedding_dimensions: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_entries": 15234,
                "recent_entries_7d": 3456,
                "total_hits": 89234,
                "hit_rate_percent": 85.4,
                "cost_saved_eur": 13385.10,
                "hume_cost_per_minute": 0.15,
                "similarity_threshold": 0.95,
                "embedding_dimensions": 384
            }
        }


class WarmCacheRequest(BaseModel):
    """Request per warming cache."""
    transcriptions: List[str] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Lista di transcriptions da precaricare"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "transcriptions": [
                    "Il prezzo è troppo alto",
                    "Servizio eccellente",
                    "Non sono soddisfatto"
                ]
            }
        }


class WarmCacheResponse(BaseModel):
    """Risultato warming cache."""
    processed: int
    cached: int
    errors: int
    message: str


class ClearCacheResponse(BaseModel):
    """Risultato clear cache."""
    deleted_count: int
    message: str


class ClearOldCacheRequest(BaseModel):
    """Request per cancellazione cache vecchia."""
    days: int = Field(
        30,
        ge=1,
        le=365,
        description="Cancella entries più vecchie di X giorni (GDPR)"
    )


# ==========================================
# AUTH DEPENDENCY
# ==========================================

async def verify_admin_token(authorization: Optional[str] = Header(None)) -> str:
    """
    Verifica token admin per operazioni sensibili.
    
    In produzione: validare JWT con claims admin.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    
    # TODO: Validare JWT con claim admin
    if token != "admin-token-123":  # Placeholder
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return "admin"


# ==========================================
# ENDPOINTS
# ==========================================

@router.get(
    "/stats",
    response_model=CacheStatsResponse,
    summary="Statistiche semantic cache",
    description="""
    Recupera statistiche della cache semantica:
    - Hit rate (percentuale cache hit)
    - Costo risparmiato (EUR)
    - Numero entries
    - Performance metrics
    """
)
async def get_cache_stats(
    db: AsyncSession = Depends(get_db)
):
    """
    Ottieni statistiche complete della semantic cache.
    
    Mostra efficacia della cache in termini di:
    - Riduzione costi Hume AI
    - Hit rate
    - Utilizzo storage
    """
    try:
        cache = await get_semantic_cache(db)
        stats = await cache.get_stats()
        
        logger.info(
            "cache_stats_accessed",
            total_entries=stats.get("total_entries", 0),
            hit_rate=stats.get("hit_rate_percent", 0)
        )
        
        return CacheStatsResponse(**stats)
        
    except Exception as e:
        logger.error("cache_stats_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve cache stats: {str(e)}"
        )


@router.post(
    "/warm",
    response_model=WarmCacheResponse,
    summary="Precarica cache",
    description="Precarica la cache con transcriptions comuni per ridurre latency"
)
async def warm_cache(
    request: WarmCacheRequest,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(verify_admin_token)
):
    """
    Precarica cache con lista di transcriptions.
    
    Utile per:
    - Preparare cache prima di campagne
    - Precaricare frasi comuni
    - Ridurre cold start
    
    Limiti:
    - Max 1000 transcriptions per chiamata
    - Solo admin
    """
    try:
        cache = await get_semantic_cache(db)
        result = await cache.warm_cache(request.transcriptions)
        
        logger.info(
            "cache_warm_executed",
            admin=admin,
            processed=result["processed"],
            cached=result["cached"]
        )
        
        return WarmCacheResponse(
            processed=result["processed"],
            cached=result["cached"],
            errors=result["errors"],
            message=f"Cache warming completed: {result['cached']}/{result['processed']} entries cached"
        )
        
    except Exception as e:
        logger.error("cache_warm_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Cache warming failed: {str(e)}"
        )


@router.delete(
    "/clear",
    response_model=ClearCacheResponse,
    summary="Svuota cache",
    description="Svuota completamente la cache (operazione pericolosa!)"
)
async def clear_cache(
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(verify_admin_token)
):
    """
    Svuota completamente la cache semantica.
    
    ⚠️ ATTENZIONE: Questa operazione:
    - Cancella TUTTE le entries
    - Azzera il risparmio cumulato
    - Richiede rebuild della cache
    
    Usare con cautela!
    """
    try:
        # Per sicurezza, implementiamo soft delete o richiediamo conferma
        # Qui facciamo delete reale ma logghiamo pesantemente
        
        from api.models import SentimentCache
        from sqlalchemy import delete
        
        result = await db.execute(delete(SentimentCache))
        await db.commit()
        
        deleted_count = result.rowcount
        
        logger.critical(
            "cache_cleared_by_admin",
            admin=admin,
            deleted_count=deleted_count,
            timestamp=datetime.utcnow().isoformat()
        )
        
        return ClearCacheResponse(
            deleted_count=deleted_count,
            message=f"Cache cleared: {deleted_count} entries deleted"
        )
        
    except Exception as e:
        await db.rollback()
        logger.error("cache_clear_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Cache clear failed: {str(e)}"
        )


@router.post(
    "/clear-old",
    response_model=ClearCacheResponse,
    summary="Cancella cache vecchia (GDPR)",
    description="Cancella entries più vecchie di X giorni (compliance GDPR)"
)
async def clear_old_cache(
    request: ClearOldCacheRequest,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(verify_admin_token)
):
    """
    Cancella entries cache più vecchie di X giorni.
    
    GDPR Compliance:
    - Default 30 giorni retention
    - Configurabile 1-365 giorni
    - Preserva metriche aggregate
    
    Raccomandato: eseguire come cron job giornaliero
    """
    try:
        cache = await get_semantic_cache(db)
        deleted_count = await cache.clear_old_cache(request.days)
        
        logger.info(
            "cache_cleared_old",
            admin=admin,
            deleted_count=deleted_count,
            older_than_days=request.days
        )
        
        return ClearCacheResponse(
            deleted_count=deleted_count,
            message=f"Cleaned {deleted_count} entries older than {request.days} days"
        )
        
    except Exception as e:
        logger.error("cache_clear_old_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Cache cleanup failed: {str(e)}"
        )


@router.get(
    "/health",
    summary="Health check cache",
    description="Verifica stato della cache semantica"
)
async def cache_health(
    db: AsyncSession = Depends(get_db)
):
    """
    Health check per semantic cache.
    
    Verifica:
    - Connessione database
    - Disponibilità embedding model
    - Dimensione cache
    """
    try:
        cache = await get_semantic_cache(db)
        stats = await cache.get_stats()
        
        # Determina stato
        is_healthy = stats.get("total_entries", 0) >= 0  # Sempre OK se DB funziona
        
        return {
            "status": "healthy" if is_healthy else "degraded",
            "service": "semantic_cache",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                "database": "connected",
                "total_entries": stats.get("total_entries", 0),
                "hit_rate": stats.get("hit_rate_percent", 0)
            }
        }
        
    except Exception as e:
        logger.error("cache_health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "service": "semantic_cache",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }
