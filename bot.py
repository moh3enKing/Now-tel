import os
import logging
import re
import tempfile
import glob
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

BOT_TOKEN = "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY"  # ⚠️ حتماً عوضش کن

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_track_id(link: str):
    match = re.search(r'/track/([a-zA-Z0-9]+)', link)
    return match.group(1) if match else None

def get_track_info(track_id: str):
    url = f"https://open.spotify.com/track/{track_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise Exception("خطا در دریافت صفحه اسپاتیفای")
    soup = BeautifulSoup(resp.text, 'html.parser')
    title = soup.find('meta', property='og:title')
    artist = soup.find('meta', property='og:description')
    if title and artist:
        title = title['content']
        artist = artist['content'].split(' · ')[0]
        title = re.sub(r'\s*Song$', '', title)
        return title, artist
    raise Exception("اطلاعات پیدا نشد")

def search_soundcloud(query: str, tmpdir: str):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'flac', 'preferredquality': '0'}],
        'extractor_args': {'soundcloud': {'client_id': 'Web'}}
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search = ydl.extract_info(f"scsearch1:{query}", download=False)
            if 'entries' in search and search['entries']:
                ydl.download([search['entries'][0]['webpage_url']])
                return True
    except Exception as e:
        logger.warning(f"SoundCloud error: {e}")
    return False

def search_youtube(query: str, tmpdir: str):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'flac', 'preferredquality': '0'}],
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        'match_filter': lambda info: info.get('duration', 0) > 120 and info.get('duration', 0) < 600  # فیلتر مدت زمان ۲ تا ۱۰ دقیقه
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search = ydl.extract_info(f"ytsearch1:{query} audio", download=False)
            if 'entries' in search and search['entries']:
                ydl.download([search['entries'][0]['webpage_url']])
                return True
    except Exception as e:
        logger.warning(f"YouTube error: {e}")
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! لینک اسپاتیفای رو بفرست تا برات آهنگ رو دانلود کنم. 🎵")

async def handle_spotify_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    track_id = extract_track_id(link)
    if not track_id:
        await update.message.reply_text("لینک معتبر نیست.")
        return

    await update.message.reply_text("در حال دریافت اطلاعات آهنگ...")
    try:
        title, artist = get_track_info(track_id)
        query = f"{title} {artist}"
        await update.message.reply_text(f"🎵 {title} - {artist}\nدر حال جستجو در ساندکلود...")

        with tempfile.TemporaryDirectory() as tmpdir:
            success = search_soundcloud(query, tmpdir)
            if not success:
                await update.message.reply_text("ساندکلود جواب نداد، تلاش از یوتیوب...")
                success = search_youtube(query, tmpdir)

            if not success:
                await update.message.reply_text("هیچ منبعی پیدا نشد.")
                return

            files = glob.glob(os.path.join(tmpdir, "*.flac")) or glob.glob(os.path.join(tmpdir, "*.mp3"))
            if not files:
                await update.message.reply_text("فایل پیدا نشد.")
                return

            audio_file = files[0]
            with open(audio_file, 'rb') as f:
                await update.message.reply_audio(audio=f, title=os.path.basename(audio_file))

    except Exception as e:
        logger.exception(f"Error: {e}")
        await update.message.reply_text(f"خطا: {e}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_spotify_link))
    logger.info("ربات شروع به کار کرد...")
    app.run_polling()

if __name__ == "__main__":
    main()
