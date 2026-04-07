import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Amazon Echo OUI prefixes
AMAZON_OUI = {
    "F0:27:2D", "44:65:0D", "FC:A1:83", "34:D2:70", "18:74:2E",
    "40:B4:CD", "74:75:48", "A4:08:EA", "68:37:E9", "44:11:5D",
    "CC:9E:A2", "38:F7:3D", "8C:85:80", "B4:7C:9C", "F8:1A:67",
    "10:AE:60",
}

ECHO_DEVICE_TYPES = {
    "Echo Dot": "🎙️",
    "Echo": "🔊",
    "Echo Show": "📺",
    "Echo Plus": "🔊",
    "Fire TV": "📺",
}


class AlexaDiscovery:
    """
    Discovers Amazon Echo devices on the local network using MAC address OUI matching.
    Advanced Alexa control (TTS, routines) requires Amazon credentials — set up
    via the Settings page in the dashboard.
    """

    def find_devices(self, network_devices: List[Dict]) -> List[Dict]:
        """Find Amazon Echo devices in the network device list."""
        found = []
        for d in network_devices:
            mac = d.get("mac", "").upper()
            prefix = mac[:8]
            vendor = (d.get("vendor") or "").lower()
            hostname = (d.get("hostname") or "").lower()

            is_amazon = (
                prefix in AMAZON_OUI
                or "amazon" in vendor
                or "echo" in hostname
            )
            if is_amazon:
                device_type = "Echo Dot"  # Default based on user info
                if "show" in hostname:
                    device_type = "Echo Show"
                elif "plus" in hostname:
                    device_type = "Echo Plus"

                found.append({
                    "ip": d.get("ip"),
                    "mac": mac,
                    "hostname": d.get("hostname", "Amazon Echo"),
                    "device_type": device_type,
                    "icon": ECHO_DEVICE_TYPES.get(device_type, "🎙️"),
                    "online": d.get("online", True),
                    "api_connected": False,  # Requires Amazon credentials
                    "vendor": "Amazon",
                })
        if found:
            logger.info(f"🎙️  Found {len(found)} Alexa device(s) on network")
        return found

    async def send_tts(self, text: str, device_id: Optional[str] = None) -> bool:
        """Send TTS to Echo device (requires Amazon credentials)."""
        logger.warning("TTS requires Amazon credentials — not yet configured")
        return False
