import os
import logging
import asyncio
from aiohttp import web
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import yt_dlp

# === CONFIG ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
APP_URL = f"https://{os.getenv('RENDER_EXTERNAL_URL', 'your-app-name.onrender.com')}/webhook"

if not BOT_TOKEN:
    raise ValueError("⚠️ BOT_TOKEN not set!")

# === LOGGING ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_search_results = {}

# === COMMANDS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎵 Send me a song name and I'll find it for you!")

async def search_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    await update.message.reply_text(f"🔎 Searching for: {query}...")

    opts = {"quiet": True, "noplaylist": True, "extract_flat": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)
        if "entries" not in info or not info["entries"]:
            await update.message.reply_text("❌ No results found.")
            return
        results = info["entries"]
        text = "\n".join([f"{i+1}. {v['title']}" for i, v in enumerate(results)])
        await update.message.reply_text("🎶 Results:\n" + text)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {e}")

# === WEBHOOK HANDLER ===
async def webhook_handler(request):
    """Handle incoming webhook updates."""
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return web.Response(status=200)

# === MAIN APP ===
async def main():
    global application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_song))

    # --- Webhook setup ---
    await application.initialize()
    await application.start()

    await application.bot.set_webhook(APP_URL)
    logger.info(f"✅ Webhook set: {APP_URL}")

    # aiohttp web server
    app = web.Application()
    app.router.add_post("/webhook", webhook_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    logger.info(f"🚀 Server running on port {PORT}")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())