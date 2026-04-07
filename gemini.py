import logging
import json
import time
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Minimum seconds between Gemini API calls (free tier: 15 RPM = 1 every 4s, use 60s to be safe)
COOLDOWN_SECONDS = 60


class GeminiInsights:
    def __init__(self, api_key: str):
        self._ready = False
        self._last_call = 0.0
        self._cache: Dict[str, Any] = {}
        if api_key:
            try:
                import google.genai as genai
                self._client = genai.Client(api_key=api_key)
                self._ready = True
                logger.info("🧠 Gemini AI (google-genai) initialized")
            except ImportError:
                logger.error("google-genai package not installed. Run: pip install google-genai")
            except Exception as e:
                logger.error(f"Gemini init error: {e}")
        else:
            logger.warning("⚠️  No Gemini API key — AI insights disabled")

    async def analyze(
        self,
        devices: List[Dict],
        tv_status: Dict,
        alexa_devices: List[Dict],
    ) -> Dict[str, Any]:
        if not self._ready:
            return {"error": "Gemini not configured", "insights": []}

        # Cooldown check — return cached result if called too quickly
        now = time.time()
        elapsed = now - self._last_call
        if elapsed < COOLDOWN_SECONDS and self._cache:
            remaining = int(COOLDOWN_SECONDS - elapsed)
            logger.info(f"🧠 Gemini cooldown: returning cached result ({remaining}s remaining)")
            return {**self._cache, "cached": True, "cooldown_remaining": remaining}

        online = [d for d in devices if d.get("online")]
        unknown = [d for d in online if not d.get("vendor") or d.get("vendor") == "Unknown"]

        context = {
            "total_devices": len(devices),
            "online_count": len(online),
            "unknown_devices": len(unknown),
            "devices": [
                {"ip": d.get("ip"), "vendor": d.get("vendor"), "hostname": d.get("hostname")}
                for d in online[:20]
            ],
            "tv_on": tv_status.get("status") == "on",
            "tv_model": tv_status.get("model", "Samsung TV 2023"),
            "alexa_online": len(alexa_devices),
        }

        prompt = f"""You are a smart home AI assistant analyzing a real home network.

Network snapshot:
{json.dumps(context, indent=2)}

Provide a JSON response with EXACTLY this structure (no markdown, just JSON):
{{
  "summary": "One-sentence friendly summary of the home network right now",
  "insights": [
    {{"type": "info|warning|tip", "title": "Short title", "body": "2-3 sentence insight"}}
  ],
  "automations": [
    {{"title": "Automation idea", "description": "How it would work and benefit"}}
  ],
  "security": {{"score": 7, "notes": "One sentence security observation"}}
}}

Generate 3-4 insights and 2-3 automation ideas. Be specific to the actual devices found. Respond ONLY with valid JSON."""

        try:
            self._last_call = time.time()
            response = self._client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            text = response.text.strip()
            # Strip markdown code block if present
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            result = json.loads(text.strip())
            self._cache = result  # Cache for cooldown
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Gemini JSON parse error: {e}")
            fallback = {
                "summary": "Network analysis complete",
                "insights": [{"type": "info", "title": "Analysis ready", "body": "Gemini returned a non-JSON response. Check logs."}],
                "automations": [],
                "security": {"score": 5, "notes": "Manual review recommended"},
            }
            self._cache = fallback
            return fallback
        except Exception as e:
            error_str = str(e)
            logger.error(f"Gemini API error: {e}")
            # If rate limited and we have cache, return it
            if "429" in error_str and self._cache:
                return {**self._cache, "cached": True, "cooldown_remaining": COOLDOWN_SECONDS}
            return {"error": error_str, "insights": []}
