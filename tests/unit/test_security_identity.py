"""
AUTO-BROKER Security & Identity Tests
Zero Trust Architecture Validation
P0 Critical - 100% Coverage Required
"""

import pytest
import asyncio
import jwt
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from security.identity_provider import (
    IdentityProvider, JWTClaims, UserRole,
    CircuitBreaker, CircuitState
)
from security.rbac_matrix import RBACMatrix, Permission, PermissionLevel, Resource, Action
from security.pii_masking import PIIMasker


class TestCircuitBreaker:
    """Tests for Circuit Breaker pattern."""
    
    @pytest.mark.asyncio
    async def test_initial_state_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_opens_after_failures(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        
        for _ in range(3):
            try:
                await cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        
        assert cb.state == CircuitState.OPEN
    
    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)
        
        try:
            await cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        except Exception:
            pass
        
        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN


class TestRBACMatrix:
    """Tests for RBAC authorization."""
    
    def test_broker_permissions(self):
        # Broker can read own leads
        assert RBACMatrix.has_permission(
            UserRole.BROKER, Resource.LEADS, Action.READ, PermissionLevel.OWN
        )
        
        # Broker cannot delete other org leads
        assert not RBACMatrix.has_permission(
            UserRole.BROKER, Resource.LEADS, Action.DELETE, PermissionLevel.ORG
        )
    
    def test_admin_full_access(self):
        # Admin has global access
        assert RBACMatrix.has_permission(
            UserRole.ADMIN, Resource.SECRETS, Action.EXECUTE, PermissionLevel.GLOBAL
        )


class TestPIIMasking:
    """Tests for PII protection."""
    
    def test_mask_email(self):
        masker = PIIMasker()
        result = masker.mask_text("Contact john.doe@example.com for info")
        assert "john.doe@example.com" not in result
        assert "***" in result
    
    def test_mask_phone(self):
        masker = PIIMasker()
        result = masker.mask_text("Call +39 333 123 4567")
        assert "333 123 4567" not in result
        assert "*** ***" in result


# Run with: pytest tests/unit/test_security_identity.py -v
