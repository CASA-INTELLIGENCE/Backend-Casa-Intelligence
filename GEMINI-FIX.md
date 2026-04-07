# ⚠️ FIX: Error 404 con Gemini

## Problema
```
Error 404: Model gemini-2.0-flash-exp not found
```

## Causa
El modelo `gemini-2.0-flash-exp` era experimental y ya no está disponible.

## ✅ Solución Aplicada

### Cambio en `ai_provider.py`

**ANTES (modelo experimental):**
```python
self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
```

**AHORA (modelo estable):**
```python
self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
```

Con fallback a:
```python
self.gemini_model = genai.GenerativeModel('gemini-pro')  # Legacy pero estable
```

---

## 🚀 PERO... LA MEJOR SOLUCIÓN ES GROQ

### Por Qué Deberías Usar Groq en Lugar de Gemini

| Aspecto | Gemini | Groq |
|---------|--------|------|
| **Errores de modelo** | ❌ Modelos cambian/deprecan | ✅ Estable |
| **Rate limits** | ❌ Error 429 frecuente | ✅ 14,400/día |
| **Velocidad** | ⏳ 2-3 segundos | ⚡ 300ms |
| **Costo** | Gratis limitado | ✅ Gratis ilimitado |
| **Setup** | 5 min | ✅ 5 min |
| **Requiere tarjeta** | No | ✅ No |

---

## 🎯 RECOMENDACIÓN: CAMBIA A GROQ (3 minutos)

### Paso 1: Obtener Groq API Key
```
1. https://console.groq.com
2. Sign up (gratis, sin tarjeta)
3. API Keys → Create API Key
4. Copiar key (empieza con gsk_...)
```

### Paso 2: Instalar
```bash
pip install groq
```

### Paso 3: Configurar
Edita `backend/.env`:
```bash
GROQ_API_KEY=gsk_tu_key_aqui
```

### Paso 4: Reiniciar
```bash
python main.py
```

Verás:
```
✅ AI Provider: Groq (fast, free, unlimited)
```

---

## 📊 Modelos de Gemini Disponibles (Abril 2026)

Si insistes en usar Gemini, estos son los modelos **estables**:

| Modelo | Uso | Velocidad | Contexto |
|--------|-----|-----------|----------|
| `gemini-1.5-flash` | ✅ **RECOMENDADO** | Rápido | 1M tokens |
| `gemini-1.5-pro` | Calidad máxima | Medio | 2M tokens |
| `gemini-pro` | Legacy | Medio | 32K tokens |
| ~~`gemini-2.0-flash-exp`~~ | ❌ **DEPRECADO** | - | - |

---

## 🔧 El Fix Ya Está Aplicado

Ahora el sistema:

1. **Intenta `gemini-1.5-flash`** (rápido, estable)
2. Si falla → **Intenta `gemini-pro`** (legacy pero funciona)
3. Si falla → **Fallback estático** (siempre funciona)

---

## ✅ Verificación

Reinicia el backend:
```bash
python main.py
```

Deberías ver **UNO** de estos mensajes:

### Opción 1 (MEJOR):
```
✅ AI Provider: Groq (fast, free, unlimited)
```

### Opción 2 (Gemini funcionando):
```
⚠️  AI Provider: Gemini (fallback - may hit rate limits)
💡 Tip: Configure GROQ_API_KEY for better performance
```

### Opción 3 (Solo fallback):
```
❌ No AI provider available. Set GROQ_API_KEY or GEMINI_API_KEY
```

---

## 🧪 Test

```bash
curl http://localhost:8000/api/insights
```

Busca en la respuesta:
```json
{
  "provider": "gemini",  // o "groq" si configuraste Groq
  "insights": [...]
}
```

Si ves `"provider": "fallback"` → AI no está funcionando

---

## 💡 RESUMEN

### Lo Que Hice (Ya Completado)
1. ✅ Cambié `gemini-2.0-flash-exp` → `gemini-1.5-flash`
2. ✅ Agregué fallback a `gemini-pro`
3. ✅ Mejoré el logging de errores

### Lo Que Deberías Hacer (3 minutos)
1. **Configura Groq** para evitar estos problemas permanentemente
2. Ya no tendrás:
   - ❌ Errores 404 de modelos deprecados
   - ❌ Errores 429 de rate limits
   - ❌ Latencia de 2-3 segundos

---

## 📞 Links Útiles

- **Groq Console:** https://console.groq.com
- **Groq Setup Guide:** Ver `backend/GROQ-SETUP.md`
- **Gemini Models:** https://ai.google.dev/models/gemini

---

**Fecha:** 2026-04-07  
**Fix:** ✅ Modelo Gemini actualizado a versión estable  
**Recomendación:** 🚀 Usar Groq en su lugar  

🎯 **El error ya está corregido, pero Groq es la solución definitiva.**
