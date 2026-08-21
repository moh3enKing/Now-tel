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
# تنظیمات سیستم لاگ‌گیری در ترمینال Render
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
    return "Pure Uncompressed Lossless Audio Server is ONLINE!"

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
# استخراج متاداده دقیق اسپاتیفای
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
# دانلود استریم صوتی خام و اصلی (بدون تبدیل به MP3 یا فشرده‌سازی)
# --------------------------------------------------
def download_uncompressed_audio(spotify_url: str, track_name: str, artist_name: str, chat_id: int):
    query = f"{artist_name} {track_name}"
    logger.info(f"در حال استخراج استریم خام و بدون فشرده‌سازی برای: {query}")
    send_message(chat_id, f"💎 **در حال استخراج استریم صوتی خام (بدون تبدیل به MP3)...**\n🎵 `{artist_name} - {track_name}`")

    os.makedirs("downloads", exist_ok=True)
    out_template = f"downloads/{artist_name} - {track_name}.%(ext)s"

    # تنظیمات استخراج فایل صوتی کاملاً خام بدون هیچ‌گونه re-encode یا فشرده‌سازی MP3
    ydl_opts = {
        'format': 'bestaudio[ext=flac]/bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': out_template,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True
    }

    search_queries = [
        f"scsearch1:{artist_name} {track_name}",
        f"scsearch1:{artist_name} - {track_name}"
    ]

    downloaded_file = None

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for sq in search_queries:
            try:
                logger.info(f"دریافت استریم خام از: {sq}")
                info = ydl.extract_info(sq, download=True)
                
                if 'entries' in info and info['entries']:
                    info = info['entries'][0]
                
                out_name = ydl.prepare_filename(info)

                if os.path.exists(out_name) and os.path.getsize(out_name) > 1000000:
                    downloaded_file = out_name
                    logger.info(f"فایل خام آماده شد: {downloaded_file}")
                    break
            except Exception as e:
                logger.error(f"خطا در دانلود {sq}: {e}")

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
    logger.info("🚀 ربات استخراج فایل صوتی خام و فشرده‌نشده آنلاین شد...")
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

                            file_path, size_mb = download_uncompressed_audio(text, track_name, artist_name, chat_id)

                            if file_path and size_mb > 0:
                                ext_name = os.path.splitext(file_path)[1].replace('.', '').upper()
                                send_message(chat_id, f"🔥 **فایل صوتی خام ({ext_name}) دریافت شد!**\n📦 **حجم:** `{size_mb} MB`\nدر حال ارسال به صورت سند...")
                                success = send_document_file(
                                    chat_id,
                                    file_path,
                                    f"🎼 **{artist_name} - {track_name}**\n💿 **فرمت صوتی اصلی:** `{ext_name}` (بدون فشرده‌سازی MP3)\n📦 **حجم:** `{size_mb} MB`"
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

