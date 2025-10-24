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
    usage_instructions_md,  # ya devuelve HTML; el nombre se quedó "md"
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(__name__)

ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def send_message(chat_id: int, text: str, parse_mode: str = "HTML"):
    """
    Enviamos SIEMPRE como HTML. Segmentamos si pasa el límite.
    """
    max_len = 3900
    blocks = [text[i:i+max_len] for i in range(0, len(text), max_len)] or [text]
    ok = True
    for block in blocks:
        resp = requests.post(f"{API_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": block,
            "parse_mode": parse_mode,          # <-- HTML
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
        return jsonify({"ok": True})

    # /start
    if text.startswith("/start"):
        send_message(chat_id, usage_instructions_md())  # HTML
        return jsonify({"ok": True})

    # /wallet <address|url>
    if text.startswith("/wallet"):
        parts = text.split(maxsplit=1)
        if len(parts) == 1:
            send_message(
                chat_id,
                "⚠️ Debes indicar una dirección. Ejemplo:\n<code>/wallet 0xabc...1234</code>"
            )
            return jsonify({"ok": True})

        address_raw = parts[1].strip()
        m = re.search(r"0x[a-fA-F0-9]{40}", address_raw)
        address = m.group(0) if m else address_raw

        if not ADDRESS_RE.match(address):
            send_message(chat_id, "❌ Dirección inválida. Usa un address EVM de 42 chars que inicie con <code>0x</code>.")
            return jsonify({"ok": True})

        try:
            positions = get_positions(address)
            orders = get_open_orders(address)
            fills = get_recent_fills(address, limit=5)

            blocks = []
            # Encabezado en HTML (antes estaba en Markdown)
            blocks.append(f"<b>Wallet:</b> <code>{address}</code>")
            blocks.append(format_positions_md(positions))
            blocks.append(format_open_orders_md(orders, limit=8))
            blocks.append(format_recent_fills_md(fills, limit=5))

            msg = "\n\n".join([b for b in blocks if b and b.strip()])
            if not msg.strip():
                msg = f"ℹ️ No se encontraron datos para <code>{address}</code>."

            send_message(chat_id, msg)  # HTML por default
        except Exception as e:
            send_message(chat_id, f"⚠️ Error consultando datos: <code>{e}</code>")
        return jsonify({"ok": True})

    # fallback
    send_message(chat_id, "Comando no reconocido.\nUsa <code>/start</code> para ver la ayuda.")
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
