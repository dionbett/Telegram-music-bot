import os
import logging
from datetime import datetime
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

# === CONFIG ===
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://your-render-service.onrender.com/webhook
PORT = int(os.getenv("PORT", "8080"))

user_search_results = {}

# === LOGGING ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

def log_request(user_id, username, action, query=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if query:
        print(f"[{timestamp}] User {user_id} (@{username}) {action}: '{query}'")
    else:
        print(f"[{timestamp}] User {user_id} (@{username}) {action}")

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
            [InlineKeyboardButton(f"{i+1}. {entry.get('title', 'Unknown Title')[:40]}",
                                  callback_data=f"{user.id}:{i}")]
            for i, entry in enumerate(info["entries"])
        ]
        await update.message.reply_text(
            "🎶 I found these results, pick one:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logging.error(f"Error during search for user {user.id}: {str(e)}")
        await update.message.reply_text("❌ Error while searching.")

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
        logging.info(f"✅ Sent '{video_title}' to {user.id}")

    except Exception as e:
        logging.error(f"Error downloading for {user.id}: {str(e)}")
        await query.message.reply_text("❌ Error downloading the song.")


# === MAIN ===
async def handle_webhook(request):
    """Aiohttp webhook handler for Telegram"""
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return web.Response(text="OK")

if not TOKEN:
    raise ValueError("⚠️ BOT_TOKEN not set!")

application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_song))
application.add_handler(CallbackQueryHandler(button_handler))

# === Aiohttp Web Server ===
async def main():
    app = web.Application()
    app.router.add_post("/webhook", handle_webhook)

    # Start webhook server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    # Set webhook URL
    webhook_url = WEBHOOK_URL
    if not webhook_url:
        raise ValueError("⚠️ WEBHOOK_URL environment variable missing!")
    await application.bot.set_webhook(url=f"{webhook_url}/webhook")
    logging.info(f"✅ Webhook set: {webhook_url}/webhook")

    await application.start()
    await application.updater.start_polling()  # Safe fallback if webhook fails

    await application.wait_until_shutdown()
    await runner.cleanup()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())