"""
Exception classes and error handling for smart home integrations
Provides structured error information for better debugging and UX

Hierarchy:
- CasaIntelligenceError (base)
  - TransientError (retryable)
    - NetworkError
    - ServiceUnavailableError 
    - DeviceOfflineError
    - DeviceCommandError
  - PermanentError (not retryable)
    - AuthenticationError
    - ConfigurationError
    - ValidationError
    - DeviceNotFoundError
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


# ============================================================================
# Legacy Error Classification (kept for backwards compatibility)
# ============================================================================

class ErrorSeverity(Enum):
    """How severe is the error and will it self-resolve?"""
    RECOVERABLE = "recoverable"      # Will likely recover on next attempt
    DEGRADED = "degraded"            # Limited functionality but not critical
    CRITICAL = "critical"            # Service completely unavailable


class ErrorCategory(Enum):
    """Type of error for better classification"""
    NETWORK_TIMEOUT = "network_timeout"      # Connection timeout
    AUTHENTICATION = "authentication"        # Auth/permission issue
    DEVICE_OFFLINE = "device_offline"        # Device not reachable
    API_ERROR = "api_error"                  # Unexpected API response
    INVALID_CONFIG = "invalid_config"        # Missing/wrong configuration
    UNKNOWN = "unknown"                      # Unknown error


@dataclass
class IntegrationError:
    """Structured error information for integrations"""
    service: str                               # "samsung_tv", "router", "alexa"
    category: ErrorCategory
    severity: ErrorSeverity
    message: str                               # User-friendly message
    raw_error: Optional[str] = None            # Raw exception message
    retry_possible: bool = True                # Can retry help?
    recovery_hint: Optional[str] = None        # Suggestion to fix

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict"""
        return {
            "service": self.service,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "retry_possible": self.retry_possible,
            "recovery_hint": self.recovery_hint,
        }


# ============================================================================
# New Exception Hierarchy (Preferred)
# ============================================================================

class CasaIntelligenceError(Exception):
    """Base exception for all Casa Intelligence errors"""
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict"""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


# ============================================================================
# Transient Errors (Retryable)
# ============================================================================

class TransientError(CasaIntelligenceError):
    """Error that may resolve on retry (network issues, temporary unavailability)"""
    pass


class NetworkError(TransientError):
    """Network-related errors (timeout, connection refused, DNS failure)"""
    pass


class ServiceUnavailableError(TransientError):
    """Service temporarily unavailable (503, overload, maintenance)"""
    pass


class DeviceOfflineError(TransientError):
    """Device is powered off or temporarily unreachable"""
    def __init__(self, device_name: str, message: str = None, details: dict = None):
        self.device_name = device_name
        msg = message or f"Device {device_name} is offline"
        super().__init__(msg, details or {})
        self.details["device"] = device_name


class DeviceCommandError(TransientError):
    """Command sent to device failed but may succeed on retry"""
    def __init__(self, device_name: str, command: str, message: str = None, details: dict = None):
        self.device_name = device_name
        self.command = command
        msg = message or f"Command '{command}' failed on device {device_name}"
        super().__init__(msg, details or {})
        self.details.update({"device": device_name, "command": command})


# ============================================================================
# Permanent Errors (Not Retryable)
# ============================================================================

class PermanentError(CasaIntelligenceError):
    """Error that will not resolve with retry (config issues, auth failures)"""
    pass


class AuthenticationError(PermanentError):
    """Authentication or authorization failure"""
    pass


class ConfigurationError(PermanentError):
    """Invalid configuration or missing required settings"""
    pass


class ValidationError(PermanentError):
    """Invalid input data or parameters"""
    pass


class DeviceNotFoundError(PermanentError):
    """Device does not exist or cannot be found"""
    def __init__(self, device_name: str, message: str = None, details: dict = None):
        self.device_name = device_name
        msg = message or f"Device {device_name} not found"
        super().__init__(msg, details or {})
        self.details["device"] = device_name


# ============================================================================
# Exception Classification Helpers
# ============================================================================

def classify_exception(exc: Exception) -> CasaIntelligenceError:
    """
    Convert standard Python exceptions to Casa Intelligence exceptions
    
    Args:
        exc: Standard exception (TimeoutError, ConnectionError, etc.)
    
    Returns:
        CasaIntelligenceError subclass appropriate for the error type
    
    Example:
        try:
            await client.request(...)
        except Exception as e:
            raise classify_exception(e)
    """
    import asyncio
    
    # Already a CasaIntelligenceError
    if isinstance(exc, CasaIntelligenceError):
        return exc
    
    # Timeouts
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return NetworkError("Request timeout", {"original": str(exc)})
    
    # Connection errors
    if isinstance(exc, (ConnectionError, ConnectionRefusedError, ConnectionResetError)):
        return NetworkError(f"Connection error: {exc}", {"original": str(exc)})
    
    # OSError variants
    if isinstance(exc, OSError):
        if exc.errno == 111:  # Connection refused
            return NetworkError("Connection refused", {"original": str(exc)})
        elif exc.errno == 110:  # Connection timed out
            return NetworkError("Connection timed out", {"original": str(exc)})
        return NetworkError(f"OS error: {exc}", {"original": str(exc), "errno": exc.errno})
    
    # HTTP errors (aiohttp, requests)
    try:
        from aiohttp import ClientError, ServerTimeoutError
        
        if isinstance(exc, ServerTimeoutError):
            return NetworkError("Server timeout", {"original": str(exc)})
        
        if isinstance(exc, ClientError):
            if hasattr(exc, 'status'):
                if exc.status in (401, 403):
                    return AuthenticationError(f"Authentication failed: {exc}", {"status": exc.status})
                elif exc.status == 404:
                    return DeviceNotFoundError("unknown", "Resource not found", {"status": exc.status})
                elif exc.status >= 500:
                    return ServiceUnavailableError(f"Server error: {exc}", {"status": exc.status})
            return NetworkError(f"Client error: {exc}", {"original": str(exc)})
    except ImportError:
        pass
    
    # Default: treat as transient error
    return TransientError(
        f"Unexpected error: {exc}",
        {"original": str(exc), "type": type(exc).__name__}
    )


def is_retryable(exc: Exception) -> bool:
    """
    Check if an exception should trigger a retry
    
    Args:
        exc: Any exception
    
    Returns:
        True if exception is retryable (TransientError), False otherwise
    """
    if isinstance(exc, TransientError):
        return True
    
    # Classify and check
    classified = classify_exception(exc)
    return isinstance(classified, TransientError)
