"""
AUTO-BROKER: Cost Tracking Middleware

Middleware FastAPI per tracciamento automatico costi.
Intercetta response e stima costo in base al tipo di endpoint.
"""
from typing import Callable, Optional
from uuid import UUID

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.background import BackgroundTask

from services.cost_tracker import CostTracker, COST_CONFIG

logger = structlog.get_logger()


class CostTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware per tracciamento automatico costi.
    
    Intercetta le response e stima il costo in base al path:
    - /retell-webhook: ~0.15 EUR per minuto medio
    - /blockchain: 0.001 EUR + gas estimate
    - /hume*: Costi API Hume AI
    
    I costi vengono tracciati in background senza bloccare la response.
    """
    
    def __init__(self, app, db_session_factory: Optional[Callable] = None):
        super().__init__(app)
        self.db_session_factory = db_session_factory
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Processa la richiesta e traccia costi sulla response.
        
        Args:
            request: FastAPI Request
            call_next: Prossimo middleware/handler
            
        Returns:
            Response con eventuale background task per tracking
        """
        response = await call_next(request)
        
        # Estrai info dalla richiesta
        path = request.url.path
        method = request.method
        
        # Calcola costo stimato
        cost_estimate = self._estimate_cost(path, method, response)
        
        if cost_estimate > 0:
            # Aggiungi background task per tracking (non blocca response)
            if not response.background:
                response.background = BackgroundTask(
                    self._track_cost,
                    request=request,
                    response=response,
                    cost=cost_estimate,
                    path=path
                )
            else:
                # Se già presente background, chaina il task
                original_bg = response.background
                response.background = BackgroundTask(
                    self._chain_tasks,
                    original_bg=original_bg,
                    new_task=self._track_cost,
                    request=request,
                    response=response,
                    cost=cost_estimate,
                    path=path
                )
        
        return response
    
    def _estimate_cost(self, path: str, method: str, response: Response) -> float:
        """
        Stima il costo in base al path e response.
        
        Args:
            path: URL path
            method: HTTP method
            response: HTTP response
            
        Returns:
            Costo stimato in EUR
        """
        cost = 0.0
        
        # Retell webhook calls (1 minuto medio)
        if "retell-webhook" in path and method == "POST":
            cost = float(COST_CONFIG["retell_per_minute"])
            logger.debug(
                "cost_estimated_retell",
                path=path,
                estimated_cost=cost
            )
        
        # Blockchain transactions
        elif "blockchain" in path or "pod" in path:
            # Base + stimato gas (semplificato)
            base_cost = float(COST_CONFIG["polygon_tx_base"])
            gas_estimate = 0.0005  # Stima media gas in EUR
            cost = base_cost + gas_estimate
            logger.debug(
                "cost_estimated_blockchain",
                path=path,
                base_cost=base_cost,
                gas_estimate=gas_estimate,
                total_cost=cost
            )
        
        # Hume AI API calls
        elif "hume" in path or "sentiment" in path:
            # Assume 1 minuto di audio processato
            cost = float(COST_CONFIG["hume_ai_per_minute"])
            logger.debug(
                "cost_estimated_hume",
                path=path,
                estimated_cost=cost
            )
        
        # DAT iQ lookups
        elif "dat-iq" in path or "rates" in path:
            cost = float(COST_CONFIG["dat_iq_per_request"])
            logger.debug(
                "cost_estimated_dat_iq",
                path=path,
                estimated_cost=cost
            )
        
        return cost
    
    async def _track_cost(
        self,
        request: Request,
        response: Response,
        cost: float,
        path: str
    ):
        """
        Traccia il costo nel database (background task).
        
        Args:
            request: Original request
            response: HTTP response
            cost: Costo stimato
            path: URL path
        """
        try:
            # Ottieni db session
            if self.db_session_factory:
                db = self.db_session_factory()
            else:
                # Prova a ottenere da app state
                from services.database import get_db
                db = await anext(get_db())
            
            tracker = CostTracker(db)
            
            # Determina tipo evento e provider
            event_type, provider = self._classify_event(path)
            
            # Estrai shipment_id dai parametri se presente
            shipment_id = None
            if hasattr(request.state, "shipment_id"):
                shipment_id = request.state.shipment_id
            
            # Traccia evento
            await tracker.track_event(
                event_type=event_type,
                shipment_id=shipment_id,
                cost_eur=Decimal(str(cost)),
                provider=provider,
                metadata={
                    "path": path,
                    "method": request.method,
                    "status_code": response.status_code,
                    "estimated": True
                }
            )
            
            # Flush buffer
            await tracker.force_flush()
            
            logger.info(
                "cost_tracked_background",
                path=path,
                cost_eur=cost,
                provider=provider,
                event_type=event_type
            )
            
        except Exception as e:
            # Non bloccare mai la response per errori di tracking
            logger.error(
                "cost_tracking_background_failed",
                path=path,
                error=str(e),
                error_type=type(e).__name__
            )
    
    def _classify_event(self, path: str) -> tuple:
        """
        Classifica l'evento in base al path.
        
        Returns:
            Tuple (event_type, provider)
        """
        if "retell" in path:
            return ("api_call", "retell")
        elif "blockchain" in path or "pod" in path:
            return ("blockchain_tx", "polygon")
        elif "hume" in path or "sentiment" in path:
            return ("api_call", "hume")
        elif "dat" in path or "rates" in path:
            return ("api_lookup", "dat_iq")
        else:
            return ("api_call", "unknown")
    
    async def _chain_tasks(
        self,
        original_bg,
        new_task,
        **kwargs
    ):
        """Esegue task in sequenza."""
        await original_bg()
        await new_task(**kwargs)


# Factory per creare middleware con db session
def create_cost_tracking_middleware(db_session_factory: Callable):
    """
    Factory per CostTrackingMiddleware con db session configurata.
    
    Usage:
        app.add_middleware(
            CostTrackingMiddleware,
            db_session_factory=get_db
        )
    """
    return lambda app: CostTrackingMiddleware(app, db_session_factory)


# Import qui per evitare circular import
from decimal import Decimal
from uuid import uuid4
