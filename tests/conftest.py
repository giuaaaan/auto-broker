"""
Pytest configuration and fixtures for auto-broker tests.
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

# Add api to path (for importing api modules)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))


# ==================== PYTEST CONFIGURATION ====================

def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line("markers", "integration: Integration tests (with dependencies)")
    config.addinivalue_line("markers", "e2e: End-to-end tests (full flow)")
    config.addinivalue_line("markers", "asyncio: Async tests")


# ==================== FIXTURES ====================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def app():
    """Provide the FastAPI application with mocked database."""
    # Set test env vars
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost/test"
    os.environ["REDIS_URL"] = ""
    
    # Mock database engine creation
    with patch("services.database.create_async_engine") as mock_engine:
        with patch("services.database.async_sessionmaker") as mock_sessionmaker:
            # Now import main
            from main import app as fastapi_app
            yield fastapi_app


@pytest.fixture
def client(app) -> Generator[TestClient, None, None]:
    """Provide a TestClient instance."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_db_session() -> MagicMock:
    """Provide a mock database session."""
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.get = AsyncMock()
    return session


@pytest.fixture
def sample_lead_data():
    """Provide sample lead data as dict."""
    import uuid
    return {
        "id": str(uuid.uuid4()),
        "nome": "Mario",
        "cognome": "Rossi",
        "email": "mario@rossi.it",
        "telefono": "+393451234567",
        "azienda": "Rossi Srl",
        "partita_iva": "IT12345678901",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }


# ==================== SERVICE MOCKS ====================

@pytest.fixture
def mock_retell_service() -> MagicMock:
    """Provide a mock Retell service."""
    service = MagicMock()
    service.process_call = AsyncMock(return_value=MagicMock(
        origine="Milano",
        destinazione="Roma",
        tipologia_merce="Pallet",
        peso_stimato_kg=500.0,
        nome="Mario Rossi",
        email="mario@rossi.it"
    ))
    return service


@pytest.fixture
def mock_stripe_service() -> MagicMock:
    """Provide a mock Stripe service."""
    service = MagicMock()
    service.create_customer = AsyncMock(return_value={"id": "cus_test123"})
    service.create_subscription = AsyncMock(return_value={"id": "sub_test456"})
    service.create_usage_record = AsyncMock(return_value={"id": "ur_test789"})
    service.verify_webhook = MagicMock(return_value={"type": "invoice.payment_succeeded"})
    return service


@pytest.fixture(autouse=True)
def set_test_env():
    """Set test environment variables."""
    env_vars = {
        "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
        "REDIS_URL": "",
        "RETELL_API_KEY": "",
        "STRIPE_SECRET_KEY": "",
        "STRIPE_WEBHOOK_SECRET": "",
        "RESEND_API_KEY": "",
        "DOCUSIGN_INTEGRATION_KEY": "",
        "DOCUSIGN_USER_ID": "",
        "DOCUSIGN_ACCOUNT_ID": "",
        "DOCUSIGN_BASE_URL": "https://demo.docusign.net",
        "ENVIRONMENT": "test"
    }
    
    old_values = {}
    for key, value in env_vars.items():
        old_values[key] = os.environ.get(key)
        os.environ[key] = value
    
    yield
    
    for key, old_value in old_values.items():
        if old_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = old_value
