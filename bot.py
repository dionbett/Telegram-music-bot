import os
import logging
import asyncio
from aiohttp import web
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import yt_dlp
from datetime import datetime

# === CONFIG ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))

# ✅ Hardcoded Render URL (your public app URL)
APP_URL = "https://telegram-music-bot-13-oavi.onrender.com/webhook"

if not BOT_TOKEN:
    raise ValueError("⚠️ BOT_TOKEN not set!")

# === LOGGING ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === TEMP STORAGE ===
user_search_results = {}

# === UTILITY ===
def log_request(user_id, username, action, query=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if query:
        logger.info(f"[{timestamp}] User {user_id} (@{username}) {action}: '{query}'")
    else:
        logger.info(f"[{timestamp}] User {user_id} (@{username}) {action}")

# === HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_request(user.id, user.username, "started the bot")
    await update.message.reply_text("🎵 Send me a song name and I'll find it for you!")

async def search_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    query = update.message.text.strip()
    log_request(user.id, user.username, "searched for", query)

    await update.message.reply_text(f"🔎 Searching for: {query}...")

    search_opts = {"quiet": True, "noplaylist": True, "extract_flat": True}

    try:
        with yt_dlp.YoutubeDL(search_opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)

        if "entries" not in info or not info["entries"]:
            await update.message.reply_text("❌ No results found.")
            return

        user_search_results[user.id] = info["entries"]

        keyboard = [
            [InlineKeyboardButton(f"{i+1}. {entry.get('title','Unknown')[:40]}",
                                  callback_data=f"{user.id}:{i}")]
            for i, entry in enumerate(info["entries"])
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🎶 I found these results, pick one:", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error during search for {user.id}: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    data = query.data.split(":")
    if len(data) != 2 or int(data[0]) != user.id:
        return

    index = int(data[1])
    results = user_search_results.get(user.id)
    if not results or index < 0 or index >= len(results):
        await query.edit_message_text("❌ Invalid choice.")
        return

    video = results[index]
    video_url = f"https://www.youtube.com/watch?v={video['id']}"
    video_title = video.get("title", "Unknown Title")

    await query.edit_message_text(f"⬇️ Downloading: {video_title}")

    ydl_opts = {"format": "bestaudio[ext=m4a]/bestaudio/best", "outtmpl": "%(title)s.%(ext)s", "quiet": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            file_name = ydl.prepare_filename(info)

        with open(file_name, "rb") as audio:
            await query.message.reply_audio(audio=audio, title=info.get("title", "Audio"))

        os.remove(file_name)
        user_search_results.pop(user.id, None)
        logger.info(f"✅ Sent '{video_title}' to {user.id}")

    except Exception as e:
        logger.error(f"Error downloading for {user.id}: {e}")
        await query.message.reply_text("❌ Error downloading the song.")

# === WEBHOOK HANDLER ===
async def webhook_handler(request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return web.Response(status=200)

# === HEALTH CHECK ===
async def health_check(request):
    return web.Response(text="OK", status=200)

# === MAIN FUNCTION ===
async def main():
    global application
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_song))
    application.add_handler(CallbackQueryHandler(button_handler))

    # Initialize bot properly
    await application.initialize()
    await application.start()

    # Set webhook
    await application.bot.set_webhook(APP_URL)
    logger.info(f"✅ Webhook set: {APP_URL}")

    # Start aiohttp server
    app = web.Application()
    app.router.add_post("/webhook", webhook_handler)
    app.router.add_get("/", health_check)  # optional health route

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    logger.info(f"🚀 Server running on port {PORT}")
    await asyncio.Event().wait()  # keep running

if __name__ == "__main__":
    asyncio.run(main())