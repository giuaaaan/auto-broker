"""
AUTO-BROKER Services Unit Tests - 100% Coverage
Tests for lines not covered by integration tests
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from decimal import Decimal

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..', 'api'))

from services.database import get_db, check_db_health


# =============================================================================
# DATABASE SERVICE - 100% Coverage
# =============================================================================
@pytest.mark.asyncio
class TestDatabaseServiceCoverage:
    """Cover database.py lines 44-45"""
    
    async def test_check_db_health_exception(self):
        """Test check_db_health when database raises exception"""
        with patch('services.database.AsyncSessionLocal') as mock_session:
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(side_effect=Exception("DB Error"))
            mock_session.return_value = mock_context
            
            result = await check_db_health()
            assert result["status"] == "unhealthy"


# =============================================================================
# REDIS SERVICE - 100% Coverage (mockato)
# =============================================================================
@pytest.mark.asyncio
class TestRedisServiceCoverage:
    """Cover redis_service.py lines 29->exit, 68-70"""
    
    async def test_redis_service_mocked(self):
        """Test redis service with mocked client"""
        from services.redis_service import RedisService
        
        service = RedisService()
        
        # Test when not connected (should return None/False)
        result_get = await service.get("test_key")
        result_set = await service.set("test_key", {"test": "value"})
        
        # Service returns None/False when not connected
        assert result_get is None or result_get == {}
        assert result_set is False


# =============================================================================
# EMAIL SERVICE - Mock tests only
# =============================================================================
@pytest.mark.asyncio
class TestEmailServiceCoverage:
    """Cover email_service.py lines 74-86"""
    
    async def test_email_service_no_api_key(self):
        """Test email service when no API key configured"""
        from services.email_service import email_service
        
        # Test all email methods with no API key
        result_proposal = await email_service.send_proposal(
            to="test@test.com",
            nome_cliente="Test",
            azienda="Test Srl",
            preventivo_id="123",
            corriere_nome="BRT",
            prezzo_kg=1.5,
            prezzo_totale=150.0,
            tempi_consegna=2,
            lane_origine="Milano",
            lane_destinazione="Roma"
        )
        assert "id" in result_proposal
        
        result_rejection = await email_service.send_rejection(
            to="test@test.com",
            nome_cliente="Test",
            azienda="Test Srl"
        )
        assert "id" in result_rejection
        
        result_followup = await email_service.send_followup(
            to="test@test.com",
            nome_cliente="Test",
            azienda="Test Srl"
        )
        assert "id" in result_followup


# =============================================================================
# STRIPE SERVICE - Mock tests
# =============================================================================



# =============================================================================
# RETELL SERVICE - Mock tests
# =============================================================================
@pytest.mark.asyncio
class TestRetellServiceCoverage:
    """Cover retell_service.py remaining lines"""
    
    async def test_retell_service_no_key(self):
        """Test retell service with no API key"""
        from services.retell_service import retell_service
        
        # Test all three agents
        result_sara = await retell_service.call_sara(
            phone_number="+393331234567",
            lead_id="123",
            azienda="Test Srl",
            nome="Mario"
        )
        assert "call_id" in result_sara
        
        result_marco = await retell_service.call_marco(
            phone_number="+393331234567",
            lead_id="123",
            azienda="Test Srl",
            nome="Mario"
        )
        assert "call_id" in result_marco
        
        result_luigi = await retell_service.call_luigi(
            phone_number="+393331234567",
            lead_id="123",
            azienda="Test Srl",
            nome="Mario",
            preventivo_id="prev_123"
        )
        assert "call_id" in result_luigi
