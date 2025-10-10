import os
import logging
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import yt_dlp

# === CONFIG ===
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
WEBHOOK_URL = "https://telegram-music-bot-13-oavi.onrender.com"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Search songs on YouTube ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎵 Send me the name of a song, and I’ll fetch options for you!")

async def search_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    await update.message.reply_text(f"🔍 Searching for '{query}'...")

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,
        "default_search": "ytsearch5",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            results = info["entries"]

        # Build buttons for user to choose
        keyboard = [
            [InlineKeyboardButton(f"{v['title']} - {v.get('uploader', 'Unknown')}", callback_data=v["url"])]
            for v in results
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("🎶 Choose a song:", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Search error: {e}")
        await update.message.reply_text("❌ Could not find songs, try again later.")

# --- Handle selection and download ---
async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    url = query.data

    await query.edit_message_text("⏳ Downloading audio... please wait")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(tempfile.gettempdir(), "%(title)s.%(ext)s"),
        "quiet": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info).replace(".webm", ".mp3").replace(".m4a", ".mp3")

        with open(filename, "rb") as audio_file:
            await query.message.reply_audio(audio=audio_file, title=info.get("title", "Unknown"))

        os.remove(filename)

    except Exception as e:
        logger.error(f"Download error: {e}")
        await query.edit_message_text("❌ Error downloading the song.")

# === MAIN ===
app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_song))
app.add_handler(CallbackQueryHandler(download_audio))

if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        url_path=BOT_TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
    )