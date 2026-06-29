import os
import httpx
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="WhatsApp Middleware - Rectima")

# ── Credenciales ───────────────────────────────────────────────────────────────
RECTIMA_BASE_URL = os.getenv("RECTIMA_BASE_URL", "https://app.rectima.com.ec:4005")
RECTIMA_API_KEY  = os.getenv("RECTIMA_API_KEY", "")
ZAVUDEV_API_KEY  = os.getenv("ZAVUDEV_API_KEY", "")
GHL_WEBHOOK_URL  = os.getenv("GHL_WEBHOOK_URL", "")

RECTIMA_UBICACION = os.getenv(
    "RECTIMA_UBICACION",
    "📍 Nos encontramos en Ambato, Tungurahua. Lunes a viernes de 8:00 a 18:00."
)

MENU_TEXTO = (
    "👋 ¡Hola! Bienvenido a *Rectima*, tu tienda de repuestos automotrices.\n\n"
    "¿En qué podemos ayudarte?\n\n"
    "1️⃣ Ver nuestra *ubicación*\n"
    "2️⃣ Buscar un *repuesto*\n\n"
    "Responde con el número de tu opción."
)

OPCIONES_UBICACION = {"1", "ubicacion", "ubicación", "donde", "dónde", "dirección", "direccion"}
OPCIONES_REPUESTO  = {"2", "repuesto", "pieza", "parte", "buscar", "producto"}


# ── Helpers ────────────────────────────────────────────────────────────────────

