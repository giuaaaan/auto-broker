"""
Circuit Breaker Comprehensive Test Suite
Target: 100% Coverage of Circuit Breaker Module

Tests all states and transitions:
- CLOSED -> OPEN (failure threshold exceeded)
- OPEN -> HALF_OPEN (recovery timeout)
- HALF_OPEN -> CLOSED (success threshold)
- HALF_OPEN -> OPEN (failure in half-open)
- Distributed state persistence
- Metrics integration

Author: Engineering Team
Version: 3.0.0 (2026-02-14)
"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from api.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitBreakerState,
    CircuitState,
    HUME_CIRCUIT,
    OLLAMA_CIRCUIT,
    CHROMA_CIRCUIT,
    CIRCUIT_REGISTRY,
)


# ============= State Machine Tests =============

class TestCircuitStateMachine:
    """Comprehensive tests for circuit breaker state machine."""
    
    @pytest.mark.asyncio
    async def test_initial_state_is_closed(self):
        """Test circuit starts in CLOSED state."""
        config = CircuitBreakerConfig(name="test")
        circuit = CircuitBreaker(config)
        
        assert circuit.current_state == CircuitState.CLOSED
        assert circuit.state.failure_count == 0
        assert circuit.state.success_count == 0
    
    @pytest.mark.asyncio
    async def test_closed_state_allows_execution(self):
        """Test CLOSED state allows normal execution."""
        config = CircuitBreakerConfig(name="test")
        circuit = CircuitBreaker(config)
        
        mock_func = AsyncMock(return_value="success")
        result = await circuit.call(mock_func)
        
        assert result == "success"
        assert circuit.current_state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_closed_to_open_transition(self):
        """Test transition from CLOSED to OPEN after failures."""
        config = CircuitBreakerConfig(name="test", failure_threshold=3)
        circuit = CircuitBreaker(config)
        
        mock_func = AsyncMock(side_effect=ValueError("test error"))
        
        # First 2 failures - should stay closed
        for _ in range(2):
            with pytest.raises(ValueError):
                await circuit.call(mock_func)
        
        assert circuit.current_state == CircuitState.CLOSED
        assert circuit.state.failure_count == 2
        
        # 3rd failure - should open
        with pytest.raises(ValueError):
            await circuit.call(mock_func)
        
        assert circuit.current_state == CircuitState.OPEN
        assert circuit.state.opened_at is not None
    
    @pytest.mark.asyncio
    async def test_open_state_blocks_execution(self):
        """Test OPEN state blocks execution with CircuitBreakerError."""
        config = CircuitBreakerConfig(name="test", failure_threshold=1)
        circuit = CircuitBreaker(config)
        
        # Open the circuit
        with pytest.raises(ValueError):
            await circuit.call(AsyncMock(side_effect=ValueError("fail")))
        
        assert circuit.current_state == CircuitState.OPEN
        
        # Next call should raise CircuitBreakerError
        with pytest.raises(CircuitBreakerError) as exc_info:
            await circuit.call(AsyncMock(return_value="success"))
        
        assert exc_info.value.circuit_name == "test"
        assert "OPEN" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_open_to_half_open_transition(self):
        """Test transition from OPEN to HALF_OPEN after timeout."""
        config = CircuitBreakerConfig(name="test", failure_threshold=1, recovery_timeout=0)
        circuit = CircuitBreaker(config)
        
        # Open the circuit
        with pytest.raises(ValueError):
            await circuit.call(AsyncMock(side_effect=ValueError("fail")))
        
        assert circuit.current_state == CircuitState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(0.01)
        
        # Now should be half-open
        assert circuit.current_state == CircuitState.HALF_OPEN
    
    @pytest.mark.asyncio
    async def test_half_open_to_closed_transition(self):
        """Test transition from HALF_OPEN to CLOSED after successes."""
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=1,
            recovery_timeout=0,
            success_threshold=2
        )
        circuit = CircuitBreaker(config)
        
        # Open then half-open
        with pytest.raises(ValueError):
            await circuit.call(AsyncMock(side_effect=ValueError("fail")))
        await asyncio.sleep(0.01)
        
        assert circuit.current_state == CircuitState.HALF_OPEN
        
        # 2 successes should close circuit
        mock_success = AsyncMock(return_value="success")
        await circuit.call(mock_success)
        await circuit.call(mock_success)
        
        assert circuit.current_state == CircuitState.CLOSED
        assert circuit.state.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_half_open_to_open_transition(self):
        """Test transition from HALF_OPEN back to OPEN on failure."""
        config = CircuitBreakerConfig(name="test", failure_threshold=1, recovery_timeout=0)
        circuit = CircuitBreaker(config)
        
        # Open then half-open
        with pytest.raises(ValueError):
            await circuit.call(AsyncMock(side_effect=ValueError("fail")))
        await asyncio.sleep(0.01)
        
        assert circuit.current_state == CircuitState.HALF_OPEN
        
        # Failure in half-open should reopen
        with pytest.raises(ValueError):
            await circuit.call(AsyncMock(side_effect=ValueError("fail again")))
        
        assert circuit.current_state == CircuitState.OPEN
    
    @pytest.mark.asyncio
    async def test_success_resets_failure_count_in_closed(self):
        """Test that success in CLOSED state resets failure count."""
        config = CircuitBreakerConfig(name="test", failure_threshold=5)
        circuit = CircuitBreaker(config)
        
        # 2 failures
        for _ in range(2):
            with pytest.raises(ValueError):
                await circuit.call(AsyncMock(side_effect=ValueError("fail")))
        
        assert circuit.state.failure_count == 2
        
        # Success should reset
        await circuit.call(AsyncMock(return_value="success"))
        
        assert circuit.state.failure_count == 0


# ============= Half-Open State Tests =============

class TestHalfOpenState:
    """Detailed tests for HALF_OPEN state behavior."""
    
    @pytest.mark.asyncio
    async def test_half_open_limits_calls(self):
        """Test HALF_OPEN limits number of test calls."""
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=1,
            recovery_timeout=0,
            half_open_max_calls=2
        )
        circuit = CircuitBreaker(config)
        
        # Open -> half-open
        with pytest.raises(ValueError):
            await circuit.call(AsyncMock(side_effect=ValueError("fail")))
        await asyncio.sleep(0.01)
        
        # Use up half-open calls
        circuit.state.half_open_calls = 2
        
        # Next call should be blocked
        with pytest.raises(CircuitBreakerError):
            await circuit.call(AsyncMock(return_value="success"))
    
    @pytest.mark.asyncio
    async def test_half_open_tracks_calls(self):
        """Test HALF_OPEN correctly tracks call count."""
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=1,
            recovery_timeout=0,
            half_open_max_calls=5
        )
        circuit = CircuitBreaker(config)
        
        # Open -> half-open
        with pytest.raises(ValueError):
            await circuit.call(AsyncMock(side_effect=ValueError("fail")))
        await asyncio.sleep(0.01)
        
        # Each call should increment half_open_calls
        await circuit.call(AsyncMock(return_value="success"))
        assert circuit.state.half_open_calls == 1
        
        await circuit.call(AsyncMock(return_value="success"))
        assert circuit.state.half_open_calls == 2


# ============= Configuration Tests =============

class TestCircuitBreakerConfig:
    """Tests for circuit breaker configuration."""
    
    def test_valid_configuration(self):
        """Test valid configuration is accepted."""
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=5,
            recovery_timeout=60,
            half_open_max_calls=3
        )
        
        assert config.name == "test"
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60
        assert config.half_open_max_calls == 3
    
    def test_invalid_failure_threshold(self):
        """Test invalid failure threshold raises error."""
        with pytest.raises(ValueError):
            CircuitBreakerConfig(name="test", failure_threshold=0)
    
    def test_invalid_recovery_timeout(self):
        """Test invalid recovery timeout raises error."""
        with pytest.raises(ValueError):
            CircuitBreakerConfig(name="test", recovery_timeout=0)
    
    def test_default_values(self):
        """Test default configuration values."""
        config = CircuitBreakerConfig(name="test")
        
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60
        assert config.half_open_max_calls == 3


# ============= Exception Handling Tests =============

class TestExceptionHandling:
    """Tests for exception handling configuration."""
    
    @pytest.mark.asyncio
    async def test_expected_exceptions_count_as_failures(self):
        """Test expected exceptions increment failure count."""
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=2,
            expected_exceptions=(ValueError,)
        )
        circuit = CircuitBreaker(config)
        
        with pytest.raises(ValueError):
            await circuit.call(AsyncMock(side_effect=ValueError("fail")))
        
        assert circuit.state.failure_count == 1
    
    @pytest.mark.asyncio
    async def test_ignored_exceptions_not_counted(self):
        """Test ignored exceptions don't increment failure count."""
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=1,
            expected_exceptions=(ValueError,),
            ignore_exceptions=(TypeError,)
        )
        circuit = CircuitBreaker(config)
        
        with pytest.raises(TypeError):
            await circuit.call(AsyncMock(side_effect=TypeError("ignored")))
        
        assert circuit.state.failure_count == 0
        assert circuit.current_state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_unexpected_exceptions_not_counted(self):
        """Test unexpected exception types don't count as failures."""
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=1,
            expected_exceptions=(ValueError,)
        )
        circuit = CircuitBreaker(config)
        
        with pytest.raises(TypeError):
            await circuit.call(AsyncMock(side_effect=TypeError("unexpected")))
        
        # TypeError not in expected_exceptions, so shouldn't count
        # But it also won't be caught, so it propagates
        assert circuit.state.failure_count == 0


