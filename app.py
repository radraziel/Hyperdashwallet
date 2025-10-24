import os
import requests
import logging
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext

# --- Configuración de Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Constantes de la API ---
API_BASE_URL = "https://api.hyperdash.info/v1/trader"

# --- Funciones de Ayuda (Lógica del Bot) ---

def get_wallet_data(wallet_address):
    """
    Obtiene los datos de la API de Hyperdash para una wallet específica.
    Devuelve un diccionario con 'positions', 'orders' y 'history', o None si falla.
    """
    try:
        endpoints = {
            "positions": f"{API_BASE_URL}/positions?address={wallet_address}",
            "orders": f"{API_BASE_URL}/orders?address={wallet_address}",
            "history": f"{API_BASE_URL}/history?address={wallet_address}"
        }
        
        data = {}
        for key, url in endpoints.items():
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # Lanza un error si la petición falla (ej. 404, 500)
            data[key] = response.json()
            
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al contactar la API de Hyperdash: {e}")
        return None

def format_wallet_message(wallet_address, data):
    """
    Toma los datos de la API y los formatea en un mensaje de Telegram.
    """
    # Usamos HTML para formato
    
    # 1. Encabezado
    message = f"📊 <b>Datos para la Wallet:</b>\n<code>{wallet_address}</code>\n\n"
    
    # 2. Posiciones Abiertas
    message += "📈 <b>Posiciones Abiertas</b>\n"
    positions = data.get('positions', [])
    if not positions:
        message += "  <i>(No hay posiciones abiertas)</i>\n"
    else:
        for pos in positions:
            symbol = pos.get('symbol', 'N/A')
            size = float(pos.get('size', 0))
            side = "LONG" if pos.get('isLong', True) else "SHORT"
            message += f"  • <b>{symbol}</b>: {size:,.2f} ({side})\n"
            
    message += "\n"
    
    # 3. Órdenes Abiertas
    message += "📄 <b>Órdenes Abiertas</b>\n"
    orders = data.get('orders', [])
    if not orders:
        message += "  <i>(No hay órdenes abiertas)</i>\n"
    else:
        for order in orders:
            symbol = order.get('symbol', 'N/A')
            size = float(order.get('size', 0))
            price = float(order.get('price', 0))
            side = "BUY" if order.get('isBuy', True) else "SELL"
            message += f"  • <b>{side} {symbol}</b>: {size:,.2f} @ ${price:,.2f}\n"

    message += "\n"

    # 4. Movimientos Recientes (ej. los últimos 5)
    message += "🔄 <b>Movimientos Recientes (Últimos 5)</b>\n"
    history = data.get('history', [])
    if not history:
        message += "  <i>(No hay movimientos recientes)</i>\n"
    else:
        for item in history[:5]: # Tomamos solo los primeros 5
            action = item.get('action', 'N/A') # Ej: 'Deposit', 'Withdraw', 'Trade'
            amount = float(item.get('amount', 0))
            symbol = item.get('symbol', '')
            message += f"  • {action} {amount:,.2f} {symbol}\n"
            
    return message

# --- Comandos de Telegram (Síncronos, V13) ---

def start(update: Update, context: CallbackContext):
    """Manejador del comando /start"""
    user = update.effective_user
    welcome_message = (
        f"¡Hola, {user.first_name}! 👋\n\n"
        "Soy tu bot de seguimiento de Hyperdash Wallet.\n\n"
        "<b>Cómo usarme:</b>\n"
        "Envíame el comando <code>/wallet</code> seguido de tu dirección de wallet.\n\n"
        "<b>Ejemplo:</b>\n"
        "<code>/wallet 0xc2a30212a8ddac9e123944d6e29faddce994e5f2</code>"
    )
    update.message.reply_text(welcome_message, parse_mode="HTML")

def wallet(update: Update, context: CallbackContext):
    """Manejador del comando /wallet <address>"""
    chat_id = update.message.chat_id
    
    if not context.args or len(context.args) == 0:
        update.message.reply_text(
            "⚠️ <b>Formato incorrecto.</b>\n"
            "Ejemplo: <code>/wallet 0x...</code>",
            parse_mode="HTML"
        )
        return
        
    wallet_address = context.args[0]
    
    if not (wallet_address.startswith("0x") and len(wallet_address) == 42):
        update.message.reply_text(
            "⚠️ <b>Dirección no válida.</b>\n"
            "Asegúrate de que sea una dirección Ethereum (0x...) de 42 caracteres.",
            parse_mode="HTML"
        )
        return

    context.bot.send_message(chat_id, f"🔎 Buscando datos para la wallet...\n<code>{wallet_address}</code>", parse_mode="HTML")
    
    data = get_wallet_data(wallet_address)
    
    if data:
        message = format_wallet_message(wallet_address, data)
        context.bot.send_message(chat_id, message, parse_mode="HTML")
    else:
        context.bot.send_message(chat_id, "❌ <b>Error</b>\nNo pude encontrar datos para esa wallet o la API falló.", parse_mode="HTML")

def handle_unknown(update: Update, context: CallbackContext):
    """Manejador para texto normal"""
    update.message.reply_text(
        "No entendí ese comando. Por favor, usa /start para ver las instrucciones."
    )

# --- Configuración del Servidor Flask (para Render) ---

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("No se encontró la variable de entorno BOT_TOKEN")

APP_NAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "hyperdash-wallet-bot.onrender.com")
WEBHOOK_URL = f"https://{APP_NAME}/webhook"

# --- Inicialización del Bot (V13) ---
bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, None, use_context=True, workers=4)

# Añadimos los manejadores
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("wallet", wallet))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_unknown))


# --- Rutas de Flask ---
app = Flask(__name__)

@app.route("/")
def index():
    return "Bot is alive!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    """Endpoint que recibe las actualizaciones de Telegram"""
    json_data = request.get_json()
    update = Update.de_json(json_data, bot)
    dispatcher.process_update(update) # Esto es síncrono y seguro
    return "OK", 200

@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    """Configura el webhook al visitar esta URL"""
    try:
        success = bot.set_webhook(WEBHOOK_URL)
        if success:
            return f"Webhook configurado exitosamente en: {WEBHOOK_URL}"
        else:
            return f"Error al configurar el webhook en: {WEBHOOK_URL}"
    except Exception as e:
        return f"Error: {e}"
