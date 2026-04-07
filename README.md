# 🐍 Casa Intelligence — Backend (FastAPI)

> **Motor de descubrimiento y automatización del hogar inteligente.**

Este es el núcleo de **Casa Intelligence**, encargado de escanear la red local, interactuar con APIs de hardware (TP-Link, Samsung, Amazon) y procesar insights con Google Gemini AI.

## 🛠️ Tecnologías Utilizadas

- **Framework:** FastAPI (Python 3.12+)
- **Tiempo Real:** WebSockets nativos para streaming de estado a dispositivos.
- **Descubrimiento de Red:** 
  - **Ping Sweep Activo:** Inundación controlada de la subred para forzar el registro ARP.
  - **Windows ARP:** Extracción de tablas de direcciones MAC y mapeo de vendedores.
- **Integraciones:** 
  - `samsungtvws[encrypted]` para control de TVs Samsung 2023.
  - `google-genai` (Gemini 2.0 Flash) para análisis de seguridad y patrones.
  - SSDP (Simple Service Discovery Protocol) para encontrar hardware en red.

## 🚀 Instalación y Uso

1. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configurar el entorno:**
   Crea un archivo `.env` o edita el existente:
   ```env
   GEMINI_API_KEY=AIzaSy...
   ROUTER_IP=192.168.0.1
   ROUTER_PASSWORD=tu_password
   ```

3. **Arrancar el servidor:**
   ```bash
   python -m uvicorn main:app --reload --port 8002
   ```

## 🔍 Funcionalidades Clave

- **Scan Loop:** Un bucle de fondo que actualiza el estado de la red cada 15 segundos sin bloquear la API.
- **Discovery Granular:** Detecta el Echo Dot (vía MAC OUI) y la TV (vía SSDP) de forma autónoma.
- **Motor de Reglas:** Lógica extensible para disparar alertas cuando ocurren eventos en la red (ej: dispositivo desconocido detectado).
- **Gemini Insights:** Punto final `/api/insights` que envía el snapshot de la red a la IA para generar consejos de seguridad.

---
*Parte del Reto Técnico AdoptAI — Vibe Engineer Challenge*