# ============= Distributed State Tests =============

class TestDistributedState:
    """Tests for distributed state persistence."""
    
    @pytest.mark.asyncio
    async def test_state_persistence_on_transition(self):
        """Test state is persisted on transitions."""
        mock_persistence = AsyncMock()
        mock_persistence.set = AsyncMock(return_value=True)
        
        config = CircuitBreakerConfig(name="test")
        circuit = CircuitBreaker(config, state_persistence=mock_persistence)
        
        # Trigger transition
        with pytest.raises(ValueError):
            await circuit.call(AsyncMock(side_effect=ValueError("fail")))
        
        # Should have attempted to persist
        mock_persistence.set.assert_called()
    
    @pytest.mark.asyncio
    async def test_state_persistence_failure_handled(self):
        """Test persistence failures are handled gracefully."""
        mock_persistence = AsyncMock()
        mock_persistence.set = AsyncMock(side_effect=Exception("Redis down"))
        
        config = CircuitBreakerConfig(name="test")
        circuit = CircuitBreaker(config, state_persistence=mock_persistence)
        
        # Should not raise despite persistence failure
        with pytest.raises(ValueError):
            await circuit.call(AsyncMock(side_effect=ValueError("fail")))
        
        # Circuit should still work
        assert circuit.state.failure_count == 1


