import hashlib
import requests
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class TPLinkRouter:
    """
    TP-Link Archer C50 v6 JSON-RPC API client.
    Connects to the router admin panel at http://{host}/ and authenticates
    using the stok-based session token system.
    """

    def __init__(self, host: str, password: str, username: str = "admin"):
        self.base_url = f"http://{host}"
        self.password = password
        self.username = username
        self.session = requests.Session()
        self.session.headers.update({
            "Referer": self.base_url + "/",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        })
        self.stok: Optional[str] = None
        self._connected = False
        self._info: Dict = {}

    def _md5(self, text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest().upper()

    def login(self) -> bool:
        """Try to authenticate with the router."""
        # Try plain password first, then MD5 hash
        for pwd in [self.password, self._md5(self.password), self._md5(self.password).lower()]:
            try:
                payload = {
                    "method": "do",
                    "login": {"username": self.username, "password": pwd},
                }
                resp = self.session.post(self.base_url + "/", json=payload, timeout=5)
                data = resp.json()
                if data.get("error_code") == 0 and "stok" in data:
                    self.stok = data["stok"]
                    self._connected = True
                    logger.info(f"✅ TP-Link router connected (stok={self.stok[:8]}...)")
                    return True
            except Exception as e:
                logger.debug(f"Login attempt failed: {e}")
        logger.warning("⚠️  TP-Link login failed — falling back to ARP scan only")
        return False

    def _post(self, payload: Dict) -> Dict:
        if not self.stok:
            return {}
        try:
            url = f"{self.base_url}/stok={self.stok}/ds"
            resp = self.session.post(url, json=payload, timeout=5)
            return resp.json()
        except Exception as e:
            logger.error(f"Router request failed: {e}")
            self.stok = None  # Force re-login next time
            return {}

    def get_clients(self) -> List[Dict]:
        """Return list of connected clients from router DHCP table."""
        if not self.stok and not self.login():
            return []

        data = self._post({"hosts_info": {"table": "host"}, "method": "get"})
        raw = data.get("hosts_info", {}).get("host", [])
        clients = []
        for h in raw:
            if not isinstance(h, dict):
                continue
            clients.append({
                "ip": h.get("ip", ""),
                "mac": h.get("mac", "").upper().replace("-", ":"),
                "hostname": h.get("hostname", ""),
                "connection_type": h.get("type", "unknown"),  # wireless/wired
                "up_speed": h.get("up_speed", 0),
                "down_speed": h.get("down_speed", 0),
            })
        logger.info(f"Router: {len(clients)} clients found")
        return clients

    def get_info(self) -> Dict:
        """Return basic router information."""
        if not self.stok and not self.login():
            return {"connected": False}

        data = self._post({
            "device_info": {"name": ["hw_version", "sw_version", "wan_ip"]},
            "method": "get",
        })
        info = data.get("device_info", {})
        return {
            "connected": True,
            "model": "TP-Link Archer C50",
            "hw_version": info.get("hw_version", "6.0"),
            "sw_version": info.get("sw_version", ""),
            "wan_ip": info.get("wan_ip", ""),
            "ip": self.base_url.replace("http://", ""),
        }

    def logout(self):
        try:
            self._post({"method": "do", "logout": {}})
        except Exception:
            pass
        self.stok = None
        self._connected = False
