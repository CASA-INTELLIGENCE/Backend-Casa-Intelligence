from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import List, Dict, Optional, Any
import asyncio
import logging
import json
from datetime import datetime

# Import configuration FIRST (validates on import)
from config import settings

# Setup logging SECOND (before other imports)
from logging_config import setup_logging

# Initialize structured logging with sanitization
logger_instance = setup_logging(
    log_file="logs/casa_intelligence.log",
    console_level=logging.INFO,
    file_level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Log startup
logger.info("="*60)
logger.info("Casa Intelligence Backend Starting")
logger.info(f"Environment: {settings.environment}")
logger.info("="*60)

# Now import integrations
from scanner import NetworkScanner
from tplink import TPLinkRouter
from samsung import SamsungTV, discover_via_ssdp, find_tv_in_devices
from alexa import AlexaDiscovery
from ai_provider import get_ai_provider  # NEW - Groq/Gemini provider
from automations import AutomationEngine
from websocket_manager import ConnectionManager

# ── Module Instances ────────────────────────────────────────────────────────
scanner = NetworkScanner()
router = TPLinkRouter(settings.router_ip, settings.router_password, settings.router_username)
tv = SamsungTV()
alexa = AlexaDiscovery()
ai_provider = get_ai_provider()  # NEW - Auto-selects Groq or Gemini
automations = AutomationEngine()
manager = ConnectionManager(heartbeat_interval=30)

# ── Shared State ────────────────────────────────────────────────────────────
MAX_HISTORY = 40  # Keep last 40 data points (~10 minutes at 15s intervals)

state: Dict[str, Any] = {
    "devices": [],
    "router": {},
    "tv": {"connected": False, "status": "unknown"},
    "alexa": [],
    "alerts": [],
    "online_count": 0,
    "scan_count": 0,
    "history": [],
}


# ── Background Scan Loop ────────────────────────────────────────────────────
async def scan_loop():
    """Scans the network every 15 seconds and broadcasts results."""
    # Wait a moment for app startup
    await asyncio.sleep(2)

    # Try SSDP discovery for Samsung TV once at startup
    logger.info("🔍 Searching for Samsung TV via SSDP...")
    tv_ip = await asyncio.to_thread(discover_via_ssdp)
    if tv_ip:
        tv.set_ip(tv_ip)
    elif settings.samsung_tv_ip:
        tv.set_ip(settings.samsung_tv_ip)

    while True:
        state["scan_count"] += 1
        logger.info(f"📡 Scan #{state['scan_count']} starting...")

        # 1. ARP network scan
        try:
            arp_devices = await asyncio.to_thread(scanner.scan)
        except Exception as e:
            logger.error(f"ARP scan error: {e}")
            arp_devices = []

        # 2. Enrich with router data
        try:
            router_clients = await asyncio.to_thread(router.get_clients)
            router_info = await asyncio.to_thread(router.get_info)
        except Exception as e:
            logger.error(f"Router error: {e}")
            router_clients, router_info = [], {}

        # 3. Merge and update device state
        merged = _merge_devices(arp_devices, router_clients)
        state["devices"] = merged
        state["router"] = router_info
        state["online_count"] = len([d for d in merged if d.get("online")])

        # 4. Find Samsung TV by MAC OUI if not yet found
        if not tv._ip:
            try:
                tv_ip = _safe_find_tv(merged)
                if tv_ip:
                    tv.set_ip(tv_ip)
                    logger.info(f"📺 Samsung TV found at {tv_ip}")
            except Exception as e:
                logger.error(f"TV discovery error: {e}")

        # 5. Get TV status
        try:
            if tv._ip:
                state["tv"] = await asyncio.to_thread(tv.get_status)
            else:
                state["tv"] = {"connected": False, "status": "not_found"}
        except Exception as e:
            logger.error(f"TV status error: {e}")
            state["tv"] = {"connected": False, "status": "error"}

        # 6. Find Alexa devices
        try:
            state["alexa"] = alexa.find_devices(merged)
        except Exception as e:
            logger.error(f"Alexa discovery error: {e}")

        # 7. Run automations
        try:
            await automations.check(merged, state["tv"], state["alexa"])
            state["alerts"] = automations.get_alerts()
        except Exception as e:
            logger.error(f"Automations error: {e}")

        # 8. Record history data point
        state["history"].append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "online": state["online_count"],
            "total": len(merged),
            "tv": 1 if state["tv"].get("status") == "on" else 0,
            "alexa": len(state.get("alexa", [])),
            "scan": state["scan_count"],
        })
        if len(state["history"]) > MAX_HISTORY:
            state["history"] = state["history"][-MAX_HISTORY:]

        # 9. Always broadcast even if some steps failed
        await manager.broadcast({"type": "update", **state})
        logger.info(f"✅ Scan #{state['scan_count']} complete: {state['online_count']} online")

        await asyncio.sleep(15)


def _safe_find_tv(devices: List[Dict]) -> Optional[str]:
    """Safely find Samsung TV IP with robust None handling."""
    SAMSUNG_OUI = {
        "00:12:47", "00:16:6C", "00:1D:A9", "00:21:19", "00:23:39",
        "0C:14:20", "2C:4D:54", "5C:F6:DC", "78:BD:BC", "8C:77:12",
        "A4:08:F5", "B8:BC:1B", "B8:BC:5B", "CC:07:AB", "D0:22:BE", "DC:71:96",
        "F4:7B:5E", "FC:F1:36", "24:FB:65", "70:F9:27", "84:A4:66",
    }
    for d in devices:
        if not isinstance(d, dict):
            continue
        mac = str(d.get("mac") or "").upper()
        prefix = mac[:8]
        hostname = str(d.get("hostname") or "").lower()
        vendor = str(d.get("vendor") or "").lower()
        if prefix in SAMSUNG_OUI or "samsung" in hostname or "samsung tv" in vendor:
            return d.get("ip")
    return None