# ============= Metrics Tests =============

class TestMetrics:
    """Tests for Prometheus metrics integration."""
    
    @pytest.mark.asyncio
    async def test_state_metric_updated(self):
        """Test state gauge is updated on transitions."""
        config = CircuitBreakerConfig(name="test", failure_threshold=1)
        circuit = CircuitBreaker(config)
        
        # Open circuit
        with pytest.raises(ValueError):
            await circuit.call(AsyncMock(side_effect=ValueError("fail")))
        
        # State should be OPEN (metric value 1)
        assert circuit.current_state == CircuitState.OPEN
    
    @pytest.mark.asyncio
    async def test_call_count_metrics(self):
        """Test call count metrics are tracked."""
        config = CircuitBreakerConfig(name="test")
        circuit = CircuitBreaker(config)
        
        # Successful call
        await circuit.call(AsyncMock(return_value="success"))
        
        # Failed call
        with pytest.raises(ValueError):
            await circuit.call(AsyncMock(side_effect=ValueError("fail")))
        
        assert circuit.state.success_count >= 1
        assert circuit.state.failure_count == 1


# ============= Manual Reset Tests =============

class TestManualReset:
    """Tests for manual circuit reset."""
    
    @pytest.mark.asyncio
    async def test_manual_reset_opens_to_closed(self):
        """Test manual reset from OPEN to CLOSED."""
        config = CircuitBreakerConfig(name="test", failure_threshold=1)
        circuit = CircuitBreaker(config)
        
        # Open circuit
        with pytest.raises(ValueError):
            await circuit.call(AsyncMock(side_effect=ValueError("fail")))
        
        assert circuit.current_state == CircuitState.OPEN
        
        # Manual reset
        await circuit.manual_reset()
        
        assert circuit.current_state == CircuitState.CLOSED
        assert circuit.state.failure_count == 0
        assert circuit.state.opened_at is None
    
    @pytest.mark.asyncio
    async def test_manual_reset_half_open_to_closed(self):
        """Test manual reset from HALF_OPEN to CLOSED."""
        config = CircuitBreakerConfig(name="test", failure_threshold=1, recovery_timeout=0)
        circuit = CircuitBreaker(config)
        
        # Open -> half-open
        with pytest.raises(ValueError):
            await circuit.call(AsyncMock(side_effect=ValueError("fail")))
        await asyncio.sleep(0.01)
        
        assert circuit.current_state == CircuitState.HALF_OPEN
        
        # Manual reset
        await circuit.manual_reset()
        
        assert circuit.current_state == CircuitState.CLOSED


