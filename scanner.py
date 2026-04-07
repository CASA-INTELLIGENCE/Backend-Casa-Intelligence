import subprocess
import socket
import re
import logging
import requests
import threading
import ipaddress
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Common MAC OUI → Vendor mapping (offline, instant)
MAC_VENDORS = {
    "B8:27:EB": "Raspberry Pi", "DC:A6:32": "Raspberry Pi", "E4:5F:01": "Raspberry Pi",
    "F0:27:2D": "Amazon (Echo)", "44:65:0D": "Amazon (Echo)", "FC:A1:83": "Amazon (Echo)",
    "34:D2:70": "Amazon (Echo)", "18:74:2E": "Amazon (Echo)", "40:B4:CD": "Amazon (Echo)",
    "74:75:48": "Amazon (Echo)", "A4:08:EA": "Amazon (Echo)", "68:37:E9": "Amazon (Echo)",
    "44:11:5D": "Amazon (Echo)", "CC:9E:A2": "Amazon (Echo)", "38:F7:3D": "Amazon (Echo)",
    "8C:85:80": "Amazon (Echo)", "B4:7C:9C": "Amazon (Echo)", "F8:1A:67": "Amazon (Echo)",
    "10:AE:60": "Amazon (Echo)", "A4:08:F5": "Samsung", "00:12:47": "Samsung",
    "00:16:6C": "Samsung", "2C:4D:54": "Samsung", "5C:F6:DC": "Samsung",
    "B8:BC:1B": "Samsung", "CC:07:AB": "Samsung", "D0:22:BE": "Samsung",
    "DC:71:96": "Samsung", "78:BD:BC": "Samsung TV", "F4:7B:5E": "Samsung TV",
    "FC:F1:36": "Samsung TV", "3C:22:FB": "Apple", "F8:FF:C2": "Apple",
    "AC:DE:48": "Apple", "00:50:56": "VMware", "08:00:27": "VirtualBox",
    "EC:08:6B": "TP-Link", "50:C7:BF": "TP-Link", "98:DA:C4": "TP-Link",
    "D8:07:B6": "TP-Link", "C0:25:E9": "TP-Link",
    "74:4D:28": "Realme", "6C:5A:B0": "Xiaomi", "00:9E:C8": "Xiaomi",
    "28:6D:97": "Intel (PC)", "8C:8D:28": "Intel (PC)",
    "B8:AC:6F": "Qualcomm (Android)",
}

DEVICE_ICONS = {
    "Amazon (Echo)": "🎙️", "Samsung TV": "📺", "Samsung": "📱",
    "Apple": "🍎", "TP-Link": "🔌", "Raspberry Pi": "🖥️",
    "Intel (PC)": "💻", "Realme": "📱", "Xiaomi": "📱",
    "Qualcomm (Android)": "📱",
}


def get_vendor(mac: str) -> str:
    prefix = mac.upper()[:8]
    if prefix in MAC_VENDORS:
        return MAC_VENDORS[prefix]
    prefix6 = mac.upper()[:6].replace(":", "")
    for key, val in MAC_VENDORS.items():
        if key.replace(":", "") == prefix6:
            return val
    try:
        r = requests.get(f"https://api.macvendors.com/{mac}", timeout=3)
        if r.status_code == 200:
            return r.text.strip()
    except Exception:
        pass
    return "Unknown"


def get_hostname(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ip


def _detect_subnet() -> Optional[str]:
    """Detect the local subnet from the ARP table (e.g. 192.168.0.0/24)."""
    try:
        result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=5)
        pattern = re.compile(r"(\d+\.\d+\.\d+)\.\d+")
        subnets = set()
        for line in result.stdout.splitlines():
            m = pattern.search(line)
            if m:
                prefix = m.group(1)
                # Only consider private address ranges
                if prefix.startswith(("192.168.", "10.", "172.")):
                    subnets.add(f"{prefix}.0/24")
        # Prefer 192.168.0.x or 192.168.1.x
        for s in sorted(subnets):
            if "192.168." in s:
                return s
        return next(iter(subnets), None)
    except Exception:
        return None


def ping_sweep(subnet: str):
    """
    Ping all hosts in a /24 subnet in parallel (200ms timeout per host).
    This populates the ARP table so subsequent arp -a finds all live devices,
    including smart home devices like Amazon Echo that don't initiate traffic.
    """
    try:
        network = ipaddress.IPv4Network(subnet, strict=False)
        hosts = list(network.hosts())
        logger.info(f"🔍 Ping sweep on {subnet} ({len(hosts)} hosts)...")

        def ping(ip: str):
            subprocess.run(
                ["ping", "-n", "1", "-w", "200", ip],
                capture_output=True, timeout=1
            )

        threads = [threading.Thread(target=ping, args=(str(h),), daemon=True) for h in hosts]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2)

        logger.info(f"✅ Ping sweep complete for {subnet}")
    except Exception as e:
        logger.error(f"Ping sweep error: {e}")


def arp_scan() -> List[Dict]:
    """Get devices from ARP table (Windows arp -a)."""
    devices = []
    try:
        result = subprocess.run(
            ["arp", "-a"], capture_output=True, text=True, timeout=10
        )
        pattern = re.compile(
            r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f]{2}[:-][0-9a-f]{2}[:-][0-9a-f]{2}[:-][0-9a-f]{2}[:-][0-9a-f]{2}[:-][0-9a-f]{2})",
            re.IGNORECASE,
        )
        seen_macs = set()
        for line in result.stdout.splitlines():
            match = pattern.search(line)
            if match:
                ip = match.group(1)
                mac = match.group(2).upper().replace("-", ":")
                if mac in seen_macs or mac == "FF:FF:FF:FF:FF:FF":
                    continue
                seen_macs.add(mac)
                first_octet = int(ip.split(".")[0]) if ip else 0
                if first_octet >= 224 or ip.endswith(".255") or ip.endswith(".0"):
                    continue
                vendor = get_vendor(mac)
                hostname = get_hostname(ip)
                devices.append({
                    "ip": ip,
                    "mac": mac,
                    "hostname": hostname if hostname != ip else None,
                    "vendor": vendor,
                    "icon": DEVICE_ICONS.get(vendor, "📡"),
                    "online": True,
                })
    except Exception as e:
        logger.error(f"ARP scan error: {e}")
    return devices


class NetworkScanner:
    def __init__(self):
        self._cache: List[Dict] = []
        self._sweep_done = False

    def scan(self) -> List[Dict]:
        # First scan: do an active ping sweep to discover all live devices
        # (including Echo Dot which doesn't communicate with this PC by default)
        if not self._sweep_done:
            subnet = _detect_subnet()
            if subnet:
                ping_sweep(subnet)
            self._sweep_done = True

        results = arp_scan()
        self._cache = results
        logger.info(f"Network scan: found {len(results)} devices")
        return results

    def force_sweep(self):
        """Force a new ping sweep on next scan (call when device count seems low)."""
        self._sweep_done = False

    @property
    def cached(self) -> List[Dict]:
        return self._cache
