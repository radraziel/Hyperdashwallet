import asyncio
import os
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.webhook import aiohttp_server
from apscheduler.schedulers.asyncio import AsyncIOScheduler

TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # Se configura en Render: https://tu-servicio.onrender.com/webhook

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
async def start_handler(message: types.Message):
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
async def wallet_handler(message: types.Message):
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
async def stop_handler(message: types.Message):
    user_id = message.from_user.id
    if user_id not in tracking:
        await message.answer("ℹ️ No estás rastreando ninguna wallet.")
        return

    scheduler.remove_job(tracking[user_id]['job_id'])
    del tracking[user_id]
    await message.answer("🛑 Seguimiento detenido.")

async def on_startup():
    """Configura webhook al iniciar."""
    await bot.set_webhook(WEBHOOK_URL)
    print(f"Webhook configurado en {WEBHOOK_URL}")

async def on_shutdown():
    """Limpieza al cerrar."""
    await bot.delete_webhook()
    scheduler.shutdown()

async def main():
    scheduler.start()
    await on_startup()
    # Servidor webhook
    app = aiohttp_server.create_app(dispatcher=dp, bot=bot, webhook_path="/webhook")
    port = int(os.getenv('PORT', 8080))
    await aiohttp_server.start_webhook(
        app,
        host="0.0.0.0",
        port=port,
        webhook_path="/webhook"
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        asyncio.run(on_shutdown())
