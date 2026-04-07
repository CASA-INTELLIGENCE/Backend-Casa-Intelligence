"""
AI Provider - Groq Integration
Replaces Gemini API with Groq for reliable, fast, and free AI insights.

Why Groq:
- 100% Free (no credit card required)
- 14,400 requests/day (vs Gemini's ~15-50)
- Ultra-fast: ~300ms latency
- No 429 errors (RESOURCE_EXHAUSTED)
- Llama 3 70B model (excellent quality)

Setup:
1. Get free API key: https://console.groq.com/keys
2. Add to .env: GROQ_API_KEY=gsk_your_key_here
3. Restart backend
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Try to import Groq (will be installed)
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logger.warning("Groq library not installed. Run: pip install groq")

# Fallback to Gemini if Groq not available
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class AIProvider:
    """
    AI Provider with Groq (primary) and Gemini (fallback).
    
    Priority:
    1. Groq (fast, free, unlimited)
    2. Gemini (fallback if Groq fails)
    """
    
    def __init__(self):
        self.provider = None
        self.groq_client = None
        self.gemini_model = None
        
        # Try Groq first
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key and GROQ_AVAILABLE:
            try:
                self.groq_client = Groq(api_key=groq_key)
                self.provider = "groq"
                logger.info("✅ AI Provider: Groq (fast, free, unlimited)")
            except Exception as e:
                logger.warning(f"Groq initialization failed: {e}")
        
        # Fallback to Gemini
        if not self.provider:
            gemini_key = os.getenv("GEMINI_API_KEY")
            if gemini_key and GEMINI_AVAILABLE:
                try:
                    genai.configure(api_key=gemini_key)
                    # Use stable model (not experimental)
                    # gemini-1.5-flash is fast and reliable
                    self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                    self.provider = "gemini"
                    logger.info("⚠️  AI Provider: Gemini (fallback - may hit rate limits)")
                    logger.info("💡 Tip: Configure GROQ_API_KEY for better performance and no rate limits")
                except Exception as e:
                    logger.error(f"Gemini initialization failed: {e}")
                    # Try legacy model as last resort
                    try:
                        self.gemini_model = genai.GenerativeModel('gemini-pro')
                        self.provider = "gemini"
                        logger.info("⚠️  AI Provider: Gemini (legacy model)")
                    except Exception as e2:
                        logger.error(f"Gemini legacy model also failed: {e2}")
        
        if not self.provider:
            logger.error("❌ No AI provider available. Set GROQ_API_KEY or GEMINI_API_KEY in .env")
    
    def generate_insights(
        self,
        devices: list,
        tv_status: dict,
        alexa_devices: list,
        router_info: dict
    ) -> Dict[str, Any]:
        """
        Generate AI insights about the smart home network.
        
        Returns dict with:
        - insights: list of insight objects
        - security: security analysis
        - recommendations: list of recommendations
        - provider: which AI was used
        - cached: whether result was cached
        """
        
        if not self.provider:
            return self._generate_fallback_insights(devices, tv_status, alexa_devices)
        
        # Build prompt
        prompt = self._build_prompt(devices, tv_status, alexa_devices, router_info)
        
        # Try primary provider (Groq)
        if self.provider == "groq":
            try:
                result = self._call_groq(prompt)
                result["provider"] = "groq"
                result["cached"] = False
                return result
            except Exception as e:
                logger.error(f"Groq failed: {e}")
                # Try Gemini fallback
                if self.gemini_model:
                    try:
                        result = self._call_gemini(prompt)
                        result["provider"] = "gemini_fallback"
                        result["cached"] = False
                        return result
                    except Exception as e2:
                        logger.error(f"Gemini fallback failed: {e2}")
        
        # Gemini as primary
        elif self.provider == "gemini":
            try:
                result = self._call_gemini(prompt)
                result["provider"] = "gemini"
                result["cached"] = False
                return result
            except Exception as e:
                logger.error(f"Gemini failed: {e}")
        
        # Final fallback: static insights
        logger.warning("All AI providers failed, using fallback insights")
        return self._generate_fallback_insights(devices, tv_status, alexa_devices)
    
    def _call_groq(self, prompt: str) -> Dict[str, Any]:
        """Call Groq API with automatic model fallback"""
        models = [
            "llama-3.3-70b-versatile",
            "llama3-8b-8192",
            "mixtral-8x7b-32768"
        ]
        
        last_error = None
        
        for model in models:
            try:
                logger.info(f"Trying Groq model: {model}")
                
                response = self.groq_client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a smart home security and optimization expert. Analyze network data and provide actionable insights in JSON format."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.7,
                    max_tokens=2048,
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content
                logger.info(f"Groq model {model} succeeded")
                return json.loads(content)
                
            except Exception as e:
                error_msg = str(e)
                
                if "model_decommissioned" in error_msg or "has been decommissioned" in error_msg:
                    logger.warning(f"Groq model {model} decommissioned, trying next model")
                else:
                    logger.warning(f"Groq model {model} failed: {e}")
                
                last_error = e
                continue
        
        raise Exception(f"All Groq models failed. Last error: {last_error}")
    
    def _call_gemini(self, prompt: str) -> Dict[str, Any]:
        """Call Gemini API (fallback)"""
        try:
            response = self.gemini_model.generate_content(prompt)
            
            # Try to extract JSON from response
            text = response.text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            
            return json.loads(text)
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            # Log the error details for debugging
            logger.debug(f"Gemini error details: {type(e).__name__}: {str(e)}")
            raise  # Re-raise to trigger fallback
    
    def _build_prompt(self, devices, tv_status, alexa_devices, router_info) -> str:
        """Build prompt for AI analysis"""
        online_count = len([d for d in devices if d.get('online')])
        
        prompt = f"""