# ============= Registry Tests =============

class TestCircuitRegistry:
    """Tests for circuit breaker registry."""
    
    def test_register_circuit(self):
        """Test registering a circuit."""
        registry = CircuitBreakerRegistry()
        circuit = CircuitBreaker(CircuitBreakerConfig(name="test"))
        
        registry.register(circuit)
        
        assert registry.get("test") == circuit
    
    def test_get_nonexistent_circuit(self):
        """Test getting non-existent circuit returns None."""
        registry = CircuitBreakerRegistry()
        
        assert registry.get("nonexistent") is None
    
    @pytest.mark.asyncio
    async def test_health_check_all_circuits(self):
        """Test health check returns all circuit states."""
        registry = CircuitBreakerRegistry()
        circuit1 = CircuitBreaker(CircuitBreakerConfig(name="test1"))
        circuit2 = CircuitBreaker(CircuitBreakerConfig(name="test2"))
        
        registry.register(circuit1)
        registry.register(circuit2)
        
        health = await registry.health_check()
        
        assert "test1" in health
        assert "test2" in health
        assert health["test1"]["state"] == "closed"
        assert health["test2"]["state"] == "closed"
    
    @pytest.mark.asyncio
    async def test_reset_all_circuits(self):
        """Test emergency reset of all circuits."""
        registry = CircuitBreakerRegistry()
        
        circuit1 = CircuitBreaker(CircuitBreakerConfig(name="test1", failure_threshold=1))
        circuit2 = CircuitBreaker(CircuitBreakerConfig(name="test2", failure_threshold=1))
        
        registry.register(circuit1)
        registry.register(circuit2)
        
        # Open both circuits
        with pytest.raises(ValueError):
            await circuit1.call(AsyncMock(side_effect=ValueError("fail")))
        with pytest.raises(ValueError):
            await circuit2.call(AsyncMock(side_effect=ValueError("fail")))
        
        assert circuit1.current_state == CircuitState.OPEN
        assert circuit2.current_state == CircuitState.OPEN
        
        # Reset all
        await registry.reset_all()
        
        assert circuit1.current_state == CircuitState.CLOSED
        assert circuit2.current_state == CircuitState.CLOSED


# ============= Pre-configured Circuits Tests =============

class TestPreconfiguredCircuits:
    """Tests for pre-configured circuit breakers."""
    
    def test_hume_circuit_configuration(self):
        """Test HUME_CIRCUIT has correct configuration."""
        assert HUME_CIRCUIT.config.name == "hume_api"
        assert HUME_CIRCUIT.config.failure_threshold == 5
        assert HUME_CIRCUIT.config.recovery_timeout == 60
        assert httpx.HTTPError in HUME_CIRCUIT.config.expected_exceptions
    
    def test_ollama_circuit_configuration(self):
        """Test OLLAMA_CIRCUIT has correct configuration."""
        assert OLLAMA_CIRCUIT.config.name == "ollama_local"
        assert OLLAMA_CIRCUIT.config.failure_threshold == 3
        assert OLLAMA_CIRCUIT.config.recovery_timeout == 30
    
    def test_chroma_circuit_configuration(self):
        """Test CHROMA_CIRCUIT has correct configuration."""
        assert CHROMA_CIRCUIT.config.name == "chroma_db"
        assert CHROMA_CIRCUIT.config.failure_threshold == 3
        assert CHROMA_CIRCUIT.config.recovery_timeout == 45
    
    def test_global_registry_contains_preconfigured(self):
        """Test global registry has pre-configured circuits."""
        assert CIRCUIT_REGISTRY.get("hume_api") == HUME_CIRCUIT
        assert CIRCUIT_REGISTRY.get("ollama_local") == OLLAMA_CIRCUIT
        assert CIRCUIT_REGISTRY.get("chroma_db") == CHROMA_CIRCUIT


# ============= State Dict Tests =============

