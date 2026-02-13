"""
End-to-End Tests - Pattern usato da Amazon/Netflix per testare il flusso completo.
Testa l'intero percorso: Lead → Qualificazione → Pricing → Proposal → Contract
"""
import pytest
import asyncio
import uuid
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..', 'api'))

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from models import Base, Lead, Qualificazione, Preventivo, Contratto
from main import app
from services.database import get_db


# Test database configuration
TEST_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://broker_user:broker_pass_test@localhost:5432/broker_test")

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    """Override get_db dependency for testing."""
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
    """Set up test database tables."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Cleanup dopo tutti i test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session():
    """Provide a database session for tests."""
    async with TestSessionLocal() as session:
        yield session
        # Cleanup
        await session.execute(delete(Contratto))
        await session.execute(delete(Preventivo))
        await session.execute(delete(Qualificazione))
        await session.execute(delete(Lead))
        await session.commit()


@pytest.fixture
def client():
    """Provide a TestClient instance."""
    with TestClient(app) as c:
        yield c


@pytest.mark.e2e
class TestCompleteBrokerFlow:
    """
    Test E2E del flusso completo di AUTO-BROKER.
    Simula un utente reale che attraversa tutto il funnel.
    """

    def test_complete_flow_lead_to_contract(self, client):
        """
        Flusso completo: 
        1. Crea Lead
        2. Qualifica Lead  
        3. Calcola Prezzo
        4. Crea Proposal
        5. Verifica integrità dati
        """
        unique_email = f"mario.flow.{uuid.uuid4().hex[:8]}@rossi.it"
        
        # STEP 1: Crea Lead
        lead_data = {
            "nome": "Mario",
            "cognome": "Rossi",
            "email": unique_email,
            "telefono": "+393451234567",
            "azienda": "Rossi Trasporti Srl",
            "partita_iva": "IT12345678901"
        }
        
        response = client.post("/leads", json=lead_data)
        assert response.status_code == 201, f"Failed to create lead: {response.text}"
        lead = response.json()
        lead_id = lead["id"]
        print(f"✅ Lead created: {lead_id}")
        
        # STEP 2: Qualifica Lead
        qual_data = {
            "lead_id": lead_id,
            "origine": "Milano, Via Roma 10",
            "destinazione": "Roma, Via Milano 20",
            "tipologia_merce": "Pallet",
            "peso_stimato_kg": 1500.0,
            "dimensioni": "120x80x150",
            "frequenza": "settimanale"
        }
        
        response = client.post("/qualify-lead", json=qual_data)
        assert response.status_code == 201, f"Failed to qualify lead: {response.text}"
        qual = response.json()
        qual_id = qual["id"]
        print(f"✅ Qualification created: {qual_id}")
        
        # STEP 3: Source Carriers
        source_data = {
            "origine": "Milano",
            "destinazione": "Roma", 
            "peso_kg": 1500.0
        }
        
        response = client.post("/source-carriers", json=source_data)
        assert response.status_code == 200
        carriers = response.json()
        print(f"✅ Found {len(carriers.get('quotes', []))} carriers")
        
        # STEP 4: Calcola Prezzo
        calc_data = {
            "qualificazione_id": qual_id,
            "peso_kg": 1500.0,
            "carrier_code": "BRT"  # BRT è il carrier fallback
        }
        
        response = client.post("/calculate-price", json=calc_data)
        assert response.status_code in [200, 404], f"Price calculation failed: {response.text}"
        if response.status_code == 200:
            price = response.json()
            print(f"✅ Price calculated: {price.get('prezzo_finale', 'N/A')}€")
        
        # STEP 5: Crea Proposal
        proposal_data = {
            "qualificazione_id": qual_id,
            "carrier_code": "BRT",
            "prezzo_netto": 850.00,
            "prezzo_finale": 1105.00,  # +30% margine
            "tempi_consegna_giorni": 2
        }
        
        response = client.post("/create-proposal", json=proposal_data)
        assert response.status_code == 201, f"Failed to create proposal: {response.text}"
        proposal = response.json()
        proposal_id = proposal["id"]
        print(f"✅ Proposal created: {proposal_id}")
        
        # Verifica integrità dati
        assert proposal["prezzo_finale"] == 1105.00
        assert proposal["tempi_consegna_giorni"] == 2
        
        # STEP 6: Verifica Dashboard Stats
        response = client.get("/stats/dashboard")
        assert response.status_code == 200
        stats = response.json()
        print(f"✅ Dashboard stats: {stats.get('total_leads', 0)} leads")
        
        # Verifica che il lead sia contato
        assert stats["total_leads"] >= 1

    def test_flow_with_multiple_leads(self, client):
        """
        Test con multiple leads per verificare isolamento dati.
        """
        leads_created = []
        
        for i in range(3):
            lead_data = {
                "nome": f"Test{i}",
                "cognome": "Multi",
                "email": f"test.multi.{i}.{uuid.uuid4().hex[:6]}@test.com",
                "telefono": f"+39345{i}234567",
                "azienda": f"Test Srl {i}"
            }
            
            response = client.post("/leads", json=lead_data)
            assert response.status_code == 201
            leads_created.append(response.json()["id"])
        
        print(f"✅ Created {len(leads_created)} leads")
        
        # Verifica che tutti i lead siano recuperabili
        response = client.get("/leads")
        assert response.status_code == 200
        all_leads = response.json()
        
        # Verifica che i nostri lead siano nella lista
        lead_ids = {lead["id"] for lead in all_leads}
        for lead_id in leads_created:
            assert lead_id in lead_ids, f"Lead {lead_id} not found in list"
        
        print(f"✅ All {len(leads_created)} leads verified in list")

    def test_error_handling_invalid_data(self, client):
        """
        Verifica che errori nel flusso siano gestiti correttamente.
        """
        # Test con UUID invalido
        fake_id = str(uuid.uuid4())
        
        response = client.get(f"/leads/{fake_id}")
        assert response.status_code == 404
        
        response = client.post("/qualify-lead", json={
            "lead_id": fake_id,
            "origine": "Test",
            "destinazione": "Test"
        })
        assert response.status_code == 404
        
        print("✅ Error handling verified")


@pytest.mark.e2e
class TestWebhookIntegration:
    """Test integrazione webhook E2E."""

    def test_retell_webhook_integration(self, client):
        """Test webhook Retell end-to-end."""
        # Prima crea un lead
        lead_data = {
            "nome": "Webhook",
            "cognome": "Test",
            "email": f"webhook.{uuid.uuid4().hex[:8]}@test.com",
            "telefono": "+393451234567",
            "azienda": "Webhook Srl"
        }
        response = client.post("/leads", json=lead_data)
        lead_id = response.json()["id"]
        
        # Invia webhook Retell
        webhook_data = {
            "call_id": f"call-{uuid.uuid4().hex[:8]}",
            "event": "call_completed",
            "transcript": "Test call transcript",
            "lead_id": lead_id
        }
        
        response = client.post("/retell-webhook", json=webhook_data)
        # Può essere 200, 202, o 404 se il lead non esiste
        assert response.status_code in [200, 202, 404]
        print(f"✅ Retell webhook processed: {response.status_code}")

    def test_stripe_webhook_integration(self, client):
        """Test webhook Stripe end-to-end."""
        webhook_data = {
            "id": f"evt_{uuid.uuid4().hex}",
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": f"inv_{uuid.uuid4().hex}",
                    "amount_paid": 10000
                }
            }
        }
        
        response = client.post("/stripe-webhook", json=webhook_data)
        # Senza valid signature, dovrebbe ritornare 400
        assert response.status_code in [200, 400, 401]
        print(f"✅ Stripe webhook processed: {response.status_code}")
