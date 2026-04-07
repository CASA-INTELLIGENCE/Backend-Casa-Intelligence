# 🐍 Casa Intelligence — Backend (FastAPI)

> Motor de descubrimiento y automatización del hogar inteligente.

## ✅ Qué construí y por qué

**Objetivo:** Reducir hardcodeo sin reescribir todo el sistema.  
**Solución:** Descubrimiento **semi-dinámico** con mDNS + SSDP, manteniendo ARP y las integraciones existentes.

Esto permite detectar dispositivos automáticamente en la red local, enriquecer el estado actual y seguir usando Samsung TV, Alexa y router como antes.

---

## 🔍 Descubrimiento actual

- **ARP + Router API:** base confiable para presencia/estado.
- **mDNS (zeroconf):** detecta servicios tipo Chromecast/Google Home/AirPlay.
- **SSDP/UPnP (ssdpy):** detecta TVs y media servers.
- **Clasificación simple:** hostname + vendor → `tv` | `speaker` | `smart_device` | `unknown`.
- **Mini‑plugins:** handlers simples por tipo (TV, speaker, smart device).

---

## 🧩 Integraciones existentes (se mantienen)

- **Samsung TV:** `samsungtvws[encrypted]`
- **Alexa (detección):** por red local + UI TTS (demo)
- **Router TP‑Link:** cliente DHCP + estado de red
- **IA:** Groq como proveedor principal con fallback

---

## 🚀 Instalación y uso

```bash
pip install -r requirements.txt
python -m uvicorn main:app --port 8000
```

---

## 🔗 Endpoints clave

- `GET /api/devices` → Dispositivos detectados + enrichment
- `GET /api/discover` → Forzar discovery manual (mDNS + SSDP)
- `GET /api/insights` → Insights IA
- `POST /api/tv/command` → Control TV
- `POST /api/alexa/tts` → Demo TTS Alexa

---

## 🛠️ Tecnologías

- **FastAPI** + **Uvicorn**
- **zeroconf** (mDNS)
- **ssdpy** (SSDP)
- **manuf** (MAC vendor)
- **WebSockets** para updates en tiempo real

---

*Parte del Reto Técnico AdoptAI — Vibe Engineer Challenge*