async def enviar_zavu(telefono: str, mensaje: str):
    """Envía mensaje WhatsApp vía Zavu API."""
    url = "https://api.zavu.dev/v1/messages"
    headers = {
        "Authorization": f"Bearer {ZAVUDEV_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": telefono,
        "channel": "whatsapp",
        "type": "text",
        "text": mensaje,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(url, json=payload, headers=headers)
        print(f"Zavu send → {r.status_code}: {r.text[:200]}")
        return r.status_code in (200, 201)


async def enviar_menu_botones(telefono: str):
    """Intenta enviar menú con botones interactivos vía Zavu, cae en texto si falla."""
    url = "https://api.zavu.dev/v1/messages"
    headers = {
        "Authorization": f"Bearer {ZAVUDEV_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": telefono,
        "channel": "whatsapp",
        "type": "buttons",
        "text": "👋 ¡Bienvenido a *Rectima*! ¿En qué podemos ayudarte?",
        "buttons": [
            {"id": "ubicacion", "title": "📍 Nuestra ubicación"},
            {"id": "repuesto",  "title": "🔧 Buscar repuesto"},
        ],
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(url, json=payload, headers=headers)
        print(f"Zavu botones → {r.status_code}: {r.text[:200]}")
        if r.status_code not in (200, 201):
            await enviar_zavu(telefono, MENU_TEXTO)


async def buscar_rectima(query: str) -> str:
    """Busca repuestos en la API de Rectima."""
    try:
        import urllib.parse
        q = urllib.parse.quote(query)
        url = f"{RECTIMA_BASE_URL}/api/productos/buscar/{q}/null/null/5/0"
        headers = {"rectima-api-key": RECTIMA_API_KEY}
        async with httpx.AsyncClient(timeout=20.0, verify=False) as client:
            r = await client.get(url, headers=headers)
            print(f"Rectima → {r.status_code}: {r.text[:300]}")
            if r.status_code != 200:
                return "En este momento no puedo consultar el inventario. Por favor intenta más tarde."
            data = r.json()
            if not data or len(data) == 0:
                return f"No encontré repuestos para *{query}*. Intenta con otro término o código."
            lineas = [f"🔧 Resultados para *{query}*:\n"]
            for p in data[:5]:
                nombre = p.get("nombre") or p.get("descripcion") or "Sin nombre"
                sku    = p.get("codigo") or p.get("sku") or "S/N"
                stock  = p.get("stock", 0)
                precio = p.get("precio")
                estado = f"{stock} uds." if stock and stock > 0 else "Sin stock"
                precio_txt = f"  💰 ${precio}" if precio else ""
                lineas.append(f"• *{nombre}*\n  SKU: {sku} | {estado}{precio_txt}")
            return "\n".join(lineas)
    except Exception as e:
        print(f"Error Rectima: {e}")
        return "Error al consultar el inventario. Por favor intenta más tarde."


async def notificar_ghl(evento: str, telefono: str, extra: dict = {}):
    """Notifica al webhook de GHL para registrar en CRM."""
    if not GHL_WEBHOOK_URL:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(GHL_WEBHOOK_URL, json={
                "evento": evento,
                "phone": telefono,
                **extra,
            })
    except Exception:
        pass


def procesar_opcion(texto: str) -> str | None:
    t = texto.strip().lower()
    if t in OPCIONES_UBICACION:
        return "ubicacion"
    if t in OPCIONES_REPUESTO:
        return "repuesto"
    return None


# ── Webhook de Zavu ────────────────────────────────────────────────────────────

@app.post("/webhook/zavu")
async def webhook_zavu(request: Request):
    """Recibe eventos de Zavu (message.inbound, etc.)."""
    try:
        data = await request.json()
        print(f"Zavu webhook: {data}")

        evento = data.get("type", "")
        if evento != "message.inbound":
            return {"status": "ignorado", "type": evento}

        msg_data = data.get("data", {})
        telefono = msg_data.get("from", "")
        tipo_msg = msg_data.get("type", "text")

        # Botones interactivos — leer el id del botón presionado
        if tipo_msg in ("button_reply", "interactive"):
            mensaje = (
                msg_data.get("buttonReply", {}).get("id") or
                msg_data.get("interactive", {}).get("button_reply", {}).get("id") or
                msg_data.get("text", "")
            )
        else:
            mensaje = msg_data.get("text", "").strip()

        if not telefono or not mensaje:
            return {"status": "ignorado", "razon": "sin telefono o mensaje"}

        opcion = procesar_opcion(mensaje)

        if opcion == "ubicacion":
            await enviar_zavu(telefono, RECTIMA_UBICACION)
            await notificar_ghl("consulta_ubicacion", telefono)
            return {"status": "ok", "respuesta": "ubicacion"}

        if opcion == "repuesto":
            await enviar_zavu(telefono, "🔍 Buscando... ¿Qué repuesto necesitas? Escríbeme el nombre o código.")
            await notificar_ghl("inicio_busqueda", telefono)
            return {"status": "ok", "respuesta": "pidiendo_repuesto"}

        # Si el mensaje anterior fue "2" o "repuesto", ahora busca el producto
        # (Zavu maneja el contexto de conversación — aquí asumimos búsqueda directa)
        if len(mensaje) > 3 and opcion is None:
            respuesta = await buscar_rectima(mensaje)
            await enviar_zavu(telefono, respuesta)
            await notificar_ghl("busqueda_repuesto", telefono, {"query": mensaje})
            return {"status": "ok", "respuesta": "resultado_busqueda"}

        # Cualquier otro mensaje → menú
        await enviar_menu_botones(telefono)
        await notificar_ghl("menu_enviado", telefono)
        return {"status": "ok", "respuesta": "menu_enviado"}

    except Exception as e:
        print(f"Error webhook_zavu: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Webhook legacy GHL (mantener por compatibilidad) ──────────────────────────

@app.post("/webhook/ghl")
async def webhook_ghl(request: Request):
    try:
        data = await request.json()
        print(f"GHL webhook: {data}")
        mensaje    = (data.get("message") or data.get("body") or data.get("text") or "").strip()
        telefono   = (data.get("phone") or data.get("contactPhone") or data.get("from") or "").replace("+", "").replace(" ", "")
        return {"status": "recibido", "mensaje": mensaje, "telefono": telefono}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/debug")
async def webhook_debug(request: Request):
    body = await request.body()
    try:
        data = await request.json()
    except Exception:
        data = body.decode()
    print(f"DEBUG: {data}")
    return {"headers": dict(request.headers), "body": data}


@app.get("/health")
async def health():
    return {
        "status": "running",
        "rectima_url": RECTIMA_BASE_URL,
        "zavu_configured": bool(ZAVUDEV_API_KEY),
        "ghl_webhook": bool(GHL_WEBHOOK_URL),
    }


@app.get("/")
async def root():
    return {"mensaje": "Rectima WhatsApp Bot activo. Webhook Zavu: /webhook/zavu"}
