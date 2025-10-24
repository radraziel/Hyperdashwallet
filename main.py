import asyncio
import logging
import os
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from apscheduler.schedulers.asyncio import AsyncIOScheduler

TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # e.g., https://hyperdash-wallet-bot.onrender.com/webhook
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.getenv('PORT', 8080))

bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# Almacenamiento en memoria (user_id: {'address': str, 'job_id': str})
tracking = {}

async def fetch_wallet_data(address: str) -> str:
    """Scraping de datos de HyperDash. AJUSTA LOS SELECTORES BASADO EN EL HTML REAL."""
    url = f"https://hyperdash.info/trader/{address}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Parsing de posiciones abiertas (ajusta selectores)
        positions = []
        pos_section = soup.find('div', {'class': 'asset-positions'})  # Ejemplo: busca por clase o id
        if pos_section:
            rows = pos_section.find_all('tr')  # Asume tabla
            for row in rows[1:]:  # Salta header
                cols = row.find_all('td')
                if len(cols) >= 3:
                    asset = cols[0].get_text(strip=True)
                    pos_type = cols[1].get_text(strip=True)  # Long/Short
                    amount = cols[2].get_text(strip=True)
                    positions.append(f"{asset}: {pos_type} {amount}")

        # Órdenes abiertas (ajusta)
        orders_text = "Órdenes abiertas: 0"  # Placeholder
        orders_section = soup.find('div', {'class': 'open-orders'})
        if orders_section:
            count_elem = orders_section.find('span', {'class': 'order-count'})  # Ejemplo
            count = count_elem.get_text(strip=True) if count_elem else "0"
            orders_text = f"Órdenes abiertas: {count}"

        # Movimientos recientes (fills/trades, últimos 5)
        recent = []
        fills_section = soup.find('div', {'class': 'recent-fills'})
        if fills_section:
            items = fills_section.find_all('div', {'class': 'fill-item'}, limit=5)  # Ejemplo
            for item in items:
                recent.append(item.get_text(strip=True))

        message = (
            f"📊 **Actualización para {address}** ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n"
            f"**Posiciones abiertas:**\n" + "\n".join(positions) + "\n\n"
            f"{orders_text}\n\n"
            f"**Movimientos recientes:**\n" + "\n".join(recent[:3])  # Limita a 3 para Telegram
        )
        return message if positions or recent else "No se encontraron datos. Verifica la dirección."

    except Exception as e:
        return f"❌ Error al obtener datos: {str(e)}"

async def periodic_update(user_id: int):
    """Función para envío periódico."""
    if user_id not in tracking:
        return
    address = tracking[user_id]['address']
    data = await fetch_wallet_data(address)
    try:
        await bot.send_message(user_id, data, parse_mode='Markdown')
    except Exception:
        # Usuario bloqueó el bot o error
        pass

@dp.message(Command("start"))
async def start_handler(message: Message):
    instructions = (
        "¡Bienvenido al Bot Hyperdash Wallet! 👋\n\n"
        "Este bot te permite rastrear wallets en HyperDash.\n\n"
        "**Comandos:**\n"
        "/wallet <dirección> - Inicia el seguimiento (ej: /wallet 0xc2a30212a8ddac9e123944d6e29faddce994e5f2)\n"
        "/stopwallet - Detiene el seguimiento\n\n"
        "Se enviarán actualizaciones cada 10 minutos automáticamente."
    )
    await message.answer(instructions)

@dp.message(Command("wallet"))
async def wallet_handler(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Proporciona una dirección: /wallet <dirección>")
        return

    address = parts[1].strip()
    if not re.match(r'^0x[a-fA-F0-9]{40}$', address):
        await message.answer("❌ Dirección inválida (debe ser Ethereum 0x... 40 chars).")
        return

    user_id = message.from_user.id
    job_id = f"track_{user_id}"

    # Detener job anterior si existe
    if user_id in tracking:
        scheduler.remove_job(tracking[user_id]['job_id'])

    # Agregar nuevo job
    scheduler.add_job(
        periodic_update,
        'interval',
        minutes=10,
        id=job_id,
        args=(user_id,),
        replace_existing=True
    )
    tracking[user_id] = {'address': address, 'job_id': job_id}

    # Envío inicial
    await message.answer(f"✅ Iniciado seguimiento de {address}.\nPrimer update en 10 min.")
    await periodic_update(user_id)  # Envío inmediato

@dp.message(Command("stopwallet"))
async def stop_handler(message: Message):
    user_id = message.from_user.id
    if user_id not in tracking:
        await message.answer("ℹ️ No estás rastreando ninguna wallet.")
        return

    scheduler.remove_job(tracking[user_id]['job_id'])
    del tracking[user_id]
    await message.answer("🛑 Seguimiento detenido.")

async def on_startup(bot: Bot) -> None:
    """Configura webhook al iniciar."""
    await bot.set_webhook(WEBHOOK_URL)
    scheduler.start()
    logging.info(f"Webhook configurado en {WEBHOOK_URL}")

async def on_shutdown(bot: Bot) -> None:
    """Limpieza al cerrar."""
    await bot.delete_webhook()
    scheduler.shutdown()
    logging.info("Webhook eliminado y scheduler detenido.")

def main():
    # Configura logging
    logging.basicConfig(level=logging.INFO)

    # Registra hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Crea la app aiohttp
    app = web.Application()

    # Configura el handler de webhook
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_handler.register(app, path=WEBHOOK_PATH)

    # Monta hooks del dispatcher en la app
    setup_application(app, dp, bot=bot)

    # Inicia el servidor
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logging.info("Aplicación detenida.")
