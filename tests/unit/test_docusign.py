"""
Unit tests for DocuSign service.
"""
import json
import pytest
from datetime import datetime

from api.services.docusign_service import DocuSignService, docusign_service


class TestDocuSignService:
    """Test suite for DocuSignService."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_envelope_returns_mock_when_no_config(self):
        """Test creating envelope returns mock when no config."""
        result = await docusign_service.create_envelope(
            document_base64="dGVzdA==",
            document_name="contratto.pdf",
            signer_name="Mario Rossi",
            signer_email="mario@rossi.it",
            subject="Firma Contratto"
        )
        
        assert "envelope_id" in result
        assert result["status"] == "sent"
        assert result["mock"] == True
        assert "recipient_view_url" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_envelope_with_metadata(self):
        """Test creating envelope with metadata."""
        result = await docusign_service.create_envelope(
            document_base64="dGVzdA==",
            document_name="contratto.pdf",
            signer_name="Mario Rossi",
            signer_email="mario@rossi.it",
            subject="Firma Contratto - Rossi Srl",
            metadata={"contract_id": "contr-123", "lead_id": "lead-456"}
        )
        
        assert "envelope_id" in result
        assert result["status"] == "sent"

    @pytest.mark.unit
    def test_parse_webhook_completed(self):
        """Test parsing completed webhook."""
        payload = json.dumps({
            "event": "envelope-completed",
            "envelopeId": "env-123-456",
            "status": "completed"
        }).encode()
        
        result = docusign_service.parse_webhook(payload)
        
        assert result["event"] == "envelope-completed"
        assert result["envelope_id"] == "env-123-456"
        assert result["status"] == "completed"
        assert result["completed"] == True

    @pytest.mark.unit
    def test_parse_webhook_sent(self):
        """Test parsing sent webhook."""
        payload = json.dumps({
            "event": "envelope-sent",
            "envelopeId": "env-789",
            "status": "sent"
        }).encode()
        
        result = docusign_service.parse_webhook(payload)
        
        assert result["event"] == "envelope-sent"
        assert result["completed"] == False

    @pytest.mark.unit
    def test_parse_webhook_invalid_json(self):
        """Test parsing invalid webhook payload."""
        payload = b"invalid json"
        
        result = docusign_service.parse_webhook(payload)
        
        assert "error" in result

    @pytest.mark.unit
    def test_docusign_service_singleton(self):
        """Test that docusign_service is a singleton instance."""
        assert isinstance(docusign_service, DocuSignService)
