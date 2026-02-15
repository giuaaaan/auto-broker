"""
Pytest Configuration and Fixtures - BIG TECH 100 Standards
==========================================================
Centralized test fixtures for unit, integration, and e2e tests.
"""

import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
import uuid

# Database
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# FastAPI
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Redis
import fakeredis.aioredis

# Add project root to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.core.cache import CacheManager, CacheConfig, init_cache_manager
from api.core.database_optimized import (
    DatabaseConfig, 
    OptimizedDatabaseManager,
    init_database
)


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/test_auto_broker"
TEST_REDIS_URL = "redis://localhost:6379/1"


# ═══════════════════════════════════════════════════════════════════════════════
# Event Loop
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Database Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest_asyncio.fixture(scope="function")
async def test_db_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def database_manager() -> AsyncGenerator[OptimizedDatabaseManager, None]:
    """Create a test database manager."""
    config = DatabaseConfig(
        database_url=TEST_DATABASE_URL,
        pool_size=2,
        max_overflow=0,
        echo=False,
    )
    
    manager = OptimizedDatabaseManager(config)
    # Mock engine for tests
    manager.engine = MagicMock()
    manager.session_factory = MagicMock()
    
    yield manager


# ═══════════════════════════════════════════════════════════════════════════════
# Redis Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest_asyncio.fixture(scope="function")
async def fake_redis():
    """Create a fake Redis client for testing."""
    redis = fakeredis.aioredis.FakeRedis()
    yield redis
    await redis.flushall()
    await redis.close()


@pytest_asyncio.fixture(scope="function")
async def cache_manager(fake_redis) -> AsyncGenerator[CacheManager, None]:
    """Create a test cache manager with fake Redis."""
    config = CacheConfig(
        default_ttl=60,
        prefix="test",
        circuit_breaker_enabled=False,
    )
    
    manager = CacheManager(redis_client=fake_redis, config=config)
    yield manager


# ═══════════════════════════════════════════════════════════════════════════════
# Application Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def app() -> FastAPI:
    """Create a test FastAPI application."""
    from main import app
    return app


@pytest.fixture(scope="function")
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    """Create a test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest_asyncio.fixture(scope="function")
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# ═══════════════════════════════════════════════════════════════════════════════
# Mock Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="function")
def mock_email_service():
    """Mock email service."""
    service = MagicMock()
    service.send_email = AsyncMock(return_value={"message_id": "test-123"})
    service.send_template_email = AsyncMock(return_value={"message_id": "test-456"})
    return service


@pytest.fixture(scope="function")
def mock_stripe_client():
    """Mock Stripe client."""
    client = MagicMock()
    client.create_payment_intent = AsyncMock(return_value={
        "id": "pi_test_123",
        "client_secret": "secret_test",
        "status": "requires_confirmation"
    })
    client.confirm_payment = AsyncMock(return_value={
        "id": "pi_test_123",
        "status": "succeeded"
    })
    return client


@pytest.fixture(scope="function")
def mock_external_apis():
    """Mock all external API calls."""
    mocks = {
        "scraping_service": MagicMock(),
        "pricing_engine": MagicMock(),
        "notification_service": MagicMock(),
        "document_generator": MagicMock(),
    }
    
    # Setup default returns
    mocks["scraping_service"].scrape = AsyncMock(return_value=[{
        "id": "1",
        "title": "Test Vehicle",
        "price": 50000,
        "source": "test"
    }])
    
    mocks["pricing_engine"].calculate_price = AsyncMock(return_value={
        "base_price": 50000,
        "adjustments": [],
        "final_price": 52000,
        "currency": "EUR"
    })
    
    mocks["notification_service"].send = AsyncMock(return_value={"sent": True})
    
    mocks["document_generator"].generate_pdf = AsyncMock(return_value=b"PDF content")
    
    return mocks


# ═══════════════════════════════════════════════════════════════════════════════
# Data Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="function")
def sample_vehicle_data():
    """Sample vehicle data for tests."""
    return {
        "id": str(uuid.uuid4()),
        "make": "BMW",
        "model": "X5",
        "year": 2024,
        "mileage": 15000,
        "fuel_type": "diesel",
        "transmission": "automatic",
        "price": 65000.00,
        "currency": "EUR",
        "vin": "WBA12345678901234",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture(scope="function")
def sample_user_data():
    """Sample user data for tests."""
    return {
        "id": str(uuid.uuid4()),
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User",
        "role": "customer",
        "is_active": True,
        "created_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture(scope="function")
def sample_order_data():
    """Sample order data for tests."""
    return {
        "id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "vehicle_id": str(uuid.uuid4()),
        "status": "pending",
        "total_amount": 65000.00,
        "currency": "EUR",
        "payment_status": "pending",
        "created_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture(scope="function")
def sample_api_response():
    """Sample API response structure."""
    return {
        "success": True,
        "data": None,
        "error": None,
        "meta": {
            "request_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Authentication Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="function")
def auth_headers():
    """Authentication headers for protected endpoints."""
    return {
        "Authorization": "Bearer test_token_123",
        "Content-Type": "application/json",
    }


@pytest.fixture(scope="function")
def admin_auth_headers():
    """Admin authentication headers."""
    return {
        "Authorization": "Bearer admin_token_456",
        "Content-Type": "application/json",
        "X-User-Role": "admin",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Utility Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="function")
def freeze_time():
    """Freeze time for deterministic tests."""
    from freezegun import freeze_time
    with freeze_time("2024-01-15 12:00:00") as frozen:
        yield frozen


@pytest.fixture(scope="function")
def temp_file(tmp_path):
    """Create a temporary file."""
    file_path = tmp_path / "test_file.txt"
    file_path.write_text("test content")
    return file_path


@pytest.fixture(scope="function")
def temp_directory(tmp_path):
    """Create a temporary directory."""
    dir_path = tmp_path / "test_dir"
    dir_path.mkdir()
    return dir_path


# ═══════════════════════════════════════════════════════════════════════════════
# Performance Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="function")
def benchmark():
    """Benchmark helper for performance tests."""
    import time
    
    class Benchmark:
        def __init__(self):
            self.results = []
        
        def measure(self, func, *args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            self.results.append({
                "function": func.__name__,
                "elapsed_ms": elapsed * 1000,
            })
            return result
        
        async def measure_async(self, func, *args, **kwargs):
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            self.results.append({
                "function": func.__name__,
                "elapsed_ms": elapsed * 1000,
            })
            return result
        
        def report(self):
            return self.results
    
    return Benchmark()


# ═══════════════════════════════════════════════════════════════════════════════
# Cleanup Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
async def cleanup_after_test():
    """Cleanup after each test."""
    yield
    # Cleanup code here
    await asyncio.sleep(0)  # Allow pending tasks to complete


# ═══════════════════════════════════════════════════════════════════════════════
# Markers
# ═══════════════════════════════════════════════════════════════════════════════

def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
