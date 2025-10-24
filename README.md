# Hyperdash Wallet Telegram Bot

Bot para rastrear wallets en HyperDash.info. Envía actualizaciones cada 10 min.

## Configuración Local
1. Clona el repo.
2. `pip install -r requirements.txt`
3. Crea `.env` con `BOT_TOKEN=tu_token`
4. `python main.py` (usa polling local: modifica para `dp.start_polling(bot)`)

## Deploy en Render
Ver instrucciones abajo.

## Ajustes
- Scraping en `fetch_wallet_data`: Inspecciona HTML de HyperDash y actualiza selectores.
