import os
import re
import time
from flask import Flask, request, jsonify
import requests

from utils.hyperliquid import (
    get_positions,
    get_open_orders,
    get_recent_fills,
)
from utils.formatters import (
    format_positions_md,
    format_open_orders_md,
    format_recent_fills_md,
    usage_instructions_md,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # NO guardes el token en el repo. Configúralo en Render.
API_URL = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(__name__)

ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def send_message(chat_id: int, text: str, parse_mode: str = "HTML"):
    # Telegram limita mensajes ~4096 chars: segmentamos si es necesario
    max_len = 3900
    blocks = [text[i:i+max_len] for i in range(0, len(text), max_len)] or [text]
    ok = True
    for block in blocks:
        resp = requests.post(f"{API_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": block,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }, timeout=20)
        ok = ok and resp.ok
    return ok


@app.get("/health")
def health():
    return jsonify({"ok": True, "time": int(time.time())})


@app.post("/webhook")
def webhook():
    if not TOKEN:
        return jsonify({"ok": False, "error": "Missing TELEGRAM_BOT_TOKEN"}), 500

    update = request.get_json(silent=True) or {}
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    if not chat_id or not text:
        return jsonify({"ok": True})  # ignoramos updates no relevantes

    # Comandos
    if text.startswith("/start"):
        send_message(chat_id, usage_instructions_md())
        return jsonify({"ok": True})

    if text.startswith("/wallet"):
        parts = text.split(maxsplit=1)
        if len(parts) == 1:
            send_message(chat_id, "⚠️ Debes indicar una dirección. Ejemplo:\n`/wallet 0xabc...1234`", "Markdown")
            return jsonify({"ok": True})

        address = parts[1].strip()
        # Permite que el usuario pegue URL completa de HyperDash; extraemos el 0x...
        m = re.search(r"0x[a-fA-F0-9]{40}", address)
        address = m.group(0) if m else address

        if not ADDRESS_RE.match(address):
            send_message(chat_id, "❌ Dirección inválida. Asegúrate de usar un address EVM de 42 chars que inicie con `0x`.", "Markdown")
            return jsonify({"ok": True})

        # Llamadas a Hyperliquid
        try:
            positions = get_positions(address)
            orders = get_open_orders(address)
            fills = get_recent_fills(address, limit=5)

            # Armamos el reporte
            blocks = []
            blocks.append(f"🧾 *Wallet:* `{address}`")
            blocks.append(format_positions_md(positions))
            blocks.append(format_open_orders_md(orders, limit=8))
            blocks.append(format_recent_fills_md(fills, limit=5))
            msg = "\n\n".join([b for b in blocks if b])
            if not msg.strip():
                msg = f"ℹ️ No se encontraron datos para `{address}`."

            send_message(chat_id, msg, parse_mode="Markdown")
        except Exception as e:
            send_message(chat_id, f"⚠️ Error consultando datos: {e}")
        return jsonify({"ok": True})

    # Respuesta por defecto (hint)
    send_message(chat_id, "Comando no reconocido.\nUsa /start para ver la ayuda.")
    return jsonify({"ok": True})


if __name__ == "__main__":
    # Útil para pruebas locales
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
