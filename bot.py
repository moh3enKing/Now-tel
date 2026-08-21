import os
import logging
import subprocess
import tempfile
import glob
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# توکن ربات (مستقیم در کد)
BOT_TOKEN = "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY"  # ⚠️ این رو عوض کن!

# کلیدهای اسپاتیفای (از محیط می‌گیریم یا می‌تونی مستقیم هم بذاری)
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! لینک آهنگ اسپاتیفای رو بفرست تا برات دانلودش کنم. 🎵")

async def handle_spotify_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    if "open.spotify.com" not in link:
        await update.message.reply_text("لطفاً یک لینک معتبر از اسپاتیفای بفرست.")
        return

    await update.message.reply_text("در حال دانلود آهنگ... لطفاً چند لحظه صبر کنید.")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                "spotdl",
                link,
                "--output", os.path.join(tmpdir, "{artist} - {title}.{output-ext}"),
                "--format", "mp3"
            ]
            env = os.environ.copy()
            env["SPOTIPY_CLIENT_ID"] = SPOTIPY_CLIENT_ID
            env["SPOTIPY_CLIENT_SECRET"] = SPOTIPY_CLIENT_SECRET

            process = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=tmpdir)
            if process.returncode != 0:
                logger.error(f"spotdl error: {process.stderr}")
                await update.message.reply_text("متأسفانه دانلود انجام نشد. لینک را بررسی کنید یا دوباره تلاش کنید.")
                return

            files = glob.glob(os.path.join(tmpdir, "*.mp3"))
            if not files:
                await update.message.reply_text("فایل خروجی پیدا نشد.")
                return

            audio_file = files[0]
            with open(audio_file, 'rb') as f:
                await update.message.reply_audio(audio=f, title=os.path.basename(audio_file))

    except Exception as e:
        logger.exception(f"Error: {e}")
        await update.message.reply_text("خطایی رخ داد. لطفاً دوباره تلاش کنید.")

def main():
    if not SPOTIPY_CLIENT_ID or not SPOTIPY_CLIENT_SECRET:
        raise ValueError("SPOTIPY_CLIENT_ID و SPOTIPY_CLIENT_SECRET را تنظیم کنید!")
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_spotify_link))

    logger.info("ربات شروع به کار کرد...")
    app.run_polling()

if __name__ == "__main__":
    main()
