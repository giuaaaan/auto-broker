"""
Auto-Broker Configuration
Supporta DEMO_MODE per test senza costi API
"""
import os
from typing import Optional


class Settings:
    """Application settings with DEMO_MODE support"""
    
    # Demo Mode
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() == "true"
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://autobroker:autobroker@localhost:5432/autobroker"
    )
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Security
    JWT_SECRET: str = os.getenv("JWT_SECRET", "demo-secret-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
    
    # AI Services (opzionali in DEMO_MODE)
    HUME_API_KEY: Optional[str] = os.getenv("HUME_API_KEY")
    HUME_SECRET_KEY: Optional[str] = os.getenv("HUME_SECRET_KEY")
    INSIGHTO_API_KEY: Optional[str] = os.getenv("INSIGHTO_API_KEY")
    
    # Environment
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Performance
    UVICORN_WORKERS: int = int(os.getenv("UVICORN_WORKERS", "2"))
    DATABASE_POOL_SIZE: int = int(os.getenv("DATABASE_POOL_SIZE", "5"))
    
    @property
    def is_demo(self) -> bool:
        """Check if running in demo mode"""
        return self.DEMO_MODE
    
    @property
    def ai_services_enabled(self) -> bool:
        """Check if real AI services are configured"""
        if self.DEMO_MODE:
            return False
        return bool(self.HUME_API_KEY and self.INSIGHTO_API_KEY)


# Singleton instance
settings = Settings()
