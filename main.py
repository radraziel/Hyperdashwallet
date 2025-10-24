import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # e.g., https://hyperdash-wallet-bot.onrender.com/webhook
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.getenv('PORT', 8080))

bot = Bot(token=TOKEN)
dp = Dispatcher()

async def fetch_wallet_data(address: str) -> str:
    """Scraping de datos de HyperDash con manejo avanzado de bloqueos."""
    url = f"https://hyperdash.info/trader/{address}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://hyperdash.info/",
    }
    try:
        # Intento 1: Solicitud directa con headers
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Intento 2: Si falla, simula un navegador más
        if not soup.find('div', {'class': 'asset-positions'}):  # Ajusta selector
            headers["User-Agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15"
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

        # Parsing de posiciones abiertas
        positions = []
        pos_section = soup.find('div', {'class': 'asset-positions'})  # Ajusta según HTML real
        if pos_section:
            rows = pos_section.find_all('tr')
            for row in rows[1:]:
                cols = row.find_all('td')
                if len(cols) >= 3:
                    asset = cols[0].get_text(strip=True)
                    pos_type = cols[1].get_text(strip=True)
                    amount = cols[2].get_text(strip=True)
                    positions.append(f"{asset}: {pos_type} {amount}")

        # Órdenes abiertas
        orders_text = "Órdenes abiertas: 0"
        orders_section = soup.find('div', {'class': 'open-orders'})
        if orders_section:
            count_elem = orders_section.find('span', {'class': 'order-count'})
            count = count_elem.get_text(strip=True) if count_elem else "0"
            orders_text = f"Órdenes abiertas: {count}"

        # Movimientos recientes
        recent = []
        fills_section = soup.find('div', {'class': 'recent-fills'})
        if fills_section:
            items = fills_section.find_all('div', {'class': 'fill-item'}, limit=5)
            for item in items:
                recent.append(item.get_text(strip=True))

        message = (
            f"📊 **Datos para {address}** ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n"
            f"**Posiciones abiertas:**\n" + "\n".join(positions) + "\n\n"
            f"{orders_text}\n\n"
            f"**Movimientos recientes:**\n" + "\n".join(recent[:3])
        )
        return message if positions or recent else "No se encontraron datos. Verifica la dirección."

    except requests.exceptions.RequestException as e:
        return f"❌ Error al obtener datos: {str(e)} (Código: {getattr(e.response, 'status_code', 'N/A')})"

@dp.message(Command("start"))
async def start_handler(message: Message):
    instructions = (
        "¡Bienvenido al Bot Hyperdash Wallet! 👋\n\n"
        "Este bot te permite rastrear wallets en HyperDash.\n\n"
        "**Comandos:**\n"
        "/wallet <dirección> - Obtiene datos actuales (ej: /wallet 0xc2a30212a8ddac9e123944d6e29faddce994e5f2)\n"
        "/stopwallet - No aplica sin seguimiento automático\n\n"
        "Solicita datos manualmente cuando lo necesites."
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

    data = await fetch_wallet_data(address)
    await message.answer(data, parse_mode='Markdown')

@dp.message(Command("stopwallet"))
async def stop_handler(message: Message):
    await message.answer("ℹ️ El seguimiento automático no está habilitado. Usa /wallet para consultas manuales.")

async def on_startup(bot: Bot) -> None:
    """Configura webhook al iniciar."""
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook configurado en {WEBHOOK_URL}")

async def on_shutdown(bot: Bot) -> None:
    """Limpieza al cerrar."""
    await bot.delete_webhook()
    logging.info("Webhook eliminado.")

def main():
    logging.basicConfig(level=logging.INFO)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logging.info("Aplicación detenida.")
