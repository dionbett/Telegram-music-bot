import os
import logging
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import yt_dlp
import asyncio
import nest_asyncio
import requests

# === CONFIG ===
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = "https://telegram-music-bot-13-oavi.onrender.com"  # your Render URL

# === FLASK APP ===
app = Flask(__name__)

# === LOGGING ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === SEARCH FUNCTION ===
async def search_song(query):
    try:
        ydl_opts = {"quiet": True, "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query} site:music.youtube.com", download=False)
            return info["entries"]
    except Exception as e:
        logger.error(f"Search error: {e}")
        return None

# === DOWNLOAD FUNCTION ===
def download_audio(url):
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "%(title)s.%(ext)s",
        "quiet": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".mp3"
            return filename, info.get("title", "Unknown Title")
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None, None

# === COMMAND HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎶 Send me a song name and I’ll fetch it from YouTube Music!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    results = await search_song(query)

    if not results:
        await update.message.reply_text("❌ No results found. Try another song.")
        return

    buttons = [[InlineKeyboardButton(f"{v['title']}", callback_data=f"song|{v['id']}")] for v in results]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("🎧 Choose your song:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("song|"):
        video_id = query.data.split("|")[1]
        video_url = f"https://music.youtube.com/watch?v={video_id}"

        await query.edit_message_text("⬇️ Downloading your song, please wait...")
        filename, title = download_audio(video_url)

        if filename:
            await query.message.reply_audio(audio=open(filename, "rb"), title=title)
            os.remove(filename)
        else:
            await query.edit_message_text("❌ Error downloading the song.")

# === TELEGRAM APP ===
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(CallbackQueryHandler(button_handler))

# === INITIALIZE APP FOR WEBHOOK ===
async def init_app():
    await application.initialize()
    await application.start()
    await application.bot.initialize()

# === FLASK WEBHOOK ===
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.create_task(application.process_update(update))  # safe async processing
    return "OK", 200

@app.route("/")
def index():
    return "🎵 Telegram Music Bot is live!", 200

# === MAIN ===
if __name__ == "__main__":
    # allow nested event loops (Flask + asyncio)
    nest_asyncio.apply()

    # initialize the Application
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_app())

    # set webhook
    resp = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={WEBHOOK_URL}/{BOT_TOKEN}")
    if resp.status_code == 200:
        logger.info("✅ Webhook set successfully")
    else:
        logger.error(f"❌ Webhook error: {resp.text}")

    # run Flask
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))