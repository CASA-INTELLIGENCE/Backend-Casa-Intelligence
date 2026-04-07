"""
Device Handlers - Mini sistema de plugins (simple)
Cada tipo de dispositivo tiene su handler.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class DeviceHandler(ABC):
    """Base handler para dispositivos"""
    
    device_type: str = "unknown"
    
    @abstractmethod
    async def get_status(self, ip: str) -> Dict[str, Any]:
        """Obtener estado del dispositivo"""
        pass
    
    @abstractmethod
    async def send_command(self, ip: str, command: str, params: Dict = None) -> bool:
        """Enviar comando al dispositivo"""
        pass


class TVHandler(DeviceHandler):
    """Handler para TVs (Samsung, etc.)"""
    
    device_type = "tv"
    
    def __init__(self, samsung_tv_instance=None):
        """
        Usar instancia existente de SamsungTV si está disponible
        """
        self.samsung_tv = samsung_tv_instance
    
    async def get_status(self, ip: str) -> Dict[str, Any]:
        """Obtener estado del TV"""
        try:
            # Si ya tienes integración Samsung, úsala
            if self.samsung_tv and self.samsung_tv._ip == ip:
                return self.samsung_tv.get_status()
            
            # Fallback genérico
            return {
                "connected": True,
                "status": "detected",
                "type": "tv",
            }
        except Exception as e:
            logger.error(f"TV status error ({ip}): {e}")
            return {"connected": False, "status": "error"}
    
    async def send_command(self, ip: str, command: str, params: Dict = None) -> bool:
        """Enviar comando al TV"""
        try:
            if self.samsung_tv and self.samsung_tv._ip == ip:
                # Usar integración existente
                if command == "power_on":
                    self.samsung_tv.power_on()
                elif command == "power_off":
                    self.samsung_tv.power_off()
                return True
            
            return False
        except Exception as e:
            logger.error(f"TV command error ({ip}): {e}")
            return False


class SpeakerHandler(DeviceHandler):
    """Handler para smart speakers (Alexa, Google Home)"""
    
    device_type = "speaker"
    
    async def get_status(self, ip: str) -> Dict[str, Any]:
        """Obtener estado del speaker"""
        return {
            "connected": True,
            "status": "online",
            "type": "speaker",
        }
    
    async def send_command(self, ip: str, command: str, params: Dict = None) -> bool:
        """Enviar comando (TTS, etc.)"""
        logger.info(f"Speaker command not implemented: {command} to {ip}")
        return False


class SmartDeviceHandler(DeviceHandler):
    """Handler para smart devices (bulbs, plugs, etc.)"""
    
    device_type = "smart_device"
    
    async def get_status(self, ip: str) -> Dict[str, Any]:
        """Obtener estado del dispositivo"""
        return {
            "connected": True,
            "status": "online",
            "type": "smart_device",
        }
    
    async def send_command(self, ip: str, command: str, params: Dict = None) -> bool:
        """Enviar comando (on/off, brightness, etc.)"""
        logger.info(f"Smart device command not implemented: {command} to {ip}")
        return False


class DeviceHandlerRegistry:
    """
    Registro de handlers - mapea tipo → handler
    """
    
    def __init__(self):
        self.handlers: Dict[str, DeviceHandler] = {}
    
    def register(self, handler: DeviceHandler):
        """Registrar handler"""
        self.handlers[handler.device_type] = handler
        logger.info(f"✅ Handler registered: {handler.device_type}")
    
    def get_handler(self, device_type: str) -> Optional[DeviceHandler]:
        """Obtener handler por tipo"""
        return self.handlers.get(device_type)
    
    async def get_status(self, device_type: str, ip: str) -> Dict[str, Any]:
        """Obtener estado usando handler apropiado"""
        handler = self.get_handler(device_type)
        if handler:
            return await handler.get_status(ip)
        
        return {"connected": False, "status": "no_handler"}
    
    async def send_command(self, device_type: str, ip: str, 
                          command: str, params: Dict = None) -> bool:
        """Enviar comando usando handler apropiado"""
        handler = self.get_handler(device_type)
        if handler:
            return await handler.send_command(ip, command, params)
        
        return False