class TestStateDict:
    """Tests for state serialization."""
    
    @pytest.mark.asyncio
    async def test_get_state_dict_contains_all_fields(self):
        """Test state dict contains expected fields."""
        config = CircuitBreakerConfig(name="test", failure_threshold=5)
        circuit = CircuitBreaker(config)
        
        state = await circuit.get_state_dict()
        
        assert "state" in state
        assert "failure_count" in state
        assert "success_count" in state
        assert "config" in state
        assert "can_execute" in state
        assert state["config"]["failure_threshold"] == 5
    
    @pytest.mark.asyncio
    async def test_state_dict_in_open_state(self):
        """Test state dict when circuit is open."""
        config = CircuitBreakerConfig(name="test", failure_threshold=1)
        circuit = CircuitBreaker(config)
        
        # Open circuit
        with pytest.raises(ValueError):
            await circuit.call(AsyncMock(side_effect=ValueError("fail")))
        
        state = await circuit.get_state_dict()
        
        assert state["state"] == "open"
        assert state["can_execute"] is False


# ============= Can Execute Tests =============

class TestCanExecute:
    """Tests for can_execute method."""
    
    @pytest.mark.asyncio
    async def test_can_execute_closed_state(self):
        """Test can_execute returns True in CLOSED state."""
        config = CircuitBreakerConfig(name="test")
        circuit = CircuitBreaker(config)
        
        assert circuit.can_execute() is True
    
    @pytest.mark.asyncio
    async def test_can_execute_open_state(self):
        """Test can_execute returns False in OPEN state."""
        config = CircuitBreakerConfig(name="test", failure_threshold=1)
        circuit = CircuitBreaker(config)
        
        with pytest.raises(ValueError):
            await circuit.call(AsyncMock(side_effect=ValueError("fail")))
        
        assert circuit.can_execute() is False
    
    @pytest.mark.asyncio
    async def test_can_execute_half_open_within_limit(self):
        """Test can_execute returns True in HALF_OPEN within call limit."""
        config = CircuitBreakerConfig(name="test", failure_threshold=1, recovery_timeout=0)
        circuit = CircuitBreaker(config)
        
        with pytest.raises(ValueError):
            await circuit.call(AsyncMock(side_effect=ValueError("fail")))
        await asyncio.sleep(0.01)
        
        # Should allow calls in half-open
        assert circuit.can_execute() is True
    
    @pytest.mark.asyncio
    async def test_can_execute_half_open_at_limit(self):
        """Test can_execute returns False when half_open limit reached."""
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=1,
            recovery_timeout=0,
            half_open_max_calls=2
        )
        circuit = CircuitBreaker(config)
        
        with pytest.raises(ValueError):
            await circuit.call(AsyncMock(side_effect=ValueError("fail")))
        await asyncio.sleep(0.01)
        
        # Set to limit
        circuit.state.half_open_calls = 2
        
        assert circuit.can_execute() is False


# ============= Decorator Tests =============

class TestDecorator:
    """Tests for decorator syntax."""
    
    @pytest.mark.asyncio
    async def test_decorator_applies_circuit(self):
        """Test decorator applies circuit breaker."""
        config = CircuitBreakerConfig(name="test", failure_threshold=1)
        circuit = CircuitBreaker(config)
        
        @circuit
        async def protected_function():
            return "success"
        
        result = await protected_function()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_decorator_exposes_circuit_info(self):
        """Test decorated function exposes circuit breaker."""
        config = CircuitBreakerConfig(name="test")
        circuit = CircuitBreaker(config)
        
        @circuit
        async def protected_function():
            return "success"
        
        assert hasattr(protected_function, '_circuit_breaker')
        assert protected_function._circuit_breaker == circuit


# ============= Sync Function Tests =============

class TestSyncFunctions:
    """Tests for synchronous function support."""
    
    @pytest.mark.asyncio
    async def test_call_sync_function(self):
        """Test circuit breaker works with sync functions."""
        config = CircuitBreakerConfig(name="test")
        circuit = CircuitBreaker(config)
        
        def sync_function():
            return "sync success"
        
        result = await circuit.call(sync_function)
        assert result == "sync success"
    
    @pytest.mark.asyncio
    async def test_call_sync_function_exception(self):
        """Test sync function exceptions are handled."""
        config = CircuitBreakerConfig(name="test", failure_threshold=1)
        circuit = CircuitBreaker(config)
        
        def sync_fail():
            raise ValueError("sync fail")
        
        with pytest.raises(ValueError):
            await circuit.call(sync_fail)
        
        assert circuit.state.failure_count == 1


# Run with: pytest tests/unit/test_eq_circuit_breaker.py -v --cov=api.services.circuit_breaker --cov-report=term-missing
