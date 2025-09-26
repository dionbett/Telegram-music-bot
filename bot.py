from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import yt_dlp
import os
from datetime import datetime

TOKEN = "8420395786:AAGpnMz3ExBad_kQIHv9JB44_vK9zs7kW"

# Store user search results temporarily
user_search_results = {}

def log_request(user_id, username, action, query=None):
    """Simple logging function"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if query:
        print(f"[{timestamp}] User {user_id} (@{username}) {action}: '{query}'")
    else:
        print(f"[{timestamp}] User {user_id} (@{username}) {action}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_request(user.id, user.username, "started the bot")
    await update.message.reply_text("🎵 Send me a song name and I'll find it for you!")

async def search_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    query = update.message.text.strip()

    log_request(user.id, user.username, "searched for", query)
    await update.message.reply_text(f"🔎 Searching for: {query}...")

    search_opts = {
        "quiet": True,
        "noplaylist": True,
        "extract_flat": True,  # makes search much faster
    }

    try:
        with yt_dlp.YoutubeDL(search_opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)

        if "entries" not in info or not info["entries"]:
            await update.message.reply_text("❌ No results found.")
            return

        # Save results for the user
        user_search_results[user.id] = info["entries"]

        # Build buttons
        keyboard = []
        for i, entry in enumerate(info["entries"], start=1):
            title = entry.get("title", "Unknown Title")
            keyboard.append([InlineKeyboardButton(f"{i}. {title[:40]}", callback_data=f"{user.id}:{i-1}")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("🎶 I found these results, pick one:", reply_markup=reply_markup)

    except Exception as e:
        print(f"❌ Error during search for user {user.id}: {str(e)}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Acknowledge button press

    user = update.effective_user
    data = query.data.split(":")

    if len(data) != 2 or int(data[0]) != user.id:
        return  # Ignore invalid or other users' presses

    index = int(data[1])
    results = user_search_results.get(user.id)

    if not results or index < 0 or index >= len(results):
        await query.edit_message_text("❌ Invalid choice.")
        return

    video = results[index]
    video_url = f"https://www.youtube.com/watch?v={video['id']}"
    video_title = video.get("title", "Unknown Title")

    await query.edit_message_text(f"⬇️ Downloading: {video_title}")

    # Download audio
    ydl_opts_download = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": "%(title)s.%(ext)s",
        "quiet": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
            file_info = ydl.extract_info(video_url, download=True)
            file_name = ydl.prepare_filename(file_info)

        # Send to user
        with open(file_name, "rb") as audio:
            await query.message.reply_audio(audio=audio, title=file_info.get("title", "Audio"))

        # Clean up
        os.remove(file_name)
        del user_search_results[user.id]

        print(f"✅ Sent '{video_title}' to user {user.id}")

    except Exception as e:
        print(f"❌ Error downloading for user {user.id}: {str(e)}")
        await query.message.reply_text(f"❌ Error: {str(e)}")

# Init bot
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_song))
app.add_handler(CallbackQueryHandler(button_handler))

print("🤖 Bot running...")
app.run_polling()