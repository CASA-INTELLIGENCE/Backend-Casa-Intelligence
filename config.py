"""
Configuration module with validation
Ensures all required credentials are present before starting
"""
import os
import sys
import logging
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing"""
    pass


class Settings:
    """Application settings with validation"""
    
    def __init__(self):
        # Load all settings
        self.router_ip: str = os.getenv("ROUTER_IP", "192.168.0.1")
        self.router_username: str = os.getenv("ROUTER_USERNAME", "admin")
        self.router_password: str = os.getenv("ROUTER_PASSWORD", "")
        self.samsung_tv_ip: str = os.getenv("SAMSUNG_TV_IP", "")
        self.amazon_email: str = os.getenv("AMAZON_EMAIL", "")
        self.amazon_password: str = os.getenv("AMAZON_PASSWORD", "")
        self.alexa_email: str = os.getenv("AMAZON_EMAIL", "")  # Alias for consistency
        self.alexa_password: str = os.getenv("AMAZON_PASSWORD", "")  # Alias for consistency
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
        self.encryption_key: str = os.getenv("ENCRYPTION_KEY", "")
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        self.environment: str = os.getenv("ENVIRONMENT", "development")
        
        # Validate on initialization
        self._validate()
    
    def _require(self, key: str, value: str, help_text: str) -> str:
        """Validate required setting"""
        if not value or value.strip() == "":
            error_msg = (
                f"\n{'='*60}\n"
                f"ERROR: Missing required configuration: {key}\n"
                f"Help: {help_text}\n"
                f"{'='*60}\n"
            )
            raise ConfigurationError(error_msg)
        return value.strip()
    
    def _validate(self):
        """Validate all settings"""
        errors = []
        
        # CRITICAL: Encryption key (44 chars for Fernet)
        try:
            self.encryption_key = self._require(
                "ENCRYPTION_KEY",
                self.encryption_key,
                "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
            if len(self.encryption_key) != 44:
                errors.append(f"ENCRYPTION_KEY must be exactly 44 characters (got {len(self.encryption_key)})")
        except ConfigurationError as e:
            errors.append(str(e))
        
        # CRITICAL: Gemini API key
        try:
            self.gemini_api_key = self._require(
                "GEMINI_API_KEY",
                self.gemini_api_key,
                "Get free key at: https://aistudio.google.com/app/apikey"
            )
            if not self.gemini_api_key.startswith("AIza"):
                logger.warning(f"GEMINI_API_KEY doesn't match expected format (should start with 'AIza')")
        except ConfigurationError as e:
            errors.append(str(e))
        
        # CRITICAL: Router password
        try:
            self.router_password = self._require(
                "ROUTER_PASSWORD",
                self.router_password,
                "Your router admin password is required to query network info"
            )
        except ConfigurationError as e:
            errors.append(str(e))
        
        # OPTIONAL: Samsung TV IP (will auto-discover if blank)
        if self.samsung_tv_ip:
            if not self._is_valid_ip(self.samsung_tv_ip):
                logger.warning(f"SAMSUNG_TV_IP '{self.samsung_tv_ip}' doesn't look like a valid IP address")
        
        # OPTIONAL: Alexa credentials
        if self.amazon_email and not self.amazon_password:
            logger.warning("AMAZON_EMAIL set but AMAZON_PASSWORD missing - Alexa TTS won't work")
        
        # Validate log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_levels:
            logger.warning(f"Invalid LOG_LEVEL '{self.log_level}', using INFO. Valid: {valid_levels}")
            self.log_level = "INFO"
        
        # If there are critical errors, exit
        if errors:
            error_summary = "\n\n" + "\n".join(errors) + "\n\nPlease check your .env file and fix the above errors.\n"
            print(error_summary, file=sys.stderr)
            sys.exit(1)
        
        logger.info(f"Configuration validated successfully (environment: {self.environment})")
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Basic IP validation"""
        parts = ip.split(".")
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(part) <= 255 for part in parts)
        except ValueError:
            return False
    
    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Export settings as dict (optionally redacting sensitive values)"""
        data = {
            "router_ip": self.router_ip,
            "router_username": self.router_username,
            "samsung_tv_ip": self.samsung_tv_ip or "(auto-discover)",
            "amazon_email": self.amazon_email or "(not set)",
            "log_level": self.log_level,
            "environment": self.environment,
        }
        
        if include_sensitive:
            data.update({
                "router_password": self.router_password,
                "amazon_password": self.amazon_password,
                "gemini_api_key": self.gemini_api_key,
                "encryption_key": self.encryption_key,
            })
        else:
            data.update({
                "router_password": "***SET***" if self.router_password else "(not set)",
                "amazon_password": "***SET***" if self.amazon_password else "(not set)",
                "gemini_api_key": "***SET***" if self.gemini_api_key else "(not set)",
                "encryption_key": "***SET***" if self.encryption_key else "(not set)",
            })
        
        return data


# Initialize settings (will validate on import)
try:
    settings = Settings()
except ConfigurationError as e:
    # Error already printed, just exit
    sys.exit(1)
except Exception as e:
    print(f"\nFATAL: Failed to load configuration: {e}\n", file=sys.stderr)
    sys.exit(1)