Analyze this smart home network and provide insights in JSON format.

NETWORK DATA:
- Total devices: {len(devices)}
- Online devices: {online_count}
- Router: {router_info.get('vendor', 'Unknown')} at {router_info.get('ip', 'Unknown')}
- Samsung TV: {tv_status.get('status', 'unknown')}
- Alexa devices: {len(alexa_devices)}

DEVICES:
{json.dumps(devices[:10], indent=2)}

Provide response in this EXACT JSON format:
{{
  "insights": [
    {{"type": "info|warning|tip", "icon": "emoji", "message": "insight text"}}
  ],
  "security": {{
    "score": 1-10,
    "issues": ["issue1", "issue2"],
    "strengths": ["strength1", "strength2"]
  }},
  "recommendations": [
    "recommendation 1",
    "recommendation 2"
  ]
}}

Focus on:
1. Security vulnerabilities (unknown devices, weak passwords)
2. Network optimization (device placement, bandwidth)
3. Smart home automation opportunities
4. Energy saving tips
"""
        return prompt
    
    def _generate_fallback_insights(self, devices, tv_status, alexa_devices) -> Dict[str, Any]:
        """Generate static insights when AI is unavailable"""
        online_count = len([d for d in devices if d.get('online')])
        unknown_devices = [d for d in devices if not d.get('vendor') or d.get('vendor') == 'Unknown']
        
        insights = []
        
        # Network health
        if online_count > 0:
            insights.append({
                "type": "info",
                "icon": "🌐",
                "message": f"Network healthy with {online_count} devices online"
            })
        
        # Unknown devices warning
        if len(unknown_devices) > 0:
            insights.append({
                "type": "warning",
                "icon": "⚠️",
                "message": f"{len(unknown_devices)} unknown devices detected - verify they belong to you"
            })
        
        # TV integration
        if tv_status.get('connected'):
            insights.append({
                "type": "tip",
                "icon": "📺",
                "message": "Samsung TV connected - automate routines like 'Movie Mode'"
            })
        
        # Alexa integration
        if len(alexa_devices) > 0:
            insights.append({
                "type": "tip",
                "icon": "🎙️",
                "message": "Alexa detected - enable voice-controlled home automation"
            })
        
        return {
            "insights": insights,
            "security": {
                "score": 7,
                "issues": ["AI insights unavailable - configure GROQ_API_KEY"],
                "strengths": ["Network monitoring active", "Basic security in place"]
            },
            "recommendations": [
                "Get free Groq API key: https://console.groq.com/keys",
                "Add to .env: GROQ_API_KEY=gsk_your_key_here",
                "Restart backend to enable AI insights"
            ],
            "provider": "fallback",
            "cached": False
        }


# Global instance
_ai_provider = None

def get_ai_provider() -> AIProvider:
    """Get or create AI provider singleton"""
    global _ai_provider
    if _ai_provider is None:
        _ai_provider = AIProvider()
    return _ai_provider


# Backward compatibility with gemini.py
async def generate_insights(devices, tv_status, alexa_devices, router_info=None):
    """
    Generate AI insights (backward compatible with gemini.py).
    
    Now uses Groq (fast, free, unlimited) with Gemini fallback.
    """
    if router_info is None:
        router_info = {}
    
    provider = get_ai_provider()
    return provider.generate_insights(devices, tv_status, alexa_devices, router_info)
