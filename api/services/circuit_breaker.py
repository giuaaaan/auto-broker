"""
Circuit Breaker - Netflix-style implementation
Thread-safe and asyncio-compliant
"""

import asyncio
import time
from enum import Enum
from typing import Optional, Callable, Any
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject fast
    HALF_OPEN = "half_open" # Testing if recovered


class CircuitBreaker:
    """
    Production-grade Circuit Breaker implementation.
    
    Features:
    - Thread-safe with asyncio.Lock
    - Three-state machine: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
    - Automatic recovery after timeout
    - Configurable thresholds per service
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        expected_exception: type = Exception,
        half_open_max_calls: int = 3
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.half_open_max_calls = half_open_max_calls
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.
        
        Raises:
            Exception: If circuit is OPEN
            expected_exception: If function fails
        """
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_failure_time > self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    self._success_count = 0
                    logger.info(f"Circuit {self.name} entering HALF_OPEN")
                else:
                    raise Exception(f"Circuit {self.name} is OPEN")
            
            elif self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise Exception(f"Circuit {self.name} is OPEN (half-open limit reached)")
                self._half_open_calls += 1
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            await self._on_success()
            return result
        except self.expected_exception as e:
            await self._on_failure()
            raise e
    
    async def _on_success(self):
        """Handle successful execution."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= 2:  # Need 2 consecutive successes to close
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info(f"Circuit {self.name} CLOSED after recovery")
            elif self._state == CircuitState.CLOSED:
                self._failure_count = max(0, self._failure_count - 1)
    
    async def _on_failure(self):
        """Handle failed execution."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                # Immediately reopen on failure in half-open
                self._state = CircuitState.OPEN
                logger.error(f"Circuit {self.name} reopened - recovery failed")
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.error(f"Circuit {self.name} OPEN after {self._failure_count} failures")
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for timeout transitions."""
        # Check if we should transition from OPEN to HALF_OPEN
        if self._state == CircuitState.OPEN and self._last_failure_time is not None:
            if time.time() - self._last_failure_time > self.recovery_timeout:
                # Note: This transition will be fully handled on next call()
                # but we return HALF_OPEN to indicate readiness for testing
                return CircuitState.HALF_OPEN
        return self._state
    
    async def _check_and_transition(self) -> CircuitState:
        """Check timeout and transition state if needed."""
        async with self._lock:
            if self._state == CircuitState.OPEN and self._last_failure_time is not None:
                if time.time() - self._last_failure_time > self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    self._success_count = 0
                    logger.info(f"Circuit {self.name} entering HALF_OPEN")
            return self._state
    
    def get_state_dict(self) -> dict:
        """Get circuit state as dictionary for health checks."""
        return {
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "half_open_calls": self._half_open_calls,
            "last_failure": self._last_failure_time
        }
    
    async def reset(self):
        """Manually reset circuit to CLOSED."""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._last_failure_time = None
            logger.warning(f"Circuit {self.name} manually reset")


# Pre-configured circuit breakers
HUME_CIRCUIT = CircuitBreaker("hume_api", failure_threshold=3, recovery_timeout=60)
OLLAMA_CIRCUIT = CircuitBreaker("ollama", failure_threshold=5, recovery_timeout=30)
CHROMA_CIRCUIT = CircuitBreaker("chroma_db", failure_threshold=3, recovery_timeout=45)
