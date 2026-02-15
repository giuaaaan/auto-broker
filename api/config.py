"""
Auto-Broker Configuration - Production Ready
Supporta DEMO_MODE per test senza costi API
"""
import os
import secrets
from typing import Optional


class Settings:
    """Application settings with secure defaults"""
    
    # Demo Mode
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "true").lower() == "true"
    
    # Database - Default SQLite per dev, PostgreSQL per prod
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./autobroker_dev.db" if os.getenv("ENV", "development") == "development" 
        else "postgresql+asyncpg://user:pass@localhost/dbname"
    )
    
    # Redis - Optional, usa fake redis in dev
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    
    # Security - Genera secret random se non specificato
    JWT_SECRET: str = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
    
    # CORS Origins
    ALLOWED_ORIGINS: list = os.getenv(
        "ALLOWED_ORIGINS", 
        "http://localhost:5173,http://localhost:3000"
    ).split(",")
    
    # AI Services (opzionali in DEMO_MODE)
    HUME_API_KEY: Optional[str] = os.getenv("HUME_API_KEY")
    HUME_SECRET_KEY: Optional[str] = os.getenv("HUME_SECRET_KEY")
    INSIGHTO_API_KEY: Optional[str] = os.getenv("INSIGHTO_API_KEY")
    
    # Environment
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "true" if ENV == "development" else "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG" if DEBUG else "INFO")
    
    # Performance
    UVICORN_WORKERS: int = int(os.getenv("UVICORN_WORKERS", "1" if DEBUG else "2"))
    DATABASE_POOL_SIZE: int = int(os.getenv("DATABASE_POOL_SIZE", "5"))
    
    @property
    def is_demo(self) -> bool:
        """Check if running in demo mode"""
        return self.DEMO_MODE
    
    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.ENV == "production"
    
    @property
    def ai_services_enabled(self) -> bool:
        """Check if real AI services are configured"""
        if self.DEMO_MODE:
            return False
        return bool(self.HUME_API_KEY and self.INSIGHTO_API_KEY)
    
    def validate(self) -> list:
        """Validate configuration and return warnings"""
        warnings = []
        
        if self.is_production:
            if "demo" in self.JWT_SECRET.lower() or len(self.JWT_SECRET) < 32:
                warnings.append("WARNING: JWT_SECRET is not secure for production!")
            
            if "localhost" in self.DATABASE_URL:
                warnings.append("WARNING: Using local database in production!")
            
            if not self.REDIS_URL:
                warnings.append("WARNING: Redis not configured!")
        
        return warnings


# Singleton instance
settings = Settings()

# Log warnings on import
if warnings := settings.validate():
    import logging
    for warning in warnings:
        logging.warning(warning)
