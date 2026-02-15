"""
AUTO-BROKER: FastAPI Main Application - REFACTORED v2.0
Clean Architecture with Dependency Injection
Production-ready with API versioning
"""
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Callable
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from config import settings
from api.v1 import api_router as api_v1_router

# Configure structlog for JSON logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info(
        "Starting AUTO-BROKER API v2.0",
        version="2.0.0",
        environment=settings.ENV,
        demo_mode=settings.DEMO_MODE
    )
    
    # Startup logic here (DB init, etc.)
    
    yield
    
    # Shutdown logic
    logger.info("Shutting down AUTO-BROKER API")


# Create FastAPI app
app = FastAPI(
    title="AUTO-BROKER API",
    description="Production-ready API with Clean Architecture",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda req, exc: JSONResponse(
    status_code=429,
    content={"error": "Rate limit exceeded", "retry_after": 60}
))

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next: Callable) -> Response:
    """Log all HTTP requests with timing"""
    start_time = time.time()
    
    logger.info(
        "request_started",
        method=request.method,
        path=request.url.path,
        client_ip=get_remote_address(request)
    )
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(process_time * 1000, 2)
        )
        
        response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(
            "request_failed",
            method=request.method,
            path=request.url.path,
            error=str(e),
            duration_ms=round(process_time * 1000, 2)
        )
        raise


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions"""
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        error_type=type(exc).__name__,
        error=str(exc)
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "request_id": str(uuid4())[:8],
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# Health check
@app.get("/health")
@limiter.limit("60/minute")
async def health_check(request: Request):
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "environment": settings.ENV,
        "timestamp": datetime.utcnow().isoformat()
    }


# Include API routers with versioning
app.include_router(api_v1_router, prefix="/api/v1")

# Legacy router for backward compatibility (to be deprecated)
# from routers.dashboard import router as dashboard_router
# app.include_router(dashboard_router)  # Old routes without /api/v1 prefix


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main_refactored:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.UVICORN_WORKERS
    )
