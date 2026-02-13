"""
Unit tests for email service.
"""
import pytest

from api.services.email_service import EmailService, email_service


class TestEmailService:
    """Test suite for EmailService."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_email_returns_mock_when_no_api_key(self):
        """Test sending email returns mock when no API key."""
        result = await email_service.send_email(
            to="mario@rossi.it",
            subject="Test Subject",
            html_content="<p>Test</p>"
        )
        
        assert "id" in result
        assert result["status"] == "sent"
        assert result["mock"] == True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_proposal(self):
        """Test sending proposal email."""
        result = await email_service.send_proposal(
            to="mario@rossi.it",
            nome_cliente="Mario",
            azienda="Rossi Srl",
            preventivo_id="prev-123",
            corriere_nome="BRT",
            prezzo_kg=0.85,
            prezzo_totale=425.00,
            tempi_consegna=1,
            lane_origine="Milano",
            lane_destinazione="Roma"
        )
        
        assert "id" in result
        assert result["status"] == "sent"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_proposal_with_docusign(self):
        """Test sending proposal email with DocuSign link."""
        result = await email_service.send_proposal(
            to="mario@rossi.it",
            nome_cliente="Mario",
            azienda="Rossi Srl",
            preventivo_id="prev-123",
            corriere_nome="BRT",
            prezzo_kg=0.85,
            prezzo_totale=425.00,
            tempi_consegna=1,
            lane_origine="Milano",
            lane_destinazione="Roma",
            docusign_url="https://docusign.com/sign"
        )
        
        assert "id" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_followup(self):
        """Test sending follow-up email."""
        result = await email_service.send_followup(
            to="mario@rossi.it",
            nome_cliente="Mario",
            azienda="Rossi Srl",
            tipo="gentile"
        )
        
        assert "id" in result
        assert result["status"] == "sent"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_rejection(self):
        """Test sending rejection email."""
        result = await email_service.send_rejection(
            to="mario@rossi.it",
            nome_cliente="Mario",
            azienda="Rossi Srl"
        )
        
        assert "id" in result
        assert result["status"] == "sent"

    @pytest.mark.unit
    def test_email_service_singleton(self):
        """Test that email_service is a singleton instance."""
        assert isinstance(email_service, EmailService)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_email_with_api_key(self, mocker):
        """Test sending email with real API key makes HTTP request."""
        mocker.patch.object(email_service, "api_key", "test_api_key")
        
        mock_response = mocker.MagicMock()
        mock_response.json.return_value = {"id": "real-email-123"}
        mock_response.raise_for_status = mocker.MagicMock()
        
        mock_client = mocker.AsyncMock()
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=None)
        mock_client.post = mocker.AsyncMock(return_value=mock_response)
        
        mocker.patch("httpx.AsyncClient", return_value=mock_client)
        
        result = await email_service.send_email(
            to="test@example.com",
            subject="Test",
            html_content="<p>Test</p>"
        )
        
        assert result["id"] == "real-email-123"
