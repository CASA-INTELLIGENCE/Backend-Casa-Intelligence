"""
Circuit Breaker pattern to prevent cascading failures

Protects external services (TV, Alexa, Router) from being overwhelmed when failing.

States:
- CLOSED: Normal operation, all requests pass through
- OPEN: Too many failures, reject requests immediately  
- HALF_OPEN: Testing if service recovered, allow limited requests

Example:
    tv_breaker = CircuitBreaker(name="samsung_tv", failure_threshold=5, timeout=60)
    
    async def get_tv_status():
        return await tv_breaker.call(samsung_api.get_status)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Optional, Any
from exceptions import ServiceUnavailableError

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is OPEN and rejects request"""
    def __init__(self, circuit_name: str, message: str = None):
        self.circuit_name = circuit_name
        msg = message or f"Circuit breaker '{circuit_name}' is OPEN (too many failures)"
        super().__init__(msg)


class CircuitBreaker:
    """
    Circuit breaker to protect external services from cascading failures
    
    When a service fails repeatedly, the breaker "opens" and fast-fails
    subsequent requests without calling the service. After a timeout,
    it allows one test request (HALF_OPEN). If successful, circuit closes.
    
    Args:
        name: Circuit identifier (e.g., "samsung_tv", "alexa")
        failure_threshold: Failures needed to open circuit (default: 5)
        success_threshold: Successes in HALF_OPEN to close circuit (default: 2)
        timeout: Seconds before trying HALF_OPEN after OPEN (default: 60)
        expected_exceptions: Exceptions that count as failures (default: all)
    
    Example:
        tv_breaker = CircuitBreaker(name="samsung_tv", failure_threshold=3, timeout=30)
        
        async def get_tv_status():
            # Automatically protected
            return await tv_breaker.call(samsung_api.get_status)
        
        # Or as decorator
        @tv_breaker.protect
        async def turn_on_tv():
            await samsung_api.power_on()
    
    Typical thresholds:
        - Critical service: failure_threshold=3, timeout=30
        - Non-critical service: failure_threshold=5, timeout=60
        - Slow service: failure_threshold=10, timeout=120
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: int = 60,
        expected_exceptions: tuple = (Exception,),
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.expected_exceptions = expected_exceptions
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_state_change: datetime = datetime.utcnow()
        
        # For thread-safety (though we're async, helps with tests)
        self._lock = asyncio.Lock()
        
        logger.info(
            f"🔌 Circuit breaker '{name}' initialized: "
            f"failure_threshold={failure_threshold}, timeout={timeout}s"
        )
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function protected by circuit breaker
        
        Args:
            func: Async function to call
            *args, **kwargs: Arguments to pass to function
        
        Returns:
            Function result
        
        Raises:
            CircuitBreakerOpenError: If circuit is OPEN
            Exception: Original exception from function
        """
        # Check state and possibly transition
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    time_remaining = self._time_until_half_open()
                    logger.warning(
                        f"⚠️  Circuit '{self.name}' is OPEN. "
                        f"Retry in {time_remaining:.0f}s",
                        extra={
                            "circuit": self.name,
                            "state": "OPEN",
                            "time_remaining": time_remaining,
                        }
                    )
                    raise CircuitBreakerOpenError(
                        self.name,
                        f"Circuit OPEN. Retry in {time_remaining:.0f}s"
                    )
        
        # Execute function
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
            
        except self.expected_exceptions as exc:
            await self._on_failure(exc)
            raise
    
    def protect(self, func: Callable) -> Callable:
        """
        Decorator to protect an async function with circuit breaker
        
        Example:
            @tv_breaker.protect
            async def get_status():
                return await api.get(...)
        """
        async def wrapper(*args, **kwargs):
            return await self.call(func, *args, **kwargs)
        return wrapper
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try HALF_OPEN"""
        if self.last_failure_time is None:
            return True
        
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.timeout
    
    def _time_until_half_open(self) -> float:
        """Seconds until circuit will try HALF_OPEN"""
        if self.last_failure_time is None:
            return 0.0
        
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return max(0.0, self.timeout - elapsed)
    
    def _transition_to_half_open(self):
        """Transition from OPEN to HALF_OPEN"""
        logger.info(
            f"🔄 Circuit '{self.name}': OPEN -> HALF_OPEN (testing recovery)",
            extra={"circuit": self.name, "state": "HALF_OPEN"}
        )
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        self.last_state_change = datetime.utcnow()
    
    async def _on_success(self):
        """Handle successful function execution"""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                logger.info(
                    f"✅ Circuit '{self.name}' success in HALF_OPEN "
                    f"({self.success_count}/{self.success_threshold})",
                    extra={
                        "circuit": self.name,
                        "state": "HALF_OPEN",
                        "success_count": self.success_count,
                    }
                )
                
                if self.success_count >= self.success_threshold:
                    self._transition_to_closed()
            
            elif self.state == CircuitState.OPEN:
                # Shouldn't happen, but just in case
                self._transition_to_closed()
            
            # In CLOSED state, reset failure count on success
            else:
                if self.failure_count > 0:
                    logger.debug(
                        f"Circuit '{self.name}' success, resetting failure count "
                        f"({self.failure_count} -> 0)"
                    )
                self.failure_count = 0
    
    async def _on_failure(self, exc: Exception):
        """Handle failed function execution"""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.utcnow()
            
            if self.state == CircuitState.HALF_OPEN:
                logger.warning(
                    f"⚠️  Circuit '{self.name}' failed in HALF_OPEN: {exc}",
                    extra={
                        "circuit": self.name,
                        "state": "HALF_OPEN",
                        "error": str(exc),
                    }
                )
                self._transition_to_open()
            
            elif self.state == CircuitState.CLOSED:
                logger.warning(
                    f"⚠️  Circuit '{self.name}' failure "
                    f"({self.failure_count}/{self.failure_threshold}): {exc}",
                    extra={
                        "circuit": self.name,
                        "state": "CLOSED",
                        "failure_count": self.failure_count,
                        "error": str(exc),
                    }
                )
                
                if self.failure_count >= self.failure_threshold:
                    self._transition_to_open()
    
    def _transition_to_open(self):
        """Transition to OPEN state (circuit trips)"""
        logger.error(
            f"🚨 Circuit '{self.name}': {self.state.value} -> OPEN "
            f"(threshold reached: {self.failure_count} failures)",
            extra={
                "circuit": self.name,
                "state": "OPEN",
                "failure_count": self.failure_count,
                "timeout": self.timeout,
            }
        )
        self.state = CircuitState.OPEN
        self.last_state_change = datetime.utcnow()
    
    def _transition_to_closed(self):
        """Transition to CLOSED state (circuit recovers)"""
        logger.info(
            f"✅ Circuit '{self.name}': {self.state.value} -> CLOSED (recovered)",
            extra={"circuit": self.name, "state": "CLOSED"}
        )
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_state_change = datetime.utcnow()
    
    def get_status(self) -> dict:
        """Get current circuit breaker status"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "time_until_half_open": self._time_until_half_open() if self.state == CircuitState.OPEN else None,
        }
    
    def reset(self):
        """Manually reset circuit to CLOSED (for testing or admin override)"""
        logger.warning(
            f"⚠️  Circuit '{self.name}' manually reset to CLOSED",
            extra={"circuit": self.name}
        )
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = datetime.utcnow()
