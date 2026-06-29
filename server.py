import os
import httpx
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="WhatsApp Middleware")

GHL_API_KEY = os.getenv("GHL_API_KEY", "")
GHL_LOCATION_ID = os.getenv("GHL_LOCATION_ID", "M48FTeSFzw456hym1fZ5")
RECTIMA_BASE_URL = os.getenv("RECTIMA_BASE_URL", "https://app.rectima.com.ec:4005")
RECTIMA_API_KEY = os.getenv("RECTIMA_API_KEY", "")


async def consultar_rectima(mensaje: str, telefono: str) -> str:
    """Consulta la API de Rectima y retorna la respuesta."""
    try:
        url = f"{RECTIMA_BASE_URL}/api/chat"
        headers = {
            "Authorization": f"Bearer {RECTIMA_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "message": mensaje,
            "phone": telefono
        }
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            r = await client.post(url, json=payload, headers=headers)
            print(f"Rectima → {r.status_code}: {r.text[:200]}")
            if r.status_code == 200:
                data = r.json()
                return data.get("response") or data.get("message") or str(data)
            else:
                return f"Hola, recibí tu mensaje. Estamos procesando tu consulta."
    except Exception as e:
        print(f"Error Rectima: {e}")
        return "Hola, recibí tu mensaje. En un momento te respondemos."


async def enviar_whatsapp_ghl(contact_id: str, mensaje: str):
    """Envía respuesta WhatsApp via GHL API."""
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
        print(f"GHL webhook: {data}")

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

        respuesta = await consultar_rectima(mensaje, telefono)

        if contact_id:
            await enviar_whatsapp_ghl(contact_id, respuesta)
        else:
            print(f"Sin contactId — no se puede enviar. Teléfono: {telefono}")

        return {"status": "ok", "respuesta": respuesta}

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {
        "status": "running",
        "ghl_location": GHL_LOCATION_ID,
        "rectima_url": RECTIMA_BASE_URL
    }


@app.get("/")
async def root():
    return {"mensaje": "WhatsApp Middleware activo. Usa /webhook/ghl para GHL."}
