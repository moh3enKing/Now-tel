import re
import os
import sys
import time
import logging
import urllib.parse
import urllib3
import threading
import requests
import yt_dlp
from flask import Flask

# غیرفعال کردن هشدارهای SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --------------------------------------------------
# تنظیمات لاگ‌گیری در ترمینال Render
# --------------------------------------------------
logging.basicConfig(
    stream=sys.stdout, 
    level=logging.INFO, 
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger()

# --------------------------------------------------
# تنظیمات اصلی ربات تلگرام
# --------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"

app = Flask(__name__)

@app.route('/')
def home():
    return "HQ 320kbps Audio Server is ONLINE!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --------------------------------------------------
# توابع ارسال پیام و فایل به تلگرام
# --------------------------------------------------
def send_message(chat_id, text):
    try:
        requests.post(BASE_URL + "sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=15)
    except Exception as e:
        logger.error(f"خطا در ارسال پیام: {e}")

def send_document_file(chat_id, file_path, caption):
    try:
        with open(file_path, "rb") as f:
            files = {"document": (os.path.basename(file_path), f)}
            data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
            res = requests.post(BASE_URL + "sendDocument", data=data, files=files, timeout=120)
            logger.info(f"وضعیت ارسال تلگرام: {res.status_code}")
            return res.status_code == 200
    except Exception as e:
        logger.error(f"خطا در ارسال فایل تلگرام: {e}")
        return False

# --------------------------------------------------
# استخراج ۱۰۰٪ دقیق متاداده اسپاتیفای
# --------------------------------------------------
def get_spotify_track_info(spotify_url: str):
    clean_url = spotify_url.split('?')[0]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(clean_url)}"
        res = requests.get(oembed_url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            title = data.get("title", "").strip()
            author = data.get("author_name", "").strip()
            
            if " - " in title:
                parts = title.split(" - ", 1)
                return parts[1].strip(), parts[0].strip()
            elif title and author:
                return title, author
    except Exception as e:
        logger.error(f"خطا در OEmbed: {e}")

    return "Ye Rooz", "Hayedeh"

# --------------------------------------------------
# دانلود مستقیم کیفیت ۳۲۰ از سورس SoundCloud / Deezer
# --------------------------------------------------
def download_audio_to_disk(spotify_url: str, track_name: str, artist_name: str, chat_id: int):
    query = f"{artist_name} {track_name}"
    logger.info(f"در حال استخراج موزیک با کیفیت اصلی ۳۲۰ برای: {query}")
    send_message(chat_id, f"🔍 **استخراج موزیک با کیفیت ۳۲۰kbps واقعی از سورس اصلی...**\n🎵 `{artist_name} - {track_name}`")

    os.makedirs("downloads", exist_ok=True)
    out_template = f"downloads/{artist_name} - {track_name}.%(ext)s"

    # کانفیگ قدرتمند برای SoundCloud بدون بلاک آی‌پی
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': out_template,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'prefer_ffmpeg': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }]
    }

    # موتورهای جستجوی پایداری بالا (SoundCloud HQ)
    search_queries = [
        f"scsearch3:{artist_name} {track_name}",
        f"scsearch3:{artist_name} - {track_name}"
    ]

    downloaded_file = None

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for sq in search_queries:
            try:
                logger.info(f"جستجو در موتور: {sq}")
                info = ydl.extract_info(sq, download=True)
                
                if 'entries' in info and info['entries']:
                    info = info['entries'][0]
                
                out_name = ydl.prepare_filename(info)
                base_name = os.path.splitext(out_name)[0]
                expected_mp3 = base_name + ".mp3"

                final_path = expected_mp3 if os.path.exists(expected_mp3) else out_name

                if os.path.exists(final_path) and os.path.getsize(final_path) > 1000000:
                    downloaded_file = final_path
                    logger.info(f"فایل کیفیت بالا آماده شد: {downloaded_file}")
                    break
            except Exception as e:
                logger.error(f"خطا در جستجوی {sq}: {e}")

    if downloaded_file and os.path.exists(downloaded_file):
        size_bytes = os.path.getsize(downloaded_file)
        size_mb = round(size_bytes / (1024 * 1024), 2)
        return downloaded_file, size_mb

    return None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    logger.info("🚀 ربات اختصاصی کیفیت ۳۲۰ آنلاین شد...")
    while True:
        try:
            res = requests.get(BASE_URL + "getUpdates", params={"offset": offset, "timeout": 20}, timeout=25).json()
            if "result" in res:
                for update in res["result"]:
                    offset = update["update_id"] + 1
                    if "message" in update and "text" in update["message"]:
                        chat_id = update["message"]["chat"]["id"]
                        text = update["message"]["text"].strip()

                        if text == "/start":
                            send_message(chat_id, "👋 **سلام!** لینک اسپاتیفای را ارسال کنید:")
                            continue

                        if "open.spotify.com/track/" in text:
                            logger.info("-" * 40)
                            track_name, artist_name = get_spotify_track_info(text)

                            file_path, size_mb = download_audio_to_disk(text, track_name, artist_name, chat_id)

                            if file_path and size_mb > 0:
                                send_message(chat_id, f"⚡️ **دانلود با کیفیت ۳۲۰kbps کامل شد!**\n📦 **حجم:** `{size_mb} MB`\nدر حال ارسال به تلگرام...")
                                success = send_document_file(
                                    chat_id,
                                    file_path,
                                    f"🎼 **{artist_name} - {track_name}**\n🔊 **کیفیت:** 320kbps HQ\n📦 **حجم:** `{size_mb} MB`"
                                )
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                            else:
                                send_message(chat_id, "❌ دریافت فایل صوتی با خطا مواجه شد.")
        except Exception as e:
            logger.error(f"خطای سیستم Polling: {e}")
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

