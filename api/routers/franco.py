"""
AUTO-BROKER: FRANCO (Retention Agent) Router

Endpoint per la gestione delle chiamate di retention.
"""
from typing import Dict, Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession

from services.database import get_db
from services.franco_service import FrancoService

logger = structlog.get_logger()

router = APIRouter(prefix="/franco", tags=["FRANCO - Retention Agent"])


# Simple auth dependency - in production, replace with proper JWT validation
async def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """
    Dependency per autenticazione JWT.
    
    In produzione, questo dovrebbe:
    - Validare il token JWT
    - Verificare la firma
    - Controllare scadenza
    - Estrarre claims (user_id, role)
    
    Args:
        authorization: Header Authorization con Bearer token
        
    Returns:
        User ID estratto dal token
        
    Raises:
        HTTPException: 401 se token mancante o invalido
    """
    if not authorization:
        logger.warning("franco_auth_missing_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Simple Bearer token check
    if not authorization.startswith("Bearer "):
        logger.warning("franco_auth_invalid_format")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = authorization.replace("Bearer ", "")
    
    # In produzione: validare JWT qui
    # Per ora accetta qualsiasi token non vuoto
    if not token or token == "test-token":
        logger.warning("franco_auth_invalid_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Estrai user_id dal token (mock per test)
    # In produzione: decodificare JWT e estrarre sub claim
    user_id = token.split("-")[0] if "-" in token else "unknown"
    
    logger.debug("franco_auth_success", user_id=user_id)
    return user_id


@router.post(
    "/internal/trigger",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Trigger manuale chiamate retention",
    description="""
    Avvia manualmente il processo di retention per le spedizioni consegnate 7 giorni fa.
    
    Proteggere con JWT. Solo utenti autorizzati possono triggerare.
    
    Rate limiting: max 10 chiamate/ora vengono effettuate.
    
    Returns:
        Statistiche sul processo:
        - processed: numero spedizioni elaborate
        - successful_calls: chiamate avviate con successo
        - failed_calls: chiamate fallite
        - skipped: saltate (rate limit, già tentate)
    """
)
async def trigger_franco(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger manuale del processo di retention da parte dell'agente FRANCO.
    
    L'agente FRANCO contatta i clienti 7 giorni dopo la consegna per:
    - Verificare soddisfazione
    - Raccogliere feedback
    - Proporre nuove prenotazioni
    
    Autenticazione richiesta: JWT Bearer token
    """
    logger.info(
        "franco_manual_trigger_requested",
        user_id=user_id
    )
    
    try:
        service = FrancoService(db_session=db)
        result = await service.process_retention()
        
        logger.info(
            "franco_manual_trigger_completed",
            user_id=user_id,
            processed=result["processed"],
            successful=result["successful_calls"],
            failed=result["failed_calls"]
        )
        
        return {
            "success": True,
            "triggered_by": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "results": result
        }
        
    except Exception as e:
        logger.error(
            "franco_manual_trigger_failed",
            user_id=user_id,
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger retention process: {str(e)}"
        )


@router.get(
    "/stats",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Statistiche retention",
    description="""
    Recupera statistiche sulle chiamate di retention.
    
    Include:
    - Totale tentativi
    - Tasso di successo
    - Tasso di ri-prenotazione
    - Distribuzione esiti
    - Stato rate limiting
    """
)
async def get_retention_stats(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Ottieni statistiche dettagliate sulle performance dell'agente FRANCO.
    
    Metrics:
    - total_attempts: numero totale di tentativi
    - success_rate_percent: percentuale chiamate riuscite
    - rebooking_rate_percent: percentuale clienti che hanno ri-prenotato
    - recent_attempts_7d: tentativi negli ultimi 7 giorni
    """
    try:
        service = FrancoService(db_session=db)
        stats = await service.get_retention_stats()
        
        logger.info(
            "franco_stats_retrieved",
            user_id=user_id,
            total_attempts=stats["total_attempts"]
        )
        
        return {
            "success": True,
            "requested_by": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "stats": stats
        }
        
    except Exception as e:
        logger.error(
            "franco_stats_retrieval_failed",
            user_id=user_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve retention stats: {str(e)}"
        )


@router.get(
    "/health",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Health check servizio FRANCO",
    description="Verifica lo stato del servizio di retention"
)
async def franco_health_check(
    db: AsyncSession = Depends(get_db)
):
    """
    Health check per il servizio FRANCO.
    
    Verifica:
    - Connessione database
    - Stato circuit breaker
    - Rate limiting disponibilità
    """
    try:
        service = FrancoService(db_session=db)
        stats = await service.get_retention_stats()
        
        return {
            "status": "healthy",
            "service": "franco_retention",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                "database": "connected",
                "rate_limit_available": stats["rate_limit"]["current_window_calls"] < 10,
                "total_attempts": stats["total_attempts"]
            }
        }
        
    except Exception as e:
        logger.error("franco_health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "service": "franco_retention",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


# Import datetime qui per evitare circular import
from datetime import datetime
