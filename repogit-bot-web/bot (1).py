import os
import time
import requests
import threading
from flask import Flask, jsonify, request, send_from_directory
from openai import OpenAI
from supabase import create_client

# ───── CONFIG ─────
TELEGRAM_TOKEN     = os.getenv("TELEGRAM_TOKEN")
SUPABASE_URL       = os.getenv("SUPABASE_URL")
SUPABASE_KEY       = os.getenv("SUPABASE_KEY")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
FOOTBALL_DATA_TOKEN= os.getenv("FOOTBALL_DATA_TOKEN")

URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY
)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__, static_folder="static", static_url_path="/static")

# ───── EQUIPOS ─────
EQUIPOS = {
    "real madrid": 541,
    "madrid":      541,
    "barcelona":   529,
    "barça":       529,
    "barca":       529,
    "atletico":    530,
    "atlético":    530,
    "sevilla":     536,
    "valencia":    532
}

# ───── TELEGRAM HELPERS ─────
def enviar(chat_id, texto):
    requests.post(
        URL + "sendMessage",
        json={"chat_id": chat_id, "text": texto, "parse_mode": "Markdown"}
    )

# ───── DETECTORES ─────
def detectar_equipo(texto):
    texto = texto.lower()
    for nombre, tid in EQUIPOS.items():
        if nombre in texto:
            return tid, nombre
    return None, None


def es_pregunta_futbol(texto):
    texto = texto.lower()
    palabras = ["partido", "partidos", "juega", "cuando juega", "cuándo juega", "resultado", "marcador"]
    return any(p in texto for p in palabras)


def es_pregunta_eventos(texto):
    texto = texto.lower()
    palabras = ["mis eventos", "eventos", "agenda", "calendario",
                "que eventos tengo", "dime mis eventos", "muestrame mis eventos"]
    return any(p in texto for p in palabras)


# ───── FUTBOL ─────
def consultar_partidos(team_id, nombre):
    headers = {"x-apisports-key": FOOTBALL_DATA_TOKEN}
    try:
        r = requests.get(
            "https://v3.football.api-sports.io/fixtures",
            headers=headers,
            params={"team": team_id, "next": 5, "timezone": "Europe/Madrid"},
            timeout=10
        )
        data = r.json()
        partidos = data.get("response", [])
        if not partidos:
            return f"⚽ No encontré próximos partidos para *{nombre.title()}*."
        lineas = []
        for p in partidos:
            fecha    = p["fixture"]["date"][:10]
            hora     = p["fixture"]["date"][11:16]
            local    = p["teams"]["home"]["name"]
            visitante= p["teams"]["away"]["name"]
            liga     = p["league"]["name"]
            lineas.append(f"📅 *{fecha} {hora}*\n{local} vs {visitante}\n_{liga}_")
        return f"⚽ *Próximos partidos de {nombre.title()}*\n\n" + "\n\n".join(lineas)
    except Exception as e:
        print("ERROR FUTBOL", e)
        return "⚠️ Error consultando fútbol."


# ───── EVENTOS ─────
def leer_eventos():
    try:
        res = supabase.table("eventos").select("*").execute()
        if not res.data:
            return "📭 No tienes eventos."
        lineas = [f"• *{e['nombre_evento']}* — {e['fecha']}" for e in res.data]
        return "📅 *Tus eventos*\n\n" + "\n".join(lineas)
    except Exception as e:
        print(e)
        return "❌ Error leyendo eventos."


def leer_eventos_json():
    """Returns events as a list of dicts for the web dashboard."""
    try:
        res = supabase.table("eventos").select("*").execute()
        return res.data or []
    except Exception as e:
        print("ERROR eventos json:", e)
        return []


# ───── IA ─────
def preguntar_ia(texto):
    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Eres un asistente útil. Responde siempre en el idioma del usuario."},
            {"role": "user",   "content": texto}
        ],
        max_tokens=300
    )
    return r.choices[0].message.content


# ───── PROCESAR MENSAJE (Telegram) ─────
def procesar_mensaje(chat_id, texto):
    texto = texto.strip()
    try:
        team_id, nombre = detectar_equipo(texto)
        if team_id and es_pregunta_futbol(texto):
            enviar(chat_id, consultar_partidos(team_id, nombre))
            return
        if es_pregunta_eventos(texto):
            enviar(chat_id, leer_eventos())
            return
        respuesta = preguntar_ia(texto)
        enviar(chat_id, respuesta)
    except Exception as e:
        print("ERROR:", e)
        enviar(chat_id, "⚠️ Error procesando el mensaje.")


# ───── TELEGRAM POLLING ─────
def bot():
    update_id = None
    print("✅ Bot Telegram iniciado")
    while True:
        try:
            r = requests.get(
                URL + "getUpdates",
                params={"timeout": 100, "offset": update_id},
                timeout=110
            )
            data = r.json()
            if data.get("ok"):
                for update in data["result"]:
                    update_id = update["update_id"] + 1
                    msg = update.get("message")
                    if not msg:
                        continue
                    chat_id = msg["chat"]["id"]
                    texto   = msg.get("text")
                    if texto:
                        threading.Thread(
                            target=procesar_mensaje,
                            args=(chat_id, texto),
                            daemon=True
                        ).start()
        except Exception as e:
            print("Polling error", e)
            time.sleep(5)


# ───── WEB ROUTES ─────

@app.route("/")
def index():
    """Serve the dashboard HTML."""
    return send_from_directory(".", "index.html")


@app.route("/api/eventos")
def api_eventos():
    """Return events as JSON for the dashboard."""
    eventos = leer_eventos_json()
    return jsonify({"eventos": eventos})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    Chat endpoint used by the web dashboard.
    Accepts: { "message": "user text" }
    Returns: { "reply": "assistant response" }
    """
    body  = request.get_json(silent=True) or {}
    texto = (body.get("message") or "").strip()
    if not texto:
        return jsonify({"reply": "Please write a message."}), 400

    try:
        team_id, nombre = detectar_equipo(texto)
        if team_id and es_pregunta_futbol(texto):
            reply = consultar_partidos(team_id, nombre)
        elif es_pregunta_eventos(texto):
            reply = leer_eventos()
        else:
            reply = preguntar_ia(texto)
        return jsonify({"reply": reply})
    except Exception as e:
        print("ERROR /api/chat:", e)
        return jsonify({"reply": "⚠️ Internal server error."}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


# ───── MAIN ─────
if __name__ == "__main__":
    threading.Thread(target=bot, daemon=True).start()
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
