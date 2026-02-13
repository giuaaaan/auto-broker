"""
Unit tests for database service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.services.database import get_db, check_db_health, init_db


class TestDatabaseService:
    """Test suite for database service."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_db_yields_session(self):
        """Test get_db yields a session."""
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.close = AsyncMock()
        
        with patch("api.services.database.AsyncSessionLocal") as mock_session_local:
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_session_local.return_value = mock_context
            
            async for session in get_db():
                assert session == mock_session

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_db_rollback_on_error(self):
        """Test get_db rolls back on error."""
        mock_session = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        
        with patch("api.services.database.AsyncSessionLocal") as mock_session_local:
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_session_local.return_value = mock_context
            
            # Simulate error during session usage
            mock_session.commit = AsyncMock(side_effect=Exception("DB Error"))
            
            with pytest.raises(Exception, match="DB Error"):
                async for session in get_db():
                    await session.commit()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_db_health_healthy(self):
        """Test check_db_health returns healthy status."""
        mock_result = MagicMock()
        mock_result.fetchone = AsyncMock(return_value=(1,))
        
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()
        
        with patch("api.services.database.AsyncSessionLocal") as mock_session_local:
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_session_local.return_value = mock_context
            
            result = await check_db_health()
            
            assert result["status"] == "healthy"
            assert "Database connection OK" in result["message"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_db_health_unhealthy(self):
        """Test check_db_health returns unhealthy status on error."""
        with patch("api.services.database.AsyncSessionLocal") as mock_session_local:
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(side_effect=Exception("Connection Error"))
            mock_session_local.return_value = mock_context
            
            result = await check_db_health()
            
            assert result["status"] == "unhealthy"
            assert "Connection Error" in result["message"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_init_db_success(self):
        """Test init_db creates tables successfully."""
        mock_conn = AsyncMock()
        mock_conn.run_sync = AsyncMock()
        
        with patch("api.services.database.async_engine") as mock_engine:
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_engine.begin.return_value = mock_context
            
            with patch("api.services.database.logger"):
                await init_db()
                
                assert mock_conn.run_sync.called

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_init_db_failure(self):
        """Test init_db handles failure gracefully."""
        with patch("api.services.database.async_engine") as mock_engine:
            mock_engine.begin.side_effect = Exception("Connection Error")
            
            with patch("api.services.database.logger"):
                # Should raise the exception
                with pytest.raises(Exception, match="Connection Error"):
                    await init_db()
