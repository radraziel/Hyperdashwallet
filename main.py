import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
from datetime import datetime

TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # e.g., https://hyperdash-wallet-bot.onrender.com/webhook
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.getenv('PORT', 8080))

bot = Bot(token=TOKEN)
dp = Dispatcher()

def get_webdriver():
    """Configura un driver headless para Selenium."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Sin GUI
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=chrome_options)

async def fetch_wallet_data(address: str) -> str:
    """Scraping de datos de HyperDash usando Selenium."""
    url = f"https://hyperdash.info/trader/{address}"
    try:
        # Inicia el driver
        driver = get_webdriver()
        driver.get(url)

        # Espera a que los datos se carguen (ajusta el selector según el HTML real)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "asset-positions"))
        )

        # Obtiene el HTML renderizado
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Parsing de posiciones abiertas
        positions = []
        pos_section = soup.find('div', {'class': 'asset-positions'})  # Ajusta según HTML
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

        driver.quit()

        message = (
            f"📊 **Datos para {address}** ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n"
            f"**Posiciones abiertas:**\n" + "\n".join(positions) + "\n\n"
            f"{orders_text}\n\n"
            f"**Movimientos recientes:**\n" + "\n".join(recent[:3])
        )
        return message if positions or recent else "No se encontraron datos. Verifica la dirección."

    except Exception as e:
        if 'driver' in locals():
            driver.quit()
        return f"❌ Error al obtener datos: {str(e)}"

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
