import os
import logging
import re
import subprocess
import tempfile
import glob
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# توکن ربات
BOT_TOKEN = "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY"  # ⚠️ بعداً عوضش کن

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_track_id(link: str):
    match = re.search(r'/track/([a-zA-Z0-9]+)', link)
    return match.group(1) if match else None

def get_track_info(track_id: str):
    """دریافت نام آهنگ و خواننده از صفحه اسپاتیفای (بدون API)"""
    url = f"https://open.spotify.com/track/{track_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
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
    else:
        raise Exception("نتیجه مورد نظر یافت نشد")

def search_and_download(query: str, tmpdir: str, preferred_site: str = "youtube"):
    """جستجو و دانلود با انتخاب سرویس"""
    # تنظیمات پایه
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'flac',
            'preferredquality': '0',
        }],
    }

    if preferred_site == "youtube":
        # تلاش با کلاینت‌های مختلف یوتیوب
        ydl_opts['extractor_args'] = {'youtube': {'player_client': ['android', 'web', 'ios']}}
    elif preferred_site == "soundcloud":
        # جستجو در ساندکلود
        ydl_opts['extractor_args'] = {'soundcloud': {'client_id': 'Web'}}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # جستجو و انتخاب اولین نتیجه
        search_url = f"{preferred_site}search1:{query}" if preferred_site == "youtube" else f"scsearch1:{query}"
        try:
            search = ydl.extract_info(search_url, download=False)
            if 'entries' in search and search['entries']:
                first_entry = search['entries'][0]
                video_url = first_entry['webpage_url']
                ydl.download([video_url])
                return True
        except Exception as e:
            logger.warning(f"جستجو در {preferred_site} ناموفق بود: {e}")
            return False
    
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! لینک آهنگ اسپاتیفای رو بفرست تا برات با کیفیت FLAC دانلود کنم. 🎵")

async def handle_spotify_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    track_id = extract_track_id(link)
    if not track_id:
        await update.message.reply_text("لینک معتبر نیست. لینک ترک اسپاتیفای رو بفرست (مثل open.spotify.com/track/...).")
        return

    await update.message.reply_text("در حال دریافت اطلاعات آهنگ...")

    try:
        title, artist = get_track_info(track_id)
        search_query = f"{title} {artist}"
        await update.message.reply_text(f"🎵 {title} - {artist}\nدر حال جستجو و دانلود...")

        with tempfile.TemporaryDirectory() as tmpdir:
            # اول یوتیوب رو امتحان کن
            success = search_and_download(search_query, tmpdir, "youtube")
            
            # اگه یوتیوب جواب نداد، ساندکلود
            if not success:
                await update.message.reply_text("یوتیوب مسدود کرد، در حال تلاش از ساندکلود...")
                success = search_and_download(search_query, tmpdir, "soundcloud")
            
            if not success:
                await update.message.reply_text("هیچ منبعی برای این آهنگ پیدا نشد.")
                return

            # پیدا کردن فایل دانلود شده
            files = glob.glob(os.path.join(tmpdir, "*.flac"))
            if not files:
                files = glob.glob(os.path.join(tmpdir, "*.mp3"))
                if not files:
                    await update.message.reply_text("فایل خروجی پیدا نشد.")
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
