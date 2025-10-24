import os
import requests
import logging
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext

# --- Configuración de Logging ---
# (Es bueno tenerlo para ver errores en Render)
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
    # Usamos MarkdownV2 para formato. Hay que escapar caracteres especiales.
    # Telegram es muy sensible con esto. Para este caso, usaremos HTML que es más simple.
    
    # 1. Encabezado
    message = f"📊 **Datos para la Wallet:**\n<code>{wallet_address}</code>\n\n"
    
    # 2. Posiciones Abiertas
    message += "📈 **Posiciones Abiertas**\n"
    positions = data.get('positions', [])
    if not positions:
        message += "  <i>(No hay posiciones abiertas)</i>\n"
    else:
        for pos in positions:
            # Asumimos la estructura de datos de la API
            # (ajusta 'symbol', 'size', 'isLong' si los nombres de campo son diferentes)
            symbol = pos.get('symbol', 'N/A')
            size = float(pos.get('size', 0))
            side = "LONG" if pos.get('isLong', True) else "SHORT"
            message += f"  • <b>{symbol}</b>: {size:,.2f} ({side})\n"
            
    message += "\n"
    
    # 3. Órdenes Abiertas
    message += "📄 **Órdenes Abiertas**\n"
    orders = data.get('orders', [])
    if not orders:
        message += "  <i>(No hay órdenes abiertas)</i>\n"
    else:
        for order in orders:
            # Asumimos la estructura
            symbol = order.get('symbol', 'N/A')
            size = float(order.get('size', 0))
            price = float(order.get('price', 0))
            side = "BUY" if order.get('isBuy', True) else "SELL"
            message += f"  • <b>{side} {symbol}</b>: {size:,.2f} @ ${price:,.2f}\n"

    message += "\n"

    # 4. Movimientos Recientes (ej. los últimos 5)
    message += "🔄 **Movimientos Recientes (Últimos 5)**\n"
    history = data.get('history', [])
    if not history:
        message += "  <i>(No hay movimientos recientes)</i>\n"
    else:
        for item in history[:5]: # Tomamos solo los primeros 5
            # Asumimos la estructura
            action = item.get('action', 'N/A') # Ej: 'Deposit', 'Withdraw', 'Trade'
            amount = float(item.get('amount', 0))
            symbol = item.get('symbol', '')
            message += f"  • {action} {amount:,.2f} {symbol}\n"
            
    return message

# --- Comandos de Telegram ---

def start(update: Update, context: CallbackContext):
    """Manejador del comando /start"""
    user = update.effective_user
    welcome_message = (
        f"¡Hola, {user.first_name}! 👋\n\n"
        "Soy tu bot de seguimiento de Hyperdash Wallet.\n\n"
        "**Cómo usarme:**\n"
        "Envíame el comando `/wallet` seguido de tu dirección de wallet para ver tus posiciones, órdenes y movimientos.\n\n"
        "**Ejemplo:**\n"
        "`/wallet 0xc2a30212a8ddac9e123944d6e29faddce994e5f2`\n\n"
        "Puedes cambiar de wallet en cualquier momento usando el mismo comando con una nueva dirección."
    )
    update.message.reply_text(welcome_message, parse_mode="Markdown")

def wallet(update: Update, context: CallbackContext):
    """Manejador del comando /wallet <address>"""
    chat_id = update.message.chat_id
    
    # Verificamos que el usuario envió una dirección
    if not context.args or len(context.args) == 0:
        update.message.reply_text(
            "⚠️ Formato incorrecto.\n\n"
            "Por favor, incluye la dirección de la wallet después del comando.\n"
            "Ejemplo: `/wallet 0x...`",
            parse_mode="Markdown"
        )
        return
        
    wallet_address = context.args[0]
    
    # Validar que parece una dirección (simple)
    if not (wallet_address.startswith("0x") and len(wallet_address) == 42):
        update.message.reply_text(
            "⚠️ Dirección no válida.\n"
            "Asegúrate de que sea una dirección Ethereum (0x...) de 42 caracteres."
        )
        return

    # Enviamos un mensaje de "cargando"
    context.bot.send_message(chat_id, f"🔎 Buscando datos para la wallet...\n<code>{wallet_address}</code>", parse_mode="HTML")
    
    # Obtenemos los datos
    data = get_wallet_data(wallet_address)
    
    if data:
        # Formateamos y enviamos la respuesta
        message = format_wallet_message(wallet_address, data)
        context.bot.send_message(chat_id, message, parse_mode="HTML")
    else:
        # Error al obtener datos
        context.bot.send_message(chat_id, "❌ **Error**\nNo pude encontrar datos para esa wallet o la API falló. Por favor, verifica la dirección e inténtalo de nuevo.", parse_mode="Markdown")

def handle_unknown(update: Update, context: CallbackContext):
    """Manejador para texto normal"""
    update.message.reply_text(
        "No entendí ese comando. Por favor, usa /start para ver las instrucciones."
    )

# --- Configuración del Servidor Flask (para Render) ---

# Obtenemos el Token de las variables de entorno de Render
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("No se encontró la variable de entorno BOT_TOKEN")

# Obtenemos el nombre de la app de Render (para el webhook)
# El formato es <nombre-servicio>.onrender.com
APP_NAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "hyperdash-wallet-bot.onrender.com")
if not APP_NAME:
    raise ValueError("No se pudo detectar el RENDER_EXTERNAL_HOSTNAME")

WEBHOOK_URL = f"https://{APP_NAME}/webhook"

# Inicialización del servidor Flask
app = Flask(__name__)

# Endpoint de "salud" para que Render sepa que está vivo
@app.route("/")
def index():
    return "Bot is alive!", 200

# Endpoint del Webhook
@app.route("/webhook", methods=["POST"])
def webhook():
    """Endpoint que recibe las actualizaciones de Telegram"""
    json_data = request.get_json()
    update = Update.de_json(json_data, bot)
    dispatcher.process_update(update)
    return "OK", 200

@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    """
    Un endpoint simple (que puedes visitar tú mismo) 
    para configurar el webhook después de desplegar.
    """
    try:
        success = bot.set_webhook(WEBHOOK_URL)
        if success:
            return f"Webhook configurado exitosamente en: {WEBHOOK_URL}"
        else:
            return f"Error al configurar el webhook en: {WEBHOOK_URL}"
    except Exception as e:
        return f"Error: {e}"

# --- Inicialización del Bot ---
bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, None, use_context=True)

# Añadimos los manejadores de comandos
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("wallet", wallet))

# Añadimos un manejador para texto que no sea comando
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_unknown))


if __name__ == "__main__":
    # Esta parte solo se usa para pruebas locales. 
    # Render usará Gunicorn (ver requirements.txt y comando de inicio).
    logger.info("Iniciando bot (modo local)...")
    # (En local, necesitarías polling o un túnel como ngrok)
    app.run(port=5000)
