import os
import httpx
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="WhatsApp Middleware")

GHL_API_KEY = os.getenv("GHL_API_KEY", "")
GHL_LOCATION_ID = os.getenv("GHL_LOCATION_ID", "ViNYocNHiwMs8HQMUbMu")
RECTIMA_BASE_URL = os.getenv("RECTIMA_BASE_URL", "https://app.rectima.com.ec:4005")
RECTIMA_API_KEY = os.getenv("RECTIMA_API_KEY", "")
RECTIMA_UBICACION = os.getenv("RECTIMA_UBICACION", "📍 Nos encontramos en Ambato, Tungurahua. Puedes visitarnos en horario de lunes a viernes de 8:00 a 18:00.")

MENU = """👋 ¡Hola! Bienvenido a *Rectima*.

¿En qué podemos ayudarte hoy?

1️⃣ Ver nuestra *ubicación*
2️⃣ Buscar un *repuesto*

Responde con el número de tu opción."""

OPCIONES_UBICACION = {"1", "ubicacion", "ubicación", "donde", "dónde", "dirección", "direccion"}
OPCIONES_REPUESTO = {"2", "repuesto", "pieza", "parte", "buscar", "producto"}


async def consultar_rectima(mensaje: str, telefono: str) -> str:
    try:
        url = f"{RECTIMA_BASE_URL}/api/chat"
        headers = {
            "Authorization": f"Bearer {RECTIMA_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {"message": mensaje, "phone": telefono}
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            r = await client.post(url, json=payload, headers=headers)
            print(f"Rectima → {r.status_code}: {r.text[:200]}")
            if r.status_code == 200:
                data = r.json()
                return data.get("response") or data.get("message") or str(data)
            else:
                return "En este momento no podemos procesar tu consulta. Por favor intenta más tarde."
    except Exception as e:
        print(f"Error Rectima: {e}")
        return "En este momento no podemos procesar tu consulta. Por favor intenta más tarde."


async def enviar_whatsapp_ghl(contact_id: str, mensaje: str):
    url = "https://services.leadconnectorhq.com/conversations/messages"
    headers = {
        "Authorization": f"Bearer {GHL_API_KEY}",
        "Content-Type": "application/json",
        "Version": "2021-04-15"
    }
    payload = {"type": "WhatsApp", "contactId": contact_id, "message": mensaje}
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=payload, headers=headers)
        print(f"GHL reply → {r.status_code}: {r.text}")


def procesar_opcion(mensaje: str) -> str | None:
    texto = mensaje.strip().lower()
    if texto in OPCIONES_UBICACION:
        return "ubicacion"
    if texto in OPCIONES_REPUESTO:
        return "repuesto"
    return None


@app.post("/webhook/ghl")
async def webhook_ghl(request: Request):
    try:
        data = await request.json()
        print(f"GHL webhook: {data}")

        mensaje = (
            data.get("message") or
            data.get("body") or
            data.get("text") or ""
        ).strip()

        contact_id = data.get("contactId") or data.get("contact_id") or ""
        telefono = (
            data.get("phone") or
            data.get("contactPhone") or
            data.get("from") or ""
        ).replace("+", "").replace(" ", "")

        if not contact_id and not telefono:
            return {"status": "ignorado", "razon": "sin contactId ni telefono"}

        opcion = procesar_opcion(mensaje)

        if opcion == "ubicacion":
            respuesta = RECTIMA_UBICACION
        elif opcion == "repuesto":
            respuesta = await consultar_rectima(mensaje, telefono)
        else:
            # Cualquier otro mensaje → mostrar menú
            respuesta = MENU

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
