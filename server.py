import os
import httpx
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="WhatsApp Middleware")

GHL_API_KEY = os.getenv("GHL_API_KEY", "")
GHL_LOCATION_ID = os.getenv("GHL_LOCATION_ID", "M48FTeSFzw456hym1fZ5")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")


async def consultar_api_externa(mensaje: str, telefono: str) -> str:
    """
    Aquí va la lógica de tu API externa (Rectima u otras).
    Retorna el texto de respuesta para el cliente.
    """
    # Por ahora responde un mensaje de prueba
    # Reemplaza esto con tu llamada real a la API
    return f"Hola, recibí tu mensaje: '{mensaje}'. Pronto te respondo."


async def enviar_whatsapp(telefono: str, mensaje: str):
    """Envía un mensaje de WhatsApp via Meta Cloud API."""
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        print("⚠️  WHATSAPP_TOKEN o WHATSAPP_PHONE_ID no configurados")
        return

    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "text",
        "text": {"body": mensaje}
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=payload, headers=headers)
        print(f"WhatsApp enviado → {r.status_code}: {r.text}")


@app.post("/webhook/ghl")
async def webhook_ghl(request: Request):
    """Recibe mensajes entrantes de GHL y responde via WhatsApp."""
    try:
        data = await request.json()
        print(f"📩 GHL webhook recibido: {data}")

        # GHL envía el mensaje en distintos campos según el tipo
        mensaje = (
            data.get("message") or
            data.get("body") or
            data.get("text") or
            str(data)
        )
        telefono = (
            data.get("phone") or
            data.get("contactPhone") or
            data.get("from") or ""
        ).replace("+", "").replace(" ", "")

        if not telefono:
            return {"status": "ignorado", "razon": "sin telefono"}

        # Consultar API externa
        respuesta = await consultar_api_externa(mensaje, telefono)

        # Enviar respuesta por WhatsApp
        await enviar_whatsapp(telefono, respuesta)

        return {"status": "ok", "respuesta": respuesta}

    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "running", "ghl_location": GHL_LOCATION_ID}


@app.get("/")
async def root():
    return {"mensaje": "WhatsApp Middleware activo. Usa /webhook/ghl para GHL."}
