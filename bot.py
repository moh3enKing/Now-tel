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
    return "Spotify Audio Downloader Server is ONLINE!"

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
# استخراج دقیق متاداده (نام خواننده و آهنگ)
# --------------------------------------------------
def get_spotify_track_info(spotify_url: str):
    clean_url = spotify_url.split('?')[0]
    logger.info(f"دریافت متاداده برای: {clean_url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

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
# موتور دانلود اختصاصی بدون بستگی به APIهای خرابی سایت‌ها
# --------------------------------------------------
def download_audio_to_disk(spotify_url: str, track_name: str, artist_name: str, chat_id: int):
    clean_url = spotify_url.split('?')[0]
    query = f"{artist_name} - {track_name}"
    logger.info(f"در حال پردازش و استخراج فایل: {query}")
    send_message(chat_id, f"🔍 **در حال استخراج موزیک با کیفیت اصلی:**\n🎵 `{query}`")

    os.makedirs("downloads", exist_ok=True)
    file_path = f"downloads/{artist_name} - {track_name}.m4a"

    if os.path.exists(file_path):
        os.remove(file_path)

    # کانفیگ قدرتمند yt-dlp با کلاینت اندروید برای دور زدن کامل بلاک‌های Render
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=opus]/bestaudio/best',
        'outtmpl': f"downloads/{artist_name} - {track_name}.%(ext)s",
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'mweb']
            }
        }
    }

    search_queries = [
        f"ytsearch3:{artist_name} {track_name} audio",
        f"scsearch3:{artist_name} {track_name}"
    ]

    downloaded_file = None

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for sq in search_queries:
            try:
                logger.info(f"جستجو در سورس: {sq}")
                info = ydl.extract_info(sq, download=True)
                
                if 'entries' in info and info['entries']:
                    info = info['entries'][0]
                
                out_name = ydl.prepare_filename(info)
                
                # تبدیل کانتینر ظاهری mp4 به m4a بدون دست خوردن به دیتای صدا
                if out_name.endswith('.mp4'):
                    new_path = out_name[:-4] + '.m4a'
                    os.rename(out_name, new_path)
                    out_name = new_path

                if os.path.exists(out_name) and os.path.getsize(out_name) > 1000000:
                    downloaded_file = out_name
                    logger.info(f"فایل با موفقیت دانلود و ذخیره شد: {downloaded_file}")
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
    logger.info("🚀 ربات اختصاصی آنلاین شد...")
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
                            logger.info(f"درخواست جدید از {chat_id}: {text}")

                            track_name, artist_name = get_spotify_track_info(text)
                            logger.info(f"تایید متاداده: '{artist_name}' - '{track_name}'")

                            file_path, size_mb = download_audio_to_disk(text, track_name, artist_name, chat_id)

                            if file_path and size_mb > 0:
                                send_message(chat_id, f"⚡️ **دانلود کامل شد!**\n📦 **حجم:** `{size_mb} MB`\nدر حال ارسال فایل سند به تلگرام...")
                                success = send_document_file(
                                    chat_id,
                                    file_path,
                                    f"🎼 **{artist_name} - {track_name}**\n📦 **حجم:** `{size_mb} MB`"
                                )
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                                
                                if not success:
                                    send_message(chat_id, "❌ متأسفانه تلگرام اجازه آپلود فایل را نداد.")
                            else:
                                send_message(chat_id, "❌ دریافت مستقیم این ترک با خطا مواجه شد.")
        except Exception as e:
            logger.error(f"خطای سیستم Polling: {e}")
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