def _merge_devices(arp: List[Dict], router_clients: List[Dict]) -> List[Dict]:
    merged: Dict[str, Dict] = {}
    for d in arp:
        mac = d.get("mac", "").upper()
        if mac:
            merged[mac] = {**d, "source": "arp"}

    for c in router_clients:
        mac = c.get("mac", "").upper()
        if not mac:
            continue
        if mac in merged:
            # Enrich ARP data with router data
            merged[mac].update({
                k: v for k, v in c.items()
                if v and k in ("hostname", "up_speed", "down_speed", "connection_type")
            })
            merged[mac]["source"] = "router+arp"
        else:
            merged[mac] = {**c, "online": True, "source": "router"}

    return list(merged.values())


# ── App Lifespan ────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🏠 Casa Intelligence backend starting...")
    task = asyncio.create_task(scan_loop())
    yield
    task.cancel()
    router.logout()
    logger.info("👋 Shutdown complete")


# ── FastAPI App ─────────────────────────────────────────────────────────────
app = FastAPI(title="Casa Intelligence", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST Endpoints ──────────────────────────────────────────────────────────
@app.get("/api/status")
async def get_status():
    return {
        "status": "running",
        "scan_count": state["scan_count"],
        "online_count": state["online_count"],
        "router_connected": state["router"].get("connected", False),
        "tv_connected": state["tv"].get("connected", False),
        "alexa_count": len(state["alexa"]),
    }


@app.get("/api/devices")
async def get_devices():
    return {"devices": state["devices"], "count": len(state["devices"])}


@app.get("/api/router")
async def get_router():
    return {"info": state["router"]}


@app.get("/api/tv")
async def get_tv():
    return state["tv"]


@app.post("/api/tv/command")
async def tv_command(body: dict):
    command = body.get("command", "")
    value = body.get("value")
    success = await tv.send_command(command, value)
    return {"success": success, "command": command}


@app.get("/api/alexa")
async def get_alexa():
    return {"devices": state["alexa"]}


@app.post("/api/alexa/tts")
async def send_alexa_tts(payload: dict):
    """
    Send Text-to-Speech message to Alexa device.
    
    Note: This is a DEMO implementation. Real Amazon Alexa API integration
    requires AMAZON_EMAIL and AMAZON_PASSWORD credentials plus the ha-philipsjs
    library or similar.
    
    For production, implement using:
    - ha-philipsjs for TTS
    - Amazon Alexa API authentication
    - Device-specific targeting
    """
    message = payload.get("message", "").strip()
    
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    
    # Check if real credentials are configured
    has_credentials = bool(settings.alexa_email and settings.alexa_password)
    
    if has_credentials:
        # TODO: Implement real TTS using ha-philipsjs or Amazon API
        logger.info(f"📢 [DEMO] Would send TTS to Alexa: '{message}'")
        return {
            "success": True,
            "message": message,
            "mode": "demo",
            "note": "Real Amazon API integration pending - credentials detected but API not implemented"
        }
    else:
        # Simulate successful TTS for demo purposes
        logger.info(f"📢 [SIMULATION] TTS message simulated: '{message}'")
        return {
            "success": True,
            "message": message,
            "mode": "simulation",
            "note": "Configure AMAZON_EMAIL and AMAZON_PASSWORD in .env for real TTS"
        }


@app.get("/api/insights")
async def get_insights():
    """
    Generate AI insights about the smart home network.
    Now uses Groq (fast, free, unlimited) with Gemini fallback.
    """
    try:
        result = ai_provider.generate_insights(
            devices=state["devices"],
            tv_status=state["tv"],
            alexa_devices=state["alexa"],
            router_info=state["router"]
        )
        return result
    except Exception as e:
        logger.error(f"Insights generation failed: {e}", exc_info=True)
        # Return fallback insights
        return {
            "insights": [{
                "type": "warning",
                "icon": "⚠️",
                "message": "AI insights temporarily unavailable"
            }],
            "security": {"score": 5, "issues": ["AI service error"], "strengths": []},
            "recommendations": ["Check backend logs for details"],
            "provider": "error",
            "cached": False,
            "error": str(e)
        }


@app.get("/api/automations")
async def get_automations():
    return {"rules": automations.get_rules(), "alerts": automations.get_alerts()}


@app.post("/api/automations/{rule_id}/toggle")
async def toggle_automation(rule_id: str):
    success = automations.toggle(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"success": True, "rules": automations.get_rules()}


# ── WebSocket ────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    # Send current state immediately on connect
    await ws.send_json({"type": "initial", **state})
    
    try:
        while True:
            # Receive and handle messages (ping/pong, etc.)
            try:
                text = await ws.receive_text()
                
                # Parse JSON message
                try:
                    data = json.loads(text) if isinstance(text, str) else text
                    await manager.handle_message(ws, data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from WebSocket: {text[:100]}")
                    
            except asyncio.TimeoutError:
                # No message received, continue waiting
                continue
                
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
        manager.disconnect(ws)
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        manager.disconnect(ws)
