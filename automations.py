import asyncio
import logging
from datetime import datetime, time as dtime
from typing import List, Dict, Optional, Callable

logger = logging.getLogger(__name__)


class Rule:
    def __init__(self, id: str, title: str, description: str, enabled: bool = True):
        self.id = id
        self.title = title
        self.description = description
        self.enabled = enabled
        self.last_triggered: Optional[str] = None
        self.trigger_count = 0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "enabled": self.enabled,
            "last_triggered": self.last_triggered,
            "trigger_count": self.trigger_count,
        }


class AutomationEngine:
    def __init__(self):
        self._previous_devices: set = set()
        self._alerts: List[Dict] = []

        self.rules: List[Rule] = [
            Rule(
                "night_mode",
                "🌙 Night Mode Alert",
                "After 10 PM, if the TV is on for more than 2 hours, send a reminder",
            ),
            Rule(
                "unknown_device",
                "🚨 Unknown Device Alert",
                "Alert when a previously unseen device joins the network",
            ),
            Rule(
                "phone_away",
                "📴 Everyone's Away",
                "When all known phones disconnect from WiFi — home may be empty",
            ),
        ]

    def get_rules(self) -> List[Dict]:
        return [r.to_dict() for r in self.rules]

    def toggle(self, rule_id: str) -> bool:
        for rule in self.rules:
            if rule.id == rule_id:
                rule.enabled = not rule.enabled
                logger.info(f"Rule '{rule.title}' → {'ON' if rule.enabled else 'OFF'}")
                return True
        return False

    def get_alerts(self) -> List[Dict]:
        return self._alerts[-10:]  # Last 10 alerts

    async def check(self, devices: List[Dict], tv_status: Dict, alexa_devices: List[Dict]):
        now = datetime.now()
        current_macs = {d.get("mac") for d in devices if d.get("online")}

        # Rule: Unknown Device Alert
        rule = self._get_rule("unknown_device")
        if rule and rule.enabled and self._previous_devices:
            new_macs = current_macs - self._previous_devices
            if new_macs:
                for mac in new_macs:
                    device = next((d for d in devices if d.get("mac") == mac), {})
                    vendor = device.get("vendor", "Unknown")
                    ip = device.get("ip", "?")
                    alert = {
                        "rule": "unknown_device",
                        "level": "warning",
                        "message": f"New device joined: {vendor} ({ip}) [{mac}]",
                        "time": now.isoformat(),
                    }
                    self._alerts.append(alert)
                    rule.trigger_count += 1
                    rule.last_triggered = now.isoformat()
                    logger.warning(f"🚨 {alert['message']}")

        # Rule: Night Mode
        rule = self._get_rule("night_mode")
        if rule and rule.enabled:
            if now.hour >= 22 and tv_status.get("status") == "on":
                alert = {
                    "rule": "night_mode",
                    "level": "info",
                    "message": "It's late! Your Samsung TV is still on 🌙",
                    "time": now.isoformat(),
                }
                # Avoid spam — only trigger once per hour
                if not self._alerts or self._alerts[-1].get("rule") != "night_mode":
                    self._alerts.append(alert)
                    rule.trigger_count += 1
                    rule.last_triggered = now.isoformat()

        self._previous_devices = current_macs

    def _get_rule(self, rule_id: str) -> Optional[Rule]:
        return next((r for r in self.rules if r.id == rule_id), None)
