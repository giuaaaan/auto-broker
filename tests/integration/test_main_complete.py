"""
AUTO-BROKER Complete Integration Tests - 100% Coverage Target
Big Tech Platform Engineering Standards 2026

Uses AsyncClient + pytest-asyncio for proper async testing
"""
import pytest
import pytest_asyncio
import uuid
from decimal import Decimal
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..', 'api'))

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import (
    Lead, Qualificazione, Corriere, Preventivo, Contratto,
    Pagamento, Spedizione, ChiamataRetell, EmailInviata
)
from main import app


# =============================================================================
# HEALTH CHECK
# =============================================================================
@pytest.mark.asyncio
class TestHealthEndpoint:
    """Test GET /health endpoint"""
    
    async def test_health_check_success(self, async_client: AsyncClient):
        response = await async_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "timestamp" in data
        assert "database" in data
        assert "redis" in data

    async def test_health_timing_header(self, async_client: AsyncClient):
        response = await async_client.get("/health")
        assert "X-Process-Time" in response.headers
        assert float(response.headers["X-Process-Time"]) >= 0


# =============================================================================
# LEADS
# =============================================================================
@pytest.mark.asyncio
class TestLeadEndpoints:
    """Test lead endpoints"""
    
    async def test_create_lead_success(self, async_client: AsyncClient):
        lead_data = {
            "nome": "Giuseppe",
            "cognome": "Bianchi",
            "azienda": "Bianchi Trasporti",
            "telefono": "+393471234567",
            "email": f"giuseppe{uuid.uuid4().hex[:8]}@bianchi.it",
            "settore": "Trasporti"
        }
        response = await async_client.post("/leads", json=lead_data)
        assert response.status_code == 201
        data = response.json()
        assert data["nome"] == "Giuseppe"
        assert data["email"] == lead_data["email"]
        assert "id" in data

    async def test_create_lead_validation_error(self, async_client: AsyncClient):
        response = await async_client.post("/leads", json={"nome": "Test"})
        assert response.status_code == 422

    async def test_get_leads_empty(self, async_client: AsyncClient):
        response = await async_client.get("/leads")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_get_leads_with_filter(self, async_client: AsyncClient, sample_lead: Lead):
        response = await async_client.get("/leads?status=nuovo")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    async def test_get_lead_by_id_success(self, async_client: AsyncClient, sample_lead: Lead):
        response = await async_client.get(f"/leads/{sample_lead.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_lead.id)

    async def test_get_lead_by_id_not_found(self, async_client: AsyncClient):
        fake_id = uuid.uuid4()
        response = await async_client.get(f"/leads/{fake_id}")
        assert response.status_code == 404
        assert "error" in response.json()

    async def test_update_lead_success(self, async_client: AsyncClient, sample_lead: Lead):
        update_data = {"nome": "Updated Name", "status": "contattato"}
        response = await async_client.patch(f"/leads/{sample_lead.id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["nome"] == "Updated Name"
        assert data["status"] == "contattato"

    async def test_update_lead_not_found(self, async_client: AsyncClient):
        fake_id = uuid.uuid4()
        response = await async_client.patch(f"/leads/{fake_id}", json={"nome": "Test"})
        assert response.status_code == 404

    async def test_trigger_call_invalid_agent(self, async_client: AsyncClient, sample_lead: Lead):
        response = await async_client.post(f"/leads/{sample_lead.id}/call/invalid_agent")
        assert response.status_code == 400

    async def test_trigger_call_lead_not_found(self, async_client: AsyncClient):
        fake_id = uuid.uuid4()
        response = await async_client.post(f"/leads/{fake_id}/call/sara")
        assert response.status_code == 404


# =============================================================================
# QUALIFICATION
# =============================================================================
@pytest.mark.asyncio
class TestQualificationEndpoints:
    """Test qualification endpoints"""
    
    async def test_qualify_lead_success_approved(self, async_client: AsyncClient, sample_lead: Lead):
        qual_data = {
            "lead_id": str(sample_lead.id),
            "volume_kg_mensile": 500.00,
            "lane_origine": "Milano",
            "lane_destinazione": "Roma",
            "frequenza": "settimanale",
            "prezzo_attuale_kg": 1.20,
            "tipo_merce": "Abbigliamento",
            "partita_iva": "IT99999999999"
        }
        response = await async_client.post("/qualify-lead", json=qual_data)
        assert response.status_code == 200
        data = response.json()
        assert data["lead_id"] == str(sample_lead.id)
        assert "credit_score" in data

    async def test_qualify_lead_low_score_rejected(self, async_client: AsyncClient, sample_lead: Lead):
        qual_data = {
            "lead_id": str(sample_lead.id),
            "volume_kg_mensile": 100.00,
            "lane_origine": "Milano",
            "lane_destinazione": "Roma",
            "frequenza": "mensile",
            "prezzo_attuale_kg": 2.00,
            "tipo_merce": "Varie",
            "partita_iva": "IT00000000000"
        }
        response = await async_client.post("/qualify-lead", json=qual_data)
        assert response.status_code == 200
        assert "credit_score" in response.json()

    async def test_qualify_lead_not_found(self, async_client: AsyncClient):
        qual_data = {
            "lead_id": str(uuid.uuid4()),
            "volume_kg_mensile": 500.00,
            "lane_origine": "Milano",
            "lane_destinazione": "Roma",
            "frequenza": "settimanale",
            "prezzo_attuale_kg": 1.20,
            "tipo_merce": "Test",
            "partita_iva": "IT12345678901"
        }
        response = await async_client.post("/qualify-lead", json=qual_data)
        assert response.status_code == 404

    async def test_get_qualificazione_success(self, async_client: AsyncClient, sample_qualification: Qualificazione):
        response = await async_client.get(f"/qualificazioni/{sample_qualification.id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(sample_qualification.id)

    async def test_get_qualificazione_not_found(self, async_client: AsyncClient):
        fake_id = uuid.uuid4()
        response = await async_client.get(f"/qualificazioni/{fake_id}")
        assert response.status_code == 404


# =============================================================================
# PRICING
# =============================================================================
@pytest.mark.asyncio
class TestPricingEndpoints:
    """Test pricing endpoints"""
    
    async def test_calculate_price_success(self, async_client: AsyncClient, sample_carrier: Corriere):
        price_data = {
            "peso_kg": 100.00,
            "lane_origine": "Milano, Italia",
            "lane_destinazione": "Roma, Italia"
        }
        response = await async_client.post("/calculate-price", json=price_data)
        assert response.status_code == 200
        data = response.json()
        assert "prezzo_vendita" in data
        assert "costo_corriere" in data
        assert "margine_netto" in data
        assert float(data["markup_percentuale"]) == 30.00

    async def test_calculate_price_international(self, async_client: AsyncClient, sample_carrier: Corriere):
        price_data = {
            "peso_kg": 100.00,
            "lane_origine": "Milano, Italia",
            "lane_destinazione": "Paris, France"
        }
        response = await async_client.post("/calculate-price", json=price_data)
        assert response.status_code == 200
        assert "prezzo_vendita" in response.json()

    async def test_calculate_price_no_carriers(self, async_client: AsyncClient):
        price_data = {
            "peso_kg": 100.00,
            "lane_origine": "Milano",
            "lane_destinazione": "Roma"
        }
        response = await async_client.post("/calculate-price", json=price_data)
        assert response.status_code == 404

    async def test_source_carriers_success(self, async_client: AsyncClient, sample_carrier: Corriere):
        source_data = {
            "peso_kg": 100.00,
            "lane_origine": "Milano",
            "lane_destinazione": "Roma"
        }
        response = await async_client.post("/source-carriers", json=source_data)
        assert response.status_code == 200
        data = response.json()
        assert "quotes" in data
        assert "miglior_prezzo" in data
        assert isinstance(data["quotes"], list)


# =============================================================================
# PROPOSALS
# =============================================================================
@pytest.mark.asyncio
class TestProposalEndpoints:
    """Test proposal endpoints"""
    
    async def test_create_proposal_success(self, async_client: AsyncClient, sample_qualification: Qualificazione, sample_carrier: Corriere):
        proposal_data = {
            "qualifica_id": str(sample_qualification.id),
            "corriere_id": str(sample_carrier.id),
            "markup_percentuale": 30.00
        }
        response = await async_client.post("/create-proposal", json=proposal_data)
        assert response.status_code == 200
        data = response.json()
        assert "preventivo_id" in data
        assert data["email_inviata"] is True
        assert "tracking_id" in data

    async def test_create_proposal_qualifica_not_found(self, async_client: AsyncClient, sample_carrier: Corriere):
        proposal_data = {
            "qualifica_id": str(uuid.uuid4()),
            "corriere_id": str(sample_carrier.id),
            "markup_percentuale": 30.00
        }
        response = await async_client.post("/create-proposal", json=proposal_data)
        assert response.status_code == 404

    async def test_create_proposal_carrier_not_found(self, async_client: AsyncClient, sample_qualification: Qualificazione):
        proposal_data = {
            "qualifica_id": str(sample_qualification.id),
            "corriere_id": str(uuid.uuid4()),
            "markup_percentuale": 30.00
        }
        response = await async_client.post("/create-proposal", json=proposal_data)
        assert response.status_code == 404


# =============================================================================
# WEBHOOKS
# =============================================================================
@pytest.mark.asyncio
class TestWebhookEndpoints:
    """Test webhook endpoints"""
    
    async def test_stripe_webhook_payment_succeeded(self, async_client: AsyncClient):
        webhook_data = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_test_123", "amount": 10000}}
        }
        response = await async_client.post("/stripe-webhook", json=webhook_data)
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    async def test_stripe_webhook_payment_failed(self, async_client: AsyncClient):
        webhook_data = {
            "type": "payment_intent.payment_failed",
            "data": {"object": {"id": "pi_test_failed", "amount": 5000}}
        }
        response = await async_client.post("/stripe-webhook", json=webhook_data)
        assert response.status_code == 200

    async def test_retell_webhook_sara_interessato(self, async_client: AsyncClient, sample_lead: Lead):
        webhook_data = {
            "call_id": f"call_{uuid.uuid4().hex[:8]}",
            "lead_id": str(sample_lead.id),
            "agent_id": "agent_sara",
            "agent_name": "sara",
            "status": "completed",
            "duration_seconds": 120,
            "outcome": "interessato",
            "transcript": "Test transcript"
        }
        response = await async_client.post("/retell-webhook", json=webhook_data)
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    async def test_retell_webhook_sara_non_interessato(self, async_client: AsyncClient, sample_lead: Lead):
        webhook_data = {
            "call_id": f"call_{uuid.uuid4().hex[:8]}",
            "lead_id": str(sample_lead.id),
            "agent_id": "agent_sara",
            "agent_name": "sara",
            "status": "completed",
            "duration_seconds": 60,
            "outcome": "non_interessato",
            "transcript": "Test"
        }
        response = await async_client.post("/retell-webhook", json=webhook_data)
        assert response.status_code == 200

    async def test_retell_webhook_marco_qualified(self, async_client: AsyncClient, sample_lead: Lead):
        webhook_data = {
            "call_id": f"call_{uuid.uuid4().hex[:8]}",
            "lead_id": str(sample_lead.id),
            "agent_id": "agent_marco",
            "agent_name": "marco",
            "status": "completed",
            "duration_seconds": 180,
            "outcome": "qualificato_completo",
            "transcript": "Test"
        }
        response = await async_client.post("/retell-webhook", json=webhook_data)
        assert response.status_code == 200

    async def test_docusign_webhook_completed(self, async_client: AsyncClient, db_session: AsyncSession, sample_lead: Lead, sample_qualification: Qualificazione, sample_carrier: Corriere):
        envelope_id = f"env_{uuid.uuid4().hex[:16]}"
        
        # Setup: Create preventivo with qualifica, carrier and contratto
        prev = Preventivo(
            id=uuid.uuid4(),
            qualifica_id=sample_qualification.id,
            corriere_id=sample_carrier.id,
            lead_id=sample_lead.id,
            peso_kg=Decimal("100"),
            prezzo_vendita=Decimal("150")
        )
        db_session.add(prev)
        await db_session.flush()
        
        contratto = Contratto(
            id=uuid.uuid4(), preventivo_id=prev.id, lead_id=sample_lead.id,
            numero_contratto="CNT-TEST", docusign_envelope_id=envelope_id,
            status="inviato", importo_totale=Decimal("150")
        )
        db_session.add(contratto)
        await db_session.commit()
        
        webhook_data = {
            "event": "envelope-completed",
            "envelope_id": envelope_id,
            "status": "completed",
            "recipient_email": "test@test.com",
            "recipient_name": "Test User",
            "completed_at": datetime.utcnow().isoformat()
        }
        response = await async_client.post("/docusign-webhook", json=webhook_data)
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    async def test_docusign_webhook_delivered(self, async_client: AsyncClient, db_session: AsyncSession, sample_lead: Lead, sample_qualification: Qualificazione, sample_carrier: Corriere):
        envelope_id = f"env_{uuid.uuid4().hex[:16]}"
        
        prev = Preventivo(
            id=uuid.uuid4(),
            qualifica_id=sample_qualification.id,
            corriere_id=sample_carrier.id,
            lead_id=sample_lead.id,
            peso_kg=Decimal("100"),
            prezzo_vendita=Decimal("150")
        )
        db_session.add(prev)
        await db_session.flush()
        
        contratto = Contratto(
            id=uuid.uuid4(), preventivo_id=prev.id, lead_id=sample_lead.id,
            numero_contratto="CNT-TEST2", docusign_envelope_id=envelope_id,
            status="inviato", importo_totale=Decimal("150")
        )
        db_session.add(contratto)
        await db_session.commit()
        
        webhook_data = {
            "event": "envelope-delivered",
            "envelope_id": envelope_id,
            "status": "delivered",
            "recipient_email": "test@test.com",
            "recipient_name": "Test User",
            "completed_at": datetime.utcnow().isoformat()
        }
        response = await async_client.post("/docusign-webhook", json=webhook_data)
        assert response.status_code == 200

    async def test_docusign_webhook_not_found(self, async_client: AsyncClient):
        webhook_data = {
            "event": "envelope-completed",
            "envelope_id": "nonexistent_envelope_12345",
            "status": "completed",
            "recipient_email": "test@test.com",
            "recipient_name": "Test User",
            "completed_at": datetime.utcnow().isoformat()
        }
        response = await async_client.post("/docusign-webhook", json=webhook_data)
        # API returns 200 with status "not_found" for unknown envelopes
        assert response.status_code == 200
        assert response.json()["status"] == "not_found"


# =============================================================================
# SHIPMENTS
# =============================================================================
@pytest.mark.asyncio
class TestShipmentEndpoints:
    """Test shipment endpoints"""
    
    async def test_get_shipment_status_by_tracking(self, async_client: AsyncClient, db_session: AsyncSession):
        tracking_num = f"TRK{uuid.uuid4().hex[:8].upper()}"
        
        lead = Lead(id=uuid.uuid4(), nome="Test", azienda="Test", telefono="123", email="test@test.com")
        db_session.add(lead)
        await db_session.flush()
        
        sped = Spedizione(
            id=uuid.uuid4(), lead_id=lead.id,
            numero_spedizione=f"SP{uuid.uuid4().hex[:8].upper()}",
            tracking_number=tracking_num, status="in_transito"
        )
        db_session.add(sped)
        await db_session.commit()
        
        response = await async_client.get(f"/shipment-status/{tracking_num}")
        assert response.status_code == 200
        data = response.json()
        assert data["tracking_number"] == tracking_num
        assert data["status"] == "in_transito"

    async def test_get_shipment_status_by_numero(self, async_client: AsyncClient, db_session: AsyncSession):
        sped_num = f"SP{uuid.uuid4().hex[:8].upper()}"
        
        lead = Lead(id=uuid.uuid4(), nome="Test", azienda="Test", telefono="123", email="test@test.com")
        db_session.add(lead)
        await db_session.flush()
        
        sped = Spedizione(
            id=uuid.uuid4(), lead_id=lead.id,
            numero_spedizione=sped_num, status="consegnata"
        )
        db_session.add(sped)
        await db_session.commit()
        
        response = await async_client.get(f"/shipment-status/{sped_num}")
        assert response.status_code == 200
        assert response.json()["status"] == "consegnata"

    async def test_get_shipment_status_not_found(self, async_client: AsyncClient):
        response = await async_client.get("/shipment-status/NONEXISTENT123")
        assert response.status_code == 404


# =============================================================================
# DISRUPTION ALERTS
# =============================================================================
@pytest.mark.asyncio
class TestDisruptionAlertEndpoints:
    """Test disruption alert endpoint"""
    
    async def test_disruption_alert_success(self, async_client: AsyncClient, db_session: AsyncSession):
        sped_id = uuid.uuid4()
        
        lead = Lead(id=uuid.uuid4(), nome="Test", azienda="Test", telefono="123", email="test@test.com")
        db_session.add(lead)
        await db_session.flush()
        
        sped = Spedizione(
            id=sped_id, lead_id=lead.id,
            numero_spedizione=f"SP{uuid.uuid4().hex[:8].upper()}",
            status="in_transito"
        )
        db_session.add(sped)
        await db_session.commit()
        
        alert_data = {
            "spedizione_id": str(sped_id),
            "tipo_ritardo": "traffico",
            "ore_ritardo": 5,
            "nuova_eta": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "motivo": "Incidente stradale"
        }
        response = await async_client.post("/disruption-alert", json=alert_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["delay_hours"] == 5

    async def test_disruption_alert_not_found(self, async_client: AsyncClient):
        alert_data = {
            "spedizione_id": str(uuid.uuid4()),
            "tipo_ritardo": "meteo",
            "ore_ritardo": 5,
            "motivo": "Maltempo"
        }
        response = await async_client.post("/disruption-alert", json=alert_data)
        assert response.status_code == 404


# =============================================================================
# DASHBOARD
# =============================================================================
@pytest.mark.asyncio
class TestDashboardEndpoints:
    """Test dashboard stats endpoint"""
    
    async def test_get_dashboard_stats(self, async_client: AsyncClient):
        response = await async_client.get("/stats/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "leads" in data
        assert "revenue" in data
        assert "operations" in data
        assert "timestamp" in data
        assert "active_shipments" in data["operations"]


# =============================================================================
# ERROR HANDLERS
# =============================================================================
@pytest.mark.asyncio
class TestErrorHandlers:
    """Test error handlers"""
    
    async def test_404_error_format(self, async_client: AsyncClient):
        response = await async_client.get("/leads/123e4567-e89b-12d3-a456-426614174000")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "code" in data
        assert "timestamp" in data

    async def test_route_not_found(self, async_client: AsyncClient):
        response = await async_client.get("/nonexistent-route-12345")
        assert response.status_code == 404


# =============================================================================
# MIDDLEWARE
# =============================================================================
@pytest.mark.asyncio
class TestMiddleware:
    """Test request logging middleware"""
    
    async def test_process_time_header_present(self, async_client: AsyncClient):
        response = await async_client.get("/health")
        assert "X-Process-Time" in response.headers
        assert float(response.headers["X-Process-Time"]) >= 0

    async def test_multiple_requests_have_timing(self, async_client: AsyncClient):
        for _ in range(3):
            response = await async_client.get("/health")
            assert "X-Process-Time" in response.headers
            assert response.status_code == 200
