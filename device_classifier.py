"""
Device Classifier - Clasificación simple de dispositivos
NO usa ML, solo reglas básicas.
"""
import re
from typing import Optional
from manuf import manuf

# Inicializar lookup de vendors
mac_parser = manuf.MacParser(update=False)


class DeviceClassifier:
    """
    Clasificador simple basado en reglas.
    """
    
    # Patrones de hostname
    TV_PATTERNS = [
        r".*tv.*", r".*samsung.*", r".*lg.*", r".*sony.*",
        r".*roku.*", r".*chromecast.*", r".*firetv.*"
    ]
    
    SPEAKER_PATTERNS = [
        r".*echo.*", r".*alexa.*", r".*dot.*", r".*google.*home.*",
        r".*homepod.*", r".*sonos.*"
    ]
    
    SMART_DEVICE_PATTERNS = [
        r".*bulb.*", r".*light.*", r".*plug.*", r".*switch.*",
        r".*kasa.*", r".*hue.*", r".*tuya.*"
    ]
    
    # Vendors típicos (MAC prefixes)
    TV_VENDORS = ["samsung", "lg", "sony", "vizio", "tcl"]
    SPEAKER_VENDORS = ["amazon", "google", "apple", "sonos"]
    SMART_VENDORS = ["tp-link", "philips", "tuya", "lifx"]
    
    @staticmethod
    def classify(hostname: Optional[str], mac: Optional[str], 
                 services: list = None, metadata: dict = None) -> str:
        """
        Clasificar dispositivo.
        
        Returns:
            "tv", "speaker", "smart_device", o "unknown"
        """
        score = {
            "tv": 0,
            "speaker": 0,
            "smart_device": 0,
        }
        
        hostname_lower = (hostname or "").lower()
        
        # 1. Clasificar por hostname
        if hostname_lower:
            for pattern in DeviceClassifier.TV_PATTERNS:
                if re.match(pattern, hostname_lower):
                    score["tv"] += 50
            
            for pattern in DeviceClassifier.SPEAKER_PATTERNS:
                if re.match(pattern, hostname_lower):
                    score["speaker"] += 50
            
            for pattern in DeviceClassifier.SMART_DEVICE_PATTERNS:
                if re.match(pattern, hostname_lower):
                    score["smart_device"] += 50
        
        # 2. Clasificar por vendor (MAC)
        if mac:
            try:
                vendor = mac_parser.get_manuf(mac)
                if vendor:
                    vendor_lower = vendor.lower()
                    
                    if any(v in vendor_lower for v in DeviceClassifier.TV_VENDORS):
                        score["tv"] += 40
                    
                    if any(v in vendor_lower for v in DeviceClassifier.SPEAKER_VENDORS):
                        score["speaker"] += 40
                    
                    if any(v in vendor_lower for v in DeviceClassifier.SMART_VENDORS):
                        score["smart_device"] += 40
            except Exception:
                pass
        
        # 3. Clasificar por servicios (SSDP/mDNS)
        if services:
            services_str = " ".join(services).lower()
            
            if "dial" in services_str or "samsung" in services_str:
                score["tv"] += 60
            
            if "googlecast" in services_str or "airplay" in services_str:
                score["speaker"] += 30
                score["tv"] += 30  # Chromecast también puede ser TV
        
        # 4. Clasificar por metadata
        if metadata:
            server = metadata.get("server", "").lower()
            
            if "samsung" in server or "tizen" in server:
                score["tv"] += 70
            
            if "echo" in server or "alexa" in server:
                score["speaker"] += 70
        
        # Devolver tipo con mayor score
        if max(score.values()) > 0:
            return max(score, key=score.get)
        
        return "unknown"
