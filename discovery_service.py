"""
Discovery Service - Detección automática de dispositivos
Usa mDNS y SSDP para encontrar dispositivos sin hardcodear IPs.
"""
import asyncio
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
from ssdpy import SSDPClient
import socket
import time

logger = logging.getLogger(__name__)

@dataclass
class DiscoveredDevice:
    """Dispositivo descubierto"""
    ip: str
    hostname: Optional[str] = None
    device_type: Optional[str] = None  # "tv", "speaker", "smart_device", "unknown"
    vendor: Optional[str] = None
    protocol: str = "unknown"  # "mdns", "ssdp", "arp"
    services: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    discovered_at: float = field(default_factory=time.time)


class MDNSScanner(ServiceListener):
    """
    Scanner mDNS - Detecta dispositivos que anuncian servicios (Chromecast, Alexa, etc.)
    """
    
    def __init__(self):
        self.devices = {}
        self.zeroconf = None
        self.browser = None
    
    def start(self):
        """Iniciar escaneo mDNS"""
        try:
            self.zeroconf = Zeroconf()
            
            # Servicios comunes de smart home
            services = [
                "_googlecast._tcp.local.",     # Chromecast, Google Home
                "_airplay._tcp.local.",        # Apple TV, AirPlay devices
                "_spotify-connect._tcp.local.", # Spotify Connect
                "_http._tcp.local.",           # Generic HTTP devices
                "_homekit._tcp.local.",        # HomeKit devices
            ]
            
            for service in services:
                self.browser = ServiceBrowser(self.zeroconf, service, self)
            
            logger.info("✅ mDNS scanner started")
            
        except Exception as e:
            logger.error(f"mDNS scanner error: {e}")
    
    def stop(self):
        """Detener escaneo"""
        if self.zeroconf:
            self.zeroconf.close()
    
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Callback cuando se descubre un servicio"""
        try:
            info = zc.get_service_info(type_, name)
            if info:
                ip = socket.inet_ntoa(info.addresses[0])
                hostname = info.server.rstrip('.')
                
                device = DiscoveredDevice(
                    ip=ip,
                    hostname=hostname,
                    protocol="mdns",
                    services=[type_],
                    metadata={
                        "name": name,
                        "port": info.port,
                        "properties": dict(info.properties),
                    }
                )
                
                self.devices[ip] = device
                logger.info(f"📡 mDNS found: {hostname} ({ip}) - {type_}")
                
        except Exception as e:
            logger.error(f"mDNS service add error: {e}")
    
    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Callback cuando se pierde un servicio"""
        pass
    
    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Callback cuando se actualiza un servicio"""
        pass
    
    def get_devices(self) -> List[DiscoveredDevice]:
        """Obtener dispositivos descubiertos"""
        return list(self.devices.values())


class SSDPScanner:
    """
    Scanner SSDP/UPnP - Detecta TVs, media servers, etc.
    """
    
    async def scan(self, timeout: int = 3) -> List[DiscoveredDevice]:
        """Escanear red con SSDP"""
        devices = []
        
        try:
            client = SSDPClient()
            try:
                responses = client.m_search("ssdp:all", timeout=timeout)
            except TypeError:
                try:
                    responses = client.m_search("ssdp:all", timeout)
                except TypeError:
                    responses = client.m_search("ssdp:all")
            
            responses = responses or []
            
            seen_ips = set()
            
            for response in responses:
                try:
                    location = response.get("location", "")
                    if not location or "//" not in location:
                        continue
                    
                    ip = location.split("//")[1].split(":")[0]
                    
                    if not ip or ip in seen_ips:
                        continue
                    
                    seen_ips.add(ip)
                    
                    device = DiscoveredDevice(
                        ip=ip,
                        protocol="ssdp",
                        services=[response.get("st", "")],
                        metadata={
                            "server": response.get("server", ""),
                            "location": response.get("location", ""),
                            "usn": response.get("usn", ""),
                        }
                    )
                    
                    devices.append(device)
                    logger.info(f"📺 SSDP found: {ip} - {response.get('server', 'Unknown')}")
                    
                except Exception as e:
                    logger.error(f"SSDP parse error: {e}")
            
        except Exception as e:
            logger.error(f"SSDP scan error: {e}")
        
        return devices


class DiscoveryService:
    """
    Servicio de descubrimiento - Coordina mDNS y SSDP
    """
    
    def __init__(self):
        self.mdns_scanner = MDNSScanner()
        self.ssdp_scanner = SSDPScanner()
        self.running = False
    
    def start_mdns(self):
        """Iniciar escaneo continuo mDNS"""
        self.mdns_scanner.start()
        self.running = True
    
    def stop_mdns(self):
        """Detener mDNS"""
        self.mdns_scanner.stop()
        self.running = False
    
    async def discover(self) -> List[DiscoveredDevice]:
        """
        Descubrir dispositivos con ambos protocolos.
        
        Returns:
            Lista de dispositivos únicos (por IP)
        """
        all_devices = {}
        
        # 1. mDNS (instantáneo, de caché)
        mdns_devices = self.mdns_scanner.get_devices()
        for device in mdns_devices:
            all_devices[device.ip] = device
        
        # 2. SSDP (requiere escaneo activo)
        ssdp_devices = await self.ssdp_scanner.scan(timeout=2)
        for device in ssdp_devices:
            if device.ip in all_devices:
                # Merge con mDNS
                all_devices[device.ip].services.extend(device.services)
                all_devices[device.ip].metadata.update(device.metadata)
            else:
                all_devices[device.ip] = device
        
        logger.info(f"🔍 Discovery complete: {len(all_devices)} unique devices")
        return list(all_devices.values())
