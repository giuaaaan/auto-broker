from fastapi import APIRouter

from .endpoints import shipments, dashboard, auth

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(shipments.router, prefix="/shipments", tags=["shipments"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
