"""
Retry decorator with exponential backoff for transient failures

Usage:
    from decorators import retry
    from exceptions import TransientError
    
    @retry(max_attempts=3, initial_delay=1.0)
    async def fetch_data():
        # May raise TransientError
        ...
    
    @retry(max_attempts=5, backoff_factor=1.5, exceptions=(NetworkError, TimeoutError))
    async def call_api():
        ...
"""

import asyncio
import functools
import logging
import random
from typing import Callable, Type, Tuple, Optional

from exceptions import TransientError, is_retryable

logger = logging.getLogger(__name__)


def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (TransientError,),
    on_retry: Optional[Callable] = None,
):
    """
    Decorator for automatic retry with exponential backoff
    
    Args:
        max_attempts: Maximum number of attempts (including first try)
        initial_delay: Initial delay in seconds between retries
        max_delay: Maximum delay in seconds (caps exponential growth)
        backoff_factor: Multiplier for delay on each retry (2.0 = double each time)
        jitter: Add random ±25% variation to delay (prevents thundering herd)
        exceptions: Tuple of exception types that trigger retry
        on_retry: Optional callback called on each retry: fn(attempt, exc, delay)
    
    Returns:
        Decorator function
    
    Example:
        @retry(max_attempts=3, initial_delay=1.0)
        async def fetch_tv_status():
            # Will retry on TransientError
            response = await http_client.get(...)
            return response.json()
        
        @retry(max_attempts=5, backoff_factor=1.5, exceptions=(NetworkError,))
        async def ping_device(ip: str):
            # Will retry only on NetworkError
            ...
    
    Backoff formula:
        delay = min(initial_delay * (backoff_factor ^ attempt), max_delay)
        if jitter:
            delay += random.uniform(-delay*0.25, delay*0.25)
    
    Note:
        - Only retries on specified exception types
        - Logs warnings on each retry, error on final failure
        - Async functions only (for sync, remove 'await')
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    result = await func(*args, **kwargs)
                    
                    # Success! Log if this wasn't the first attempt
                    if attempt > 0:
                        logger.info(
                            f"✅ {func.__name__} succeeded on attempt {attempt + 1}/{max_attempts}",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt + 1,
                                "max_attempts": max_attempts,
                            }
                        )
                    
                    return result
                    
                except exceptions as exc:
                    last_exception = exc
                    
                    # Last attempt - no retry
                    if attempt == max_attempts - 1:
                        logger.error(
                            f"❌ {func.__name__} failed after {max_attempts} attempts: {exc}",
                            extra={
                                "function": func.__name__,
                                "attempts": max_attempts,
                                "error": str(exc),
                                "error_type": type(exc).__name__,
                            }
                        )
                        raise
                    
                    # Calculate exponential backoff delay
                    delay = min(
                        initial_delay * (backoff_factor ** attempt),
                        max_delay
                    )
                    
                    # Add jitter (±25% random variation)
                    if jitter:
                        jitter_amount = delay * 0.25 * (2 * random.random() - 1)
                        delay = max(0.1, delay + jitter_amount)  # Minimum 100ms
                    
                    logger.warning(
                        f"⚠️  {func.__name__} attempt {attempt + 1}/{max_attempts} failed: {exc}. "
                        f"Retrying in {delay:.2f}s...",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "max_attempts": max_attempts,
                            "delay": delay,
                            "error": str(exc),
                            "error_type": type(exc).__name__,
                        }
                    )
                    
                    # Optional callback
                    if on_retry:
                        try:
                            on_retry(attempt + 1, exc, delay)
                        except Exception as callback_exc:
                            logger.warning(f"on_retry callback failed: {callback_exc}")
                    
                    # Wait before retry
                    await asyncio.sleep(delay)
                
                except Exception as exc:
                    # Non-retryable exception
                    logger.error(
                        f"❌ {func.__name__} raised non-retryable exception: {exc}",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "error": str(exc),
                            "error_type": type(exc).__name__,
                        },
                        exc_info=True
                    )
                    raise
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


def retry_sync(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (TransientError,),
    on_retry: Optional[Callable] = None,
):
    """
    Synchronous version of retry decorator (no async/await)
    
    Use this for synchronous functions like ping, subprocess calls, etc.
    See retry() for full documentation.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import time
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    result = func(*args, **kwargs)
                    
                    if attempt > 0:
                        logger.info(
                            f"✅ {func.__name__} succeeded on attempt {attempt + 1}/{max_attempts}",
                            extra={"function": func.__name__, "attempt": attempt + 1}
                        )
                    
                    return result
                    
                except exceptions as exc:
                    last_exception = exc
                    
                    if attempt == max_attempts - 1:
                        logger.error(
                            f"❌ {func.__name__} failed after {max_attempts} attempts: {exc}",
                            extra={
                                "function": func.__name__,
                                "attempts": max_attempts,
                                "error": str(exc),
                            }
                        )
                        raise
                    
                    delay = min(initial_delay * (backoff_factor ** attempt), max_delay)
                    
                    if jitter:
                        jitter_amount = delay * 0.25 * (2 * random.random() - 1)
                        delay = max(0.1, delay + jitter_amount)
                    
                    logger.warning(
                        f"⚠️  {func.__name__} attempt {attempt + 1}/{max_attempts} failed: {exc}. "
                        f"Retrying in {delay:.2f}s...",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "delay": delay,
                            "error": str(exc),
                        }
                    )
                    
                    if on_retry:
                        try:
                            on_retry(attempt + 1, exc, delay)
                        except Exception:
                            pass
                    
                    time.sleep(delay)
                
                except Exception as exc:
                    logger.error(
                        f"❌ {func.__name__} raised non-retryable exception: {exc}",
                        extra={"function": func.__name__, "error": str(exc)},
                        exc_info=True
                    )
                    raise
            
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator
