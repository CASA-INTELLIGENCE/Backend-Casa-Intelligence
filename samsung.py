"""
Enhanced Samsung TV integration with structured error handling
Uses security module for token storage
"""

import socket
import logging
import json
import os
from typing import Optional, Dict
from requests.exceptions import Timeout, ConnectionError
import requests as req

from exceptions import IntegrationError, ErrorCategory, ErrorSeverity
from security import cred_manager

logger = logging.getLogger(__name__)

# Samsung OUI prefixes (first 3 bytes of MAC)
SAMSUNG_OUI = {
    "00:12:47", "00:16:6C", "00:1D:A9", "00:21:19", "00:23:39",
    "0C:14:20", "2C:4D:54", "5C:F6:DC", "78:BD:BC", "8C:77:12",
    "A4:08:F5", "B8:BC:1B", "CC:07:AB", "D0:22:BE", "DC:71:96",
    "F0:5A:09", "F4:7B:5E", "FC:F1:36", "24:FB:65", "48:44:F7",
    "70:F9:27", "84:A4:66", "94:35:0A", "C8:14:79",
}


def discover_via_ssdp(timeout: float = 3.0) -> Optional[str]:
    """Discover Samsung TV on local network via SSDP multicast."""
    SSDP_QUERIES = [
        'M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\nMX: 2\r\nST: urn:samsung.com:device:RemoteControlReceiver:1\r\n\r\n',
        'M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\nMX: 2\r\nST: upnp:rootdevice\r\n\r\n',
    ]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
    sock.settimeout(timeout)
    try:
        for query in SSDP_QUERIES:
            sock.sendto(query.encode(), ("239.255.255.250", 1900))
        while True:
            try:
                data, addr = sock.recvfrom(2048)
                response = data.decode("utf-8", errors="ignore")
                if any(kw in response for kw in ["Samsung", "DLNA", "Tizen", "SmartTV"]):
                    logger.info(f"📺 Samsung TV found via SSDP at {addr[0]}")
                    return addr[0]
            except socket.timeout:
                break
    except Exception as e:
        logger.debug(f"SSDP discovery error: {e}")
    finally:
        sock.close()
    return None


def find_tv_in_devices(devices: list) -> Optional[str]:
    """Find Samsung TV IP from network device list by MAC OUI."""
    for d in devices:
        mac = d.get("mac", "").upper()
        prefix = mac[:8]
        hostname = (d.get("hostname") or "").lower()
        vendor = (d.get("vendor") or "").lower()
        if prefix in SAMSUNG_OUI:
            return d.get("ip")
        if any(kw in hostname for kw in ["samsung", "smart-tv", "tizen"]):
            return d.get("ip")
        if "samsung tv" in vendor:
            return d.get("ip")
    return None


class SamsungTV:
    def __init__(self, cred_manager_instance=None):
        self._ip: Optional[str] = None
        self._tv = None
        self.cred_mgr = cred_manager_instance or cred_manager
        self._token = self._load_token()

    def _load_token(self) -> Optional[str]:
        """Load token from secure vault (not plain text file)"""
        try:
            if self.cred_mgr and self.cred_mgr.has_credential("samsung_tv", "token"):
                token = self.cred_mgr.get_credential("samsung_tv", "token")
                logger.debug("📺 Samsung TV token loaded from vault")
                return token
        except Exception as e:
            logger.warning(f"Failed to load token from vault: {e}")
        return None

    def _save_token(self, token: str):
        """Save token encrypted in vault (not plain file)"""
        try:
            if self.cred_mgr:
                self.cred_mgr.store_credential("samsung_tv", "token", token)
                logger.info("📺 Samsung TV token stored in vault")
            self._token = token
        except Exception as e:
            logger.error(f"Failed to save token to vault: {e}")

    def set_ip(self, ip: str):
        """Update TV IP and reset connection"""
        if ip != self._ip:
            self._ip = ip
            self._tv = None  # Reset connection

    def _get_client(self):
        """Create a Samsung TV WebSocket client"""
        if not self._ip:
            return None

        try:
            from samsungtvws import SamsungTVWS
            try:
                from samsungtvws.encrypted.remote import SamsungTVEncryptedSession
                tv = SamsungTVEncryptedSession(
                    host=self._ip,
                    port=8002,
                    token=self._token,
                    timeout=5,
                    name="CasaIntelligence",
                )
                if self._token is None:
                    logger.info("📺 Samsung TV: Approve 'Remote Access' on your TV screen...")
                return tv
            except Exception as enc_err:
                logger.debug(f"Encrypted WS unavailable: {enc_err}")
                tv = SamsungTVWS(host=self._ip, port=8002, timeout=5, name="CasaIntelligence")
                return tv
        except ImportError as e:
            logger.warning(f"samsungtvws not installed: {e}")
            return None
        except Exception as e:
            logger.error(f"Samsung TV client error: {e}")
            return None

    def get_status(self) -> Dict:
        """Get TV status with structured error handling"""
        if not self._ip:
            return {
                "connected": False,
                "ip": None,
                "status": "not_found",
                "error": {
                    "category": ErrorCategory.DEVICE_OFFLINE.value,
                    "message": "Samsung TV IP not discovered yet",
                    "severity": ErrorSeverity.RECOVERABLE.value,
                }
            }

        try:
            r = req.get(f"http://{self._ip}:8001/api/v2/", timeout=3)

            if r.status_code == 200:
                info = r.json()
                device = info.get("device", {})
                return {
                    "connected": True,
                    "ip": self._ip,
                    "status": "on",
                    "name": device.get("name", "Samsung TV"),
                    "model": device.get("modelName", "Unknown Model"),
                    "resolution": device.get("resolution", ""),
                }

            elif r.status_code == 403:
                error = IntegrationError(
                    service="samsung_tv",
                    category=ErrorCategory.AUTHENTICATION,
                    severity=ErrorSeverity.DEGRADED,
                    message="TV requires new pairing",
                    recovery_hint="Approve 'Remote Access' on TV screen and restart",
                    retry_possible=True,
                )
                logger.warning(f"📺 {error.message}")
                return {
                    "connected": False,
                    "ip": self._ip,
                    "status": "requires_pairing",
                    "error": error.to_dict(),
                }
            else:
                return {
                    "connected": False,
                    "ip": self._ip,
                    "status": "error",
                    "error": {
                        "category": ErrorCategory.API_ERROR.value,
                        "message": f"HTTP {r.status_code}",
                        "severity": ErrorSeverity.DEGRADED.value,
                    }
                }

        except Timeout:
            error = IntegrationError(
                service="samsung_tv",
                category=ErrorCategory.NETWORK_TIMEOUT,
                severity=ErrorSeverity.RECOVERABLE,
                message="TV timeout - likely offline",
                recovery_hint="Check if TV power is on and connected to network",
                retry_possible=True,
            )
            logger.warning(f"📺 {error.message}")
            return {
                "connected": False,
                "ip": self._ip,
                "status": "offline",
                "error": error.to_dict(),
            }

        except ConnectionError as e:
            error = IntegrationError(
                service="samsung_tv",
                category=ErrorCategory.NETWORK_TIMEOUT,
                severity=ErrorSeverity.RECOVERABLE,
                message="Cannot reach TV",
                raw_error=str(e),
                recovery_hint="Check network connectivity, verify TV IP is correct",
                retry_possible=True,
            )
            logger.warning(f"📺 {error.message}")
            return {
                "connected": False,
                "ip": self._ip,
                "status": "offline",
                "error": error.to_dict(),
            }

        except Exception as e:
            error = IntegrationError(
                service="samsung_tv",
                category=ErrorCategory.UNKNOWN,
                severity=ErrorSeverity.DEGRADED,
                message=f"Unexpected error: {str(e)}",
                raw_error=str(e),
                retry_possible=True,
            )
            logger.error(f"📺 {error.message}")
            return {
                "connected": False,
                "ip": self._ip,
                "status": "error",
                "error": error.to_dict(),
            }

    async def send_command(self, command: str, value=None) -> Dict:
        """Send command with structured result"""
        tv = self._get_client()
        if not tv:
            return {
                "success": False,
                "command": command,
                "error": {
                    "category": ErrorCategory.DEVICE_OFFLINE.value,
                    "message": "TV client not initialized",
                    "severity": ErrorSeverity.CRITICAL.value,
                }
            }

        try:
            KEY_MAP = {
                "power": "KEY_POWER",
                "volume_up": "KEY_VOLUP",
                "volume_down": "KEY_VOLDOWN",
                "mute": "KEY_MUTE",
                "home": "KEY_HOME",
                "back": "KEY_RETURN",
                "up": "KEY_UP",
                "down": "KEY_DOWN",
                "left": "KEY_LEFT",
                "right": "KEY_RIGHT",
                "enter": "KEY_ENTER",
                "source": "KEY_SOURCE",
            }
            key = KEY_MAP.get(command, command.upper())
            tv.send_key(key)

            logger.info(f"📺 Command sent: {command}")
            return {
                "success": True,
                "command": command,
            }

        except Exception as e:
            error = IntegrationError(
                service="samsung_tv",
                category=ErrorCategory.API_ERROR,
                severity=ErrorSeverity.RECOVERABLE,
                message=f"Failed to send command: {command}",
                raw_error=str(e),
                retry_possible=True,
            )
            logger.error(f"📺 {error.message}: {e}")
            return {
                "success": False,
                "command": command,
                "error": error.to_dict(),
            }
