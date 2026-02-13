"""
Unit tests for Pydantic schemas.
Tests schema imports and basic instantiation where possible.
"""
import pytest
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

# Import all schemas to ensure coverage
from api.schemas import (
    LeadCreate, LeadResponse, LeadUpdate, LeadBase, LeadStatus,
    QualificazioneResponse, QualifyLeadRequest, QualificazioneBase,
    FrequenzaSpedizione,
    SourceCarriersRequest, SourceCarriersResponse, CarrierQuote,
    CalculatePriceRequest, CalculatePriceResponse,
    CreateProposalRequest, CreateProposalResponse,
    RetellWebhookRequest, DocuSignWebhookRequest,
    HealthResponse, ImportResult
)


class TestLeadSchemas:
    """Test suite for Lead schemas."""

    @pytest.mark.unit
    def test_lead_create_valid(self):
        """Test creating LeadCreate with valid data."""
        lead = LeadCreate(
            nome="Mario",
            cognome="Rossi",
            email="mario@rossi.it",
            telefono="+393451234567",
            azienda="Rossi Srl"
        )
        
        assert lead.nome == "Mario"
        assert lead.email == "mario@rossi.it"
        assert lead.azienda == "Rossi Srl"

    @pytest.mark.unit
    def test_lead_update(self):
        """Test LeadUpdate schema with partial data."""
        update = LeadUpdate(
            nome="Giuseppe",
            telefono="+39333987654"
        )
        
        assert update.nome == "Giuseppe"
        assert update.cognome is None

    @pytest.mark.unit
    def test_lead_status_enum(self):
        """Test LeadStatus enum values."""
        assert LeadStatus.NUOVO == "nuovo"
        assert LeadStatus.CONVERTITO == "convertito"


class TestQualificazioneSchemas:
    """Test suite for Qualificazione schemas."""

    @pytest.mark.unit
    def test_qualificazione_base(self):
        """Test QualificazioneBase schema."""
        qual = QualificazioneBase(
            volume_kg_mensile=Decimal("1000.00"),
            lane_origine="Milano"
        )
        assert qual.lane_origine == "Milano"

    @pytest.mark.unit
    def test_frequenza_spedizione_enum(self):
        """Test FrequenzaSpedizione enum."""
        assert FrequenzaSpedizione.SETTIMANALE == "settimanale"
        assert FrequenzaSpedizione.GIORNALIERA == "giornaliera"


class TestSchemaImports:
    """Test that all schemas can be imported."""

    @pytest.mark.unit
    def test_all_schemas_imported(self):
        """Verify all expected schemas are imported."""
        # Lead schemas
        assert LeadCreate is not None
        assert LeadResponse is not None
        assert LeadUpdate is not None
        assert LeadBase is not None
        
        # Qualificazione schemas
        assert QualificazioneResponse is not None
        assert QualifyLeadRequest is not None
        
        # Carrier schemas
        assert SourceCarriersRequest is not None
        assert SourceCarriersResponse is not None
        assert CarrierQuote is not None
        
        # Pricing schemas
        assert CalculatePriceRequest is not None
        assert CalculatePriceResponse is not None
        
        # Proposal schemas
        assert CreateProposalRequest is not None
        assert CreateProposalResponse is not None
        
        # Webhook schemas
        assert RetellWebhookRequest is not None
        assert DocuSignWebhookRequest is not None
        
        # Other schemas
        assert HealthResponse is not None
        assert ImportResult is not None
