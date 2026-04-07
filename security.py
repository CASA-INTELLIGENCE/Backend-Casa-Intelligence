"""
Backend security module - Credential management with encryption
Usage:
    from backend.security import cred_manager

    # Store
    cred_manager.store_credential("router", "password", "my_password")

    # Retrieve
    password = cred_manager.get_credential("router", "password")

    # Check existence
    if cred_manager.has_credential("samsung_tv", "token"):
        ...
"""

import os
import json
import logging
from cryptography.fernet import Fernet
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CredentialManager:
    """Secure credential storage using Fernet (symmetric encryption)"""

    def __init__(self):
        master_key = os.getenv("ENCRYPTION_KEY")
        if not master_key:
            raise ValueError(
                "ENCRYPTION_KEY environment variable not set. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )

        try:
            self.cipher = Fernet(master_key.encode())
        except Exception:
            raise ValueError("Invalid ENCRYPTION_KEY format")

        self.vault_path = Path(__file__).parent / ".credentials"
        self.vault_path.mkdir(exist_ok=True, mode=0o700)

    def store_credential(self, service: str, key: str, value: str) -> None:
        """Store encrypted credential"""
        if not service or not key or not value:
            raise ValueError("service, key, and value cannot be empty")

        try:
            encrypted = self.cipher.encrypt(value.encode()).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

        vault_file = self.vault_path / f"{service}.json"

        data = {}
        try:
            if vault_file.exists():
                with open(vault_file) as f:
                    data = json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"Corrupted {vault_file}, overwriting")

        data[key] = encrypted

        try:
            with open(vault_file, "w") as f:
                json.dump(data, f, indent=2)
            vault_file.chmod(0o600)  # read/write for owner only
            logger.info(f"✅ Stored credential: {service}/{key}")
        except Exception as e:
            logger.error(f"Failed to write credential file: {e}")
            raise

    def get_credential(self, service: str, key: str) -> str:
        """Retrieve and decrypt credential"""
        vault_file = self.vault_path / f"{service}.json"

        if not vault_file.exists():
            raise KeyError(f"No credentials found for service: {service}")

        try:
            with open(vault_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to read credential file: {e}")
            raise

        if key not in data:
            raise KeyError(f"Credential '{key}' not found for service '{service}'")

        try:
            encrypted_value = data[key]
            decrypted = self.cipher.decrypt(encrypted_value.encode()).decode()
            return decrypted
        except Exception as e:
            logger.error(f"Decryption failed - credential may be corrupted: {e}")
            raise ValueError("Failed to decrypt credential")

    def has_credential(self, service: str, key: str) -> bool:
        """Check if credential exists without decrypting"""
        vault_file = self.vault_path / f"{service}.json"

        if not vault_file.exists():
            return False

        try:
            with open(vault_file) as f:
                data = json.load(f)
            return key in data
        except Exception:
            return False

    def delete_credential(self, service: str, key: str) -> bool:
        """Remove a credential"""
        vault_file = self.vault_path / f"{service}.json"

        if not vault_file.exists():
            return False

        try:
            with open(vault_file) as f:
                data = json.load(f)

            if key not in data:
                return False

            del data[key]

            with open(vault_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"🗑️ Deleted credential: {service}/{key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete credential: {e}")
            return False

    def list_services(self) -> list:
        """List all services that have stored credentials"""
        try:
            return [f.stem for f in self.vault_path.glob("*.json")]
        except Exception:
            return []


# Global instance
try:
    cred_manager = CredentialManager()
except ValueError as e:
    logger.warning(f"CredentialManager initialization failed: {e}")
    cred_manager = None
