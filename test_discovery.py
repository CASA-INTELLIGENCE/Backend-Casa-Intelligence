"""
Test Discovery Service
Prueba rápida de mDNS + SSDP discovery
"""
import asyncio
from discovery_service import DiscoveryService
from device_classifier import DeviceClassifier

async def test():
    print("\n🔍 Testing Discovery Service...\n")
    
    service = DiscoveryService()
    service.start_mdns()
    
    print("⏳ Waiting 5 seconds for mDNS discoveries...")
    await asyncio.sleep(5)
    
    print("\n📡 Running full discovery (mDNS + SSDP)...\n")
    devices = await service.discover()
    
    print(f"✅ Found {len(devices)} devices:\n")
    print(f"{'IP Address':<15} | {'Type':<15} | {'Protocol':<10} | {'Hostname'}")
    print("-" * 70)
    
    for device in devices:
        device_type = DeviceClassifier.classify(
            hostname=device.hostname,
            mac=None,
            services=device.services,
            metadata=device.metadata
        )
        
        hostname = device.hostname or "Unknown"
        print(f"{device.ip:<15} | {device_type:<15} | {device.protocol:<10} | {hostname}")
    
    print("\n🛑 Stopping mDNS scanner...")
    service.stop_mdns()
    print("✅ Done!\n")

if __name__ == "__main__":
    asyncio.run(test())
