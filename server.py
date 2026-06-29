import os
import httpx
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="WhatsApp Middleware")

GHL_API_KEY = os.getenv("GHL_API_KEY", "")
GHL_LOCATION_ID = os.getenv("GHL_LOCATION_ID", "M48FTeSFzw456hym1fZ5")


async def consultar_api_externa(mensaje: str, telefono: str) -> str:
    # Reemplaza esto con tu llamada real a la API (Rectima, etc.)
    return f"Hola, recibí tu mensaje: '{mensaje}'. Pronto te respondo."


async def enviar_whatsapp_ghl(contact_id: str, mensaje: str):
    """Envía respuesta WhatsApp via GHL API usando el contactId del webhook."""
    url = "https://services.leadconnectorhq.com/conversations/messages"
    headers = {
        "Authorization": f"Bearer {GHL_API_KEY}",
        "Content-Type": "application/json",
        "Version": "2021-04-15"
    }
    payload = {
        "type": "WhatsApp",
        "contactId": contact_id,
        "message": mensaje
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=payload, headers=headers)
        print(f"GHL reply → {r.status_code}: {r.text}")


@app.post("/webhook/ghl")
async def webhook_ghl(request: Request):
    """Recibe mensajes entrantes de GHL y responde via WhatsApp."""
    try:
        data = await request.json()
        print(f"GHL webhook recibido: {data}")

        mensaje = (
            data.get("message") or
            data.get("body") or
            data.get("text") or
            str(data)
        )
        contact_id = data.get("contactId") or data.get("contact_id") or ""
        telefono = (
            data.get("phone") or
            data.get("contactPhone") or
            data.get("from") or ""
        ).replace("+", "").replace(" ", "")

        if not contact_id and not telefono:
            return {"status": "ignorado", "razon": "sin contactId ni telefono"}

        respuesta = await consultar_api_externa(mensaje, telefono)

        if contact_id:
            await enviar_whatsapp_ghl(contact_id, respuesta)
        else:
            print(f"Sin contactId, no se puede enviar respuesta. Teléfono: {telefono}")

        return {"status": "ok", "respuesta": respuesta}

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "running", "ghl_location": GHL_LOCATION_ID}


@app.get("/")
async def root():
    return {"mensaje": "WhatsApp Middleware activo. Usa /webhook/ghl para GHL."}
