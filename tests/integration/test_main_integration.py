"""
Integration tests for main FastAPI application.
These tests run against a real PostgreSQL and Redis database.
"""
import pytest
import asyncio
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..', 'api'))

from models import Base, Lead, Qualificazione, Preventivo, Contratto, Corriere
from schemas import LeadCreate, QualifyLeadRequest, CalculatePriceRequest, CreateProposalRequest
from main import app
from services.database import get_db


# Test database URL from environment or default
TEST_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://broker_user:broker_pass_test@localhost:5432/broker_test")

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    """Override get_db to use test database."""
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module", autouse=True)
async def setup_database():
    """Set up test database."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session():
    """Provide a database session for tests."""
    async with TestSessionLocal() as session:
        yield session
        # Clean up after test
        await session.execute(delete(Contratto))
        await session.execute(delete(Preventivo))
        await session.execute(delete(Qualificazione))
        await session.execute(delete(Lead))
        await session.execute(delete(Corriere))
        await session.commit()


@pytest.fixture
def client():
    """Provide a TestClient instance."""
    with TestClient(app) as c:
        yield c


@pytest.mark.integration
class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check(self, client):
        """Test GET /health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data


@pytest.mark.integration
class TestLeadEndpoints:
    """Test lead-related endpoints."""
    
    def test_create_lead(self, client):
        """Test POST /leads endpoint."""
        lead_data = {
            "nome": "Mario",
            "cognome": "Rossi",
            "email": f"mario{uuid.uuid4().hex[:8]}@rossi.it",
            "telefono": "+393451234567",
            "azienda": "Rossi Srl"
        }
        response = client.post("/leads", json=lead_data)
        assert response.status_code == 201
        data = response.json()
        assert data["nome"] == "Mario"
        assert data["email"] == lead_data["email"]
        return data["id"]
    
    def test_get_leads(self, client):
        """Test GET /leads endpoint."""
        # First create a lead
        self.test_create_lead(client)
        
        response = client.get("/leads")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
    
    def test_get_lead_by_id(self, client):
        """Test GET /leads/{id} endpoint."""
        # First create a lead
        lead_id = self.test_create_lead(client)
        
        response = client.get(f"/leads/{lead_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == lead_id
    
    def test_get_lead_not_found(self, client):
        """Test GET /leads/{id} returns 404 for non-existent lead."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/leads/{fake_id}")
        assert response.status_code == 404
    
    def test_update_lead(self, client):
        """Test PATCH /leads/{id} endpoint."""
        # First create a lead
        lead_id = self.test_create_lead(client)
        
        update_data = {"nome": "Giuseppe", "cognome": "Bianchi"}
        response = client.patch(f"/leads/{lead_id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["nome"] == "Giuseppe"
        assert data["cognome"] == "Bianchi"
    
    def test_create_lead_duplicate_email(self, client):
        """Test POST /leads returns error for duplicate email."""
        lead_data = {
            "nome": "Mario",
            "cognome": "Rossi",
            "email": f"test{uuid.uuid4().hex[:8]}@test.com",
            "telefono": "+393451234567",
            "azienda": "Test Srl"
        }
        # Create first lead
        response1 = client.post("/leads", json=lead_data)
        assert response1.status_code == 201
        
        # Try to create second lead with same email
        lead_data["nome"] = "Giuseppe"
        response2 = client.post("/leads", json=lead_data)
        assert response2.status_code == 409  # Conflict


@pytest.mark.integration
class TestQualificationEndpoints:
    """Test qualification endpoints."""
    
    @pytest.fixture
    def create_lead_for_qual(self, client):
        """Create a lead for qualification tests."""
        lead_data = {
            "nome": "Test",
            "cognome": "Qualificazione",
            "email": f"test{uuid.uuid4().hex[:8]}@qual.it",
            "telefono": "+393451234567",
            "azienda": "Qual Srl"
        }
        response = client.post("/leads", json=lead_data)
        assert response.status_code == 201
        return response.json()["id"]
    
    def test_qualify_lead(self, client, create_lead_for_qual):
        """Test POST /qualify-lead endpoint."""
        lead_id = create_lead_for_qual
        
        qual_data = {
            "lead_id": lead_id,
            "origine": "Milano",
            "destinazione": "Roma",
            "tipologia_merce": "Pallet",
            "peso_stimato_kg": 500.0,
            "dimensioni": "120x80x100",
            "frequenza": "settimanale"
        }
        response = client.post("/qualify-lead", json=qual_data)
        assert response.status_code == 201
        data = response.json()
        assert data["origine"] == "Milano"
        assert data["destinazione"] == "Roma"
    
    def test_qualify_lead_not_found(self, client):
        """Test POST /qualify-lead returns 404 for non-existent lead."""
        fake_id = str(uuid.uuid4())
        qual_data = {
            "lead_id": fake_id,
            "origine": "Milano",
            "destinazione": "Roma"
        }
        response = client.post("/qualify-lead", json=qual_data)
        assert response.status_code == 404


@pytest.mark.integration
class TestPricingEndpoints:
    """Test pricing endpoints."""
    
    @pytest.fixture
    def create_qualification_for_pricing(self, client):
        """Create a qualification for pricing tests."""
        # Create lead
        lead_data = {
            "nome": "Test",
            "cognome": "Pricing",
            "email": f"test{uuid.uuid4().hex[:8]}@pricing.it",
            "telefono": "+393451234567",
            "azienda": "Pricing Srl"
        }
        lead_response = client.post("/leads", json=lead_data)
        lead_id = lead_response.json()["id"]
        
        # Create qualification
        qual_data = {
            "lead_id": lead_id,
            "origine": "Milano",
            "destinazione": "Roma",
            "tipologia_merce": "Pallet",
            "peso_stimato_kg": 500.0
        }
        qual_response = client.post("/qualify-lead", json=qual_data)
        return qual_response.json()["id"]
    
    def test_calculate_price(self, client, create_qualification_for_pricing):
        """Test POST /calculate-price endpoint."""
        qual_id = create_qualification_for_pricing
        
        calc_data = {
            "qualificazione_id": qual_id,
            "peso_kg": 500.0,
            "carrier_code": "BRT"
        }
        response = client.post("/calculate-price", json=calc_data)
        # May return 200 or 404 depending on carrier availability
        assert response.status_code in [200, 404]
    
    def test_calculate_price_not_found(self, client):
        """Test POST /calculate-price returns 404 for non-existent qualification."""
        fake_id = str(uuid.uuid4())
        calc_data = {
            "qualificazione_id": fake_id,
            "peso_kg": 500.0
        }
        response = client.post("/calculate-price", json=calc_data)
        assert response.status_code == 404
    
    def test_source_carriers(self, client):
        """Test POST /source-carriers endpoint."""
        data = {
            "origine": "Milano",
            "destinazione": "Roma",
            "peso_kg": 500.0
        }
        response = client.post("/source-carriers", json=data)
        assert response.status_code == 200
        data = response.json()
        assert "quotes" in data


@pytest.mark.integration
class TestProposalEndpoints:
    """Test proposal endpoints."""
    
    @pytest.fixture
    def create_data_for_proposal(self, client):
        """Create lead and qualification for proposal tests."""
        # Create lead
        lead_data = {
            "nome": "Test",
            "cognome": "Proposal",
            "email": f"test{uuid.uuid4().hex[:8]}@proposal.it",
            "telefono": "+393451234567",
            "azienda": "Proposal Srl"
        }
        lead_response = client.post("/leads", json=lead_data)
        lead_id = lead_response.json()["id"]
        
        # Create qualification
        qual_data = {
            "lead_id": lead_id,
            "origine": "Milano",
            "destinazione": "Roma",
            "tipologia_merce": "Pallet",
            "peso_stimato_kg": 500.0
        }
        qual_response = client.post("/qualify-lead", json=qual_data)
        qual_id = qual_response.json()["id"]
        
        return qual_id
    
    def test_create_proposal(self, client, create_data_for_proposal):
        """Test POST /create-proposal endpoint."""
        qual_id = create_data_for_proposal
        
        proposal_data = {
            "qualificazione_id": qual_id,
            "carrier_code": "BRT",
            "prezzo_netto": 340.00,
            "prezzo_finale": 425.00,
            "tempi_consegna_giorni": 1
        }
        response = client.post("/create-proposal", json=proposal_data)
        assert response.status_code == 201
        data = response.json()
        assert data["prezzo_finale"] == 425.00
    
    def test_create_proposal_not_found(self, client):
        """Test POST /create-proposal returns 404 for non-existent qualification."""
        fake_id = str(uuid.uuid4())
        proposal_data = {
            "qualificazione_id": fake_id,
            "carrier_code": "BRT",
            "prezzo_netto": 340.00,
            "prezzo_finale": 425.00
        }
        response = client.post("/create-proposal", json=proposal_data)
        assert response.status_code == 404


@pytest.mark.integration
class TestWebhookEndpoints:
    """Test webhook endpoints."""
    
    def test_retell_webhook(self, client):
        """Test POST /retell-webhook endpoint."""
        webhook_data = {
            "call_id": "call-test-123",
            "event": "call_completed",
            "transcript": "Test transcript",
            "lead_id": str(uuid.uuid4())
        }
        response = client.post("/retell-webhook", json=webhook_data)
        assert response.status_code in [200, 202, 404]
    
    def test_stripe_webhook(self, client):
        """Test POST /stripe-webhook endpoint."""
        webhook_data = {
            "id": "evt-test-123",
            "type": "invoice.payment_succeeded",
            "data": {"object": {"id": "inv-test"}}
        }
        response = client.post("/stripe-webhook", json=webhook_data)
        assert response.status_code in [200, 400, 401]
    
    def test_docusign_webhook(self, client):
        """Test POST /docusign-webhook endpoint."""
        webhook_data = {
            "event": "envelope-completed",
            "data": {
                "envelopeId": "env-test-123",
                "status": "completed"
            }
        }
        response = client.post("/docusign-webhook", json=webhook_data)
        assert response.status_code in [200, 202, 404]


@pytest.mark.integration
class TestDashboardEndpoints:
    """Test dashboard endpoints."""
    
    def test_get_dashboard_stats(self, client):
        """Test GET /stats/dashboard endpoint."""
        response = client.get("/stats/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "total_leads" in data
        assert "total_qualificazioni" in data


@pytest.mark.integration
class TestShipmentEndpoints:
    """Test shipment endpoints."""
    
    def test_get_shipment_status_not_found(self, client):
        """Test GET /shipment-status/{tracking_id} returns 404 for non-existent shipment."""
        response = client.get("/shipment-status/NONEXISTENT123")
        assert response.status_code == 404
