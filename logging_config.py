"""
Structured logging configuration for Casa Intelligence
Supports both JSON (file) and human-readable (console) formats
WITH AUTOMATIC SANITIZATION OF SENSITIVE DATA
"""

import logging
import json
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class SanitizingMixin:
    """Mixin to sanitize sensitive data from log messages"""
    
    # Sensitive key patterns
    SENSITIVE_KEYS = {
        'password', 'passwd', 'pwd', 'api_key', 'apikey', 'token', 
        'secret', 'authorization', 'auth', 'bearer', 'stok', 
        'encryption_key', 'private_key', 'access_token', 'refresh_token'
    }
    
    # Regex patterns for sensitive data
    SENSITIVE_PATTERNS = [
        # API Keys (e.g., AIzaSy...)
        (r'AIza[A-Za-z0-9_-]{35}', '***GEMINI_KEY***'),
        # Bearer tokens
        (r'Bearer\s+[A-Za-z0-9_\-\.]+', 'Bearer ***TOKEN***'),
        # Email addresses
        (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '***EMAIL***'),
        # Passwords in URLs or logs
        (r'password=[\w!@#$%^&*]+', 'password=***'),
        # Generic tokens (long alphanumeric strings)
        (r'(?i)(token|key|secret|stok)[\s:=]+["\']?([A-Za-z0-9_\-\.]{20,})["\']?', r'\1=***REDACTED***'),
    ]
    
    def sanitize_message(self, message: str) -> str:
        """Remove sensitive data from message strings"""
        sanitized = message
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            sanitized = re.sub(pattern, replacement, sanitized)
        return sanitized
    
    def sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively sanitize dictionaries"""
        if not isinstance(data, dict):
            return data
        
        sanitized = {}
        for key, value in data.items():
            # Check if key is sensitive
            if key.lower() in self.SENSITIVE_KEYS:
                sanitized[key] = '***REDACTED***'
            elif isinstance(value, dict):
                sanitized[key] = self.sanitize_dict(value)
            elif isinstance(value, str):
                sanitized[key] = self.sanitize_message(value)
            elif isinstance(value, (list, tuple)):
                sanitized[key] = [
                    self.sanitize_dict(item) if isinstance(item, dict) 
                    else self.sanitize_message(item) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        
        return sanitized


class JSONFormatter(logging.Formatter, SanitizingMixin):
    """Format logs as JSON for better parsing and analysis WITH SANITIZATION"""

    def format(self, record: logging.LogRecord) -> str:
        # Sanitize message
        original_msg = record.getMessage()
        sanitized_msg = self.sanitize_message(original_msg)
        
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": sanitized_msg,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.threadName,
        }

        # Add exception info if present (sanitized)
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            log_data["exception"] = self.sanitize_message(exc_text)

        # Add custom extra fields (sanitized)
        if hasattr(record, 'extra') and record.extra:
            sanitized_extra = self.sanitize_dict(record.extra)
            log_data.update(sanitized_extra)

        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter, SanitizingMixin):
    """Format logs with colors for console output WITH SANITIZATION"""

    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        # Sanitize the message before formatting
        original_msg = record.msg
        if isinstance(original_msg, str):
            record.msg = self.sanitize_message(original_msg)
        
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        formatted = super().format(record)
        
        # Restore original message (in case record is reused)
        record.msg = original_msg
        
        return formatted


def setup_logging(
    log_file: str = "logs/casa_intelligence.log",
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
) -> logging.Logger:
    """
    Configure logging with file (JSON) and console (colored) outputs
    """
    # Create logs directory
    log_path = Path(log_file)
    log_path.parent.mkdir(exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Clear existing handlers
    root_logger.handlers.clear()

    # File handler (JSON structured logging)
    try:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(file_level)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"⚠️ Failed to setup file logging: {e}")

    # Console handler (colored, human-readable)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_formatter = ColoredFormatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    root_logger.info("Logging configured (with sanitization)")
    return root_logger


def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    **context
) -> None:
    """
    Log with structured context

    Usage:
        log_with_context(logger, "info", "Device updated", ip="192.168.1.10", online=True)
    """
    log_func = getattr(logger, level.lower(), logger.info)

    # Create a custom LogRecord with extra context
    record = logger.makeRecord(
        name=logger.name,
        level=getattr(logging, level.upper(), logging.INFO),
        fn=None,
        lno=None,
        msg=message,
        args=(),
        exc_info=None,
    )

    # Attach context
    record.extra = context

    # Call the log function
    log_func(message)
    # Manually handle the context in handlers
    for handler in logger.handlers:
        if isinstance(handler.formatter, JSONFormatter):
            # Inject context for JSON formatter
            record.__dict__.update({"extra": context})


# Convenience loggers with context
def log_integration_error(
    logger: logging.Logger,
    service: str,
    error_msg: str,
    **kwargs
) -> None:
    """Log integration errors with service context"""
    log_with_context(
        logger,
        "error",
        f"{service}: {error_msg}",
        service=service,
        **kwargs
    )


def log_network_event(
    logger: logging.Logger,
    event: str,
    devices_count: int = 0,
    duration_ms: float = 0,
    **kwargs
) -> None:
    """Log network scanning events"""
    log_with_context(
        logger,
        "info",
        f"Network: {event}",
        devices=devices_count,
        duration_ms=round(duration_ms, 2),
        **kwargs
    )
