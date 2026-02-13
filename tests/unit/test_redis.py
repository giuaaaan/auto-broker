"""
Unit tests for Redis service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.services.redis_service import RedisService, redis_service


class TestRedisService:
    """Test suite for RedisService."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test connecting to Redis successfully."""
        service = RedisService()
        
        with patch("api.services.redis_service.redis.from_url") as mock_from_url:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock()
            mock_from_url.return_value = mock_client
            
            await service.connect()
            
            assert service.client is not None
            mock_client.ping.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test connecting to Redis with failure."""
        service = RedisService()
        
        with patch("api.services.redis_service.redis.from_url") as mock_from_url:
            mock_from_url.side_effect = Exception("Connection Error")
            
            with pytest.raises(Exception, match="Connection Error"):
                await service.connect()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnecting from Redis."""
        service = RedisService()
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        service.client = mock_client
        
        await service.disconnect()
        
        mock_client.close.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_success(self):
        """Test getting a key that exists."""
        service = RedisService()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value='"test_value"')
        service.client = mock_client
        
        result = await service.get("test_key")
        
        assert result == "test_value"
        mock_client.get.assert_called_once_with("test_key")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_key_not_found(self):
        """Test getting a key that doesn't exist."""
        service = RedisService()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)
        service.client = mock_client
        
        result = await service.get("missing_key")
        
        assert result is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_not_json(self):
        """Test getting a value that's not JSON."""
        service = RedisService()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value="plain_string")
        service.client = mock_client
        
        result = await service.get("test_key")
        
        assert result == "plain_string"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_string_value(self):
        """Test setting a string value."""
        service = RedisService()
        mock_client = AsyncMock()
        mock_client.set = AsyncMock()
        service.client = mock_client
        
        result = await service.set("test_key", "test_value", expire=3600)
        
        assert result is True
        mock_client.set.assert_called_once_with("test_key", "test_value", ex=3600)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_dict_value(self):
        """Test setting a dict value (should be JSON encoded)."""
        service = RedisService()
        mock_client = AsyncMock()
        mock_client.set = AsyncMock()
        service.client = mock_client
        
        result = await service.set("test_key", {"foo": "bar"})
        
        assert result is True
        mock_client.set.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_error(self):
        """Test set handles errors."""
        service = RedisService()
        mock_client = AsyncMock()
        mock_client.set = AsyncMock(side_effect=Exception("Redis Error"))
        service.client = mock_client
        
        result = await service.set("test_key", "value")
        
        assert result is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_health_healthy(self):
        """Test check_health when Redis is healthy."""
        service = RedisService()
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock()
        mock_client.info = AsyncMock(return_value={"redis_version": "6.2"})
        service.client = mock_client
        
        result = await service.check_health()
        
        assert result["status"] == "healthy"
        assert result["version"] == "6.2"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_health_unhealthy(self):
        """Test check_health when Redis is unhealthy."""
        service = RedisService()
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(side_effect=Exception("Connection Error"))
        service.client = mock_client
        
        result = await service.check_health()
        
        assert result["status"] == "unhealthy"

    @pytest.mark.unit
    def test_redis_service_singleton(self):
        """Test that redis_service is a singleton instance."""
        assert isinstance(redis_service, RedisService)
