"""
Unit tests for Retell service.
"""
import pytest
from datetime import datetime

from api.services.retell_service import RetellService, retell_service


class TestRetellService:
    """Test suite for RetellService."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_call_returns_call_data(self):
        """Test creating a call returns call data."""
        result = await retell_service.create_call(
            phone_number="+393451234567",
            agent_id="agent_sara",
            lead_id="lead-123",
            metadata={"azienda": "Rossi Srl"}
        )
        
        assert "call_id" in result
        assert result["status"] == "queued"
        assert result["agent_id"] == "agent_sara"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_call_sara(self):
        """Test calling agent Sara."""
        result = await retell_service.call_sara(
            phone_number="+393451234567",
            lead_id="lead-123",
            azienda="Rossi Srl",
            nome="Mario"
        )
        
        assert "call_id" in result
        assert result["agent_id"] == "agent_sara"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_call_marco(self):
        """Test calling agent Marco."""
        result = await retell_service.call_marco(
            phone_number="+393451234567",
            lead_id="lead-456",
            azienda="Bianchi Srl",
            nome="Giuseppe"
        )
        
        assert "call_id" in result
        assert result["agent_id"] == "agent_marco"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_call_luigi(self):
        """Test calling agent Luigi."""
        result = await retell_service.call_luigi(
            phone_number="+393451234567",
            lead_id="lead-789",
            azienda="Verdi Srl",
            nome="Luigi",
            preventivo_id="prev-123"
        )
        
        assert "call_id" in result
        assert result["agent_id"] == "agent_luigi"
        assert result["mock"] == True

    @pytest.mark.unit
    def test_retell_service_singleton(self):
        """Test that retell_service is a singleton instance."""
        assert isinstance(retell_service, RetellService)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_call_with_api_key(self, mocker):
        """Test creating call with real API key makes HTTP request."""
        # Mock the service to have an API key
        mocker.patch.object(retell_service, "api_key", "test_api_key")
        
        mock_response = mocker.MagicMock()
        mock_response.json.return_value = {
            "call_id": "real-call-123",
            "status": "queued"
        }
        mock_response.raise_for_status = mocker.MagicMock()
        
        mock_client = mocker.AsyncMock()
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=None)
        mock_client.post = mocker.AsyncMock(return_value=mock_response)
        
        mocker.patch("httpx.AsyncClient", return_value=mock_client)
        
        result = await retell_service.create_call(
            phone_number="+393451234567",
            agent_id="agent_sara"
        )
        
        assert result["call_id"] == "real-call-123"
