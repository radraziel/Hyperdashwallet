import os
import requests
import logging
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters
)

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
            # Usamos 'with' para asegurar que la sesión se cierre
            with requests.Session() as s:
                response = s.get(url, timeout=10)
                response.raise_for_status()  # Lanza un error si la petición falla
                data[key] = response.json()
            
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al contactar la API de Hyperdash: {e}")
        return None

def format_wallet_message(wallet_address, data):
    """
    Toma los datos de la API y los formatea en un mensaje de Telegram.
    """
    # Usamos HTML para formato, es más robusto que MarkdownV2.
    
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
            # Formateamos el tamaño con comas para miles
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

# --- Comandos de Telegram (ahora son 'async') ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador del comando /start"""
    user = update.effective_user
    welcome_message = (
        f"¡Hola, {user.first_name}! 👋\n\n"
        "Soy tu bot de seguimiento de Hyperdash Wallet.\n\n"
        "<b>Cómo usarme:</b>\n"
        "Envíame el comando <code>/wallet</code> seguido de tu dirección de wallet para ver tus posiciones, órdenes y movimientos.\n\n"
        "<b>Ejemplo:</b>\n"
        "<code>/wallet 0xc2a30212a8ddac9e123944d6e29faddce994e5f2</code>\n\n"
        "Puedes cambiar de wallet en cualquier momento usando el mismo comando con una nueva dirección."
    )
    # Todos los envíos de mensajes ahora usan 'await'
    await update.message.reply_text(welcome_message, parse_mode="HTML")

async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador del comando /wallet <address>"""
    chat_id = update.message.chat_id
    
    if not context.args or len(context.args) == 0:
        await update.message.reply_text(
            "⚠️ <b>Formato incorrecto.</b>\n\n"
            "Por favor, incluye la dirección de la wallet después del comando.\n"
            "Ejemplo: <code>/wallet 0x...</code>",
            parse_mode="HTML"
        )
        return
        
    wallet_address = context.args[0]
    
    if not (wallet_address.startswith("0x") and len(wallet_address) == 42):
        await update.message.reply_text(
            "⚠️ <b>Dirección no válida.</b>\n"
            "Asegúrate de que sea una dirección Ethereum (0x...) de 42 caracteres."
            , parse_mode="HTML"
        )
        return

    await context.bot.send_message(chat_id, f"🔎 Buscando datos para la wallet...\n<code>{wallet_address}</code>", parse_mode="HTML")
    
    # La obtención de datos (requests) es síncrona,
    # la ejecutamos en un hilo separado para no bloquear el bot
    data = await context.application.create_task(get_wallet_data(wallet_address))
    
    if data:
        message = format_wallet_message(wallet_address, data)
        await context.bot.send_message(chat_id, message, parse_mode="HTML")
    else:
        await context.bot.send_message(chat_id, "❌ <b>Error</b>\nNo pude encontrar datos para esa wallet o la API falló. Por favor, verifica la dirección e inténtalo de nuevo.", parse_mode="HTML")

async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador para texto normal"""
    await update.message.reply_text(
        "No entendí ese comando. Por favor, usa /start para ver las instrucciones."
    )

# --- Inicialización del Bot (v20+) y Variables de Entorno ---
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("No se encontró la variable de entorno BOT_TOKEN")

APP_NAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if not APP_NAME:
    raise ValueError("No se pudo detectar el RENDER_EXTERNAL_HOSTNAME")

WEBHOOK_URL = f"https://{APP_NAME}/webhook"

# Creamos la 'Application' (reemplaza a Bot y Dispatcher)
application = ApplicationBuilder().token(TOKEN).build()

# Añadimos los manejadores
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("wallet", wallet))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown))


# --- INICIO DE LA CORRECCIÓN ---
# Inicializamos la app (ej. descarga info del bot) ANTES de que Flask la use.
# Esto evita el error 'Application was not initialized'.
logger.info("Inicializando la aplicación del bot...")
asyncio.run(application.initialize())
logger.info("Aplicación inicializada exitosamente.")
# --- FIN DE LA CORRECCIÓN ---


# --- Configuración del Servidor Flask (para Render) ---

app = Flask(__name__) # Este objeto 'app' es el que Gunicorn usará

@app.route("/")
def index():
    return "Bot is alive!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    """Endpoint que recibe las actualizaciones de Telegram"""
    json_data = request.get_json()
    update = Update.de_json(json_data, application.bot)
    
    # Usamos asyncio.run() para ejecutar la función async 'process_update'
    # desde nuestro entorno síncrono de Flask.
    try:
        asyncio.run(application.process_update(update))
    except Exception as e:
        logger.error(f"Error al procesar update: {e}")
        
    return "OK", 200

@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    """
    Un endpoint simple (que puedes visitar tú mismo) 
    para configurar el webhook después de desplegar.
    """
    # Creamos una función async interna para poder usar 'await'
    async def _set_hook():
        try:
            success = await application.bot.set_webhook(WEBHOOK_URL)
            if success:
                return f"Webhook configurado exitosamente en: {WEBHOOK_URL}"
            else:
                return f"Error al configurar el webhook en: {WEBHOOK_URL}"
        except Exception as e:
            return f"Error: {e}"
            
    # La ejecutamos con asyncio.run()
    return asyncio.run(_set_hook())

# Esta parte solo se usa para pruebas locales (ej. 'python app.py')
# Render NO la ejecutará (usa Gunicorn)
if __name__ == "__main__":
    logger.info("Iniciando bot localmente (modo polling)...")
    # Para pruebas locales, es más fácil usar polling que webhooks
    application.run_polling()
