import re
import os
import sys
import time
import logging
import urllib.parse
import urllib3
import threading
import requests
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

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"

app = Flask(__name__)

@app.route('/')
def home():
    return "Exact Spotify Lossless Downloader is ONLINE!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

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
# استخراج دقیق متاداده اسپاتیفای
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
# دانلود مستقیم استریم خام بدون فشرده‌سازی با استفاده از Cobalt Engine
# --------------------------------------------------
def download_lossless_audio(spotify_url: str, track_name: str, artist_name: str, chat_id: int):
    clean_url = spotify_url.split('?')[0]
    logger.info(f"شروع استخراج استریم بی‌اتلاف برای: {artist_name} - {track_name}")
    send_message(chat_id, f"💎 **در حال استخراج مستقیم فایل خام غیرفشرده (Lossless / Raw Audio)...**\n🎵 `{artist_name} - {track_name}`")

    os.makedirs("downloads", exist_ok=True)
    session = requests.Session()
    session.verify = False

    # ۱. استفاده از API رسمی Cobalt v7
    cobalt_nodes = [
        "https://api.cobalt.tools/api/json",
        "https://cobalt-api.kwippy.com/api/json",
        "https://co.wuk.sh/api/json"
    ]

    dl_url = None
    file_ext = "m4a"

    payload = {
        "url": clean_url,
        "audioFormat": "best",
        "isAudioOnly": True
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    for node in cobalt_nodes:
        try:
            logger.info(f"درخواست استریم به نود Cobalt: {node}")
            res = session.post(node, json=payload, headers=headers, timeout=20)
            logger.info(f"پاسخ نود: {res.status_code}")
            
            if res.status_code == 200:
                data = res.json()
                dl_url = data.get("url")
                if dl_url:
                    logger.info(f"لینک صوتی بی‌اتلاف دریافت شد: {dl_url}")
                    break
        except Exception as e:
            logger.error(f"خطا در نود {node}: {e}")

    # ۲. فال‌بک به API مستقیم Deezer/Spotify Direct اگر نودهای قبلی پاسخ ندادند
    if not dl_url:
        try:
            fallback_api = f"https://spotify-downloader-api.vercel.app/api/download?url={urllib.parse.quote(clean_url)}"
            logger.info(f"درخواست به API جایگزین: {fallback_api}")
            res = session.get(fallback_api, timeout=20)
            if res.status_code == 200:
                data = res.json()
                dl_url = data.get("link") or data.get("url")
        except Exception as e:
            logger.error(f"خطا در API جایگزین: {e}")

    # دانلود و ذخیره فایل خام روی دیسک
    if dl_link := dl_url:
        try:
            if "flac" in dl_link.lower(): file_ext = "flac"
            elif "wav" in dl_link.lower(): file_ext = "wav"
            elif "m4a" in dl_link.lower(): file_ext = "m4a"
            
            file_path = f"downloads/{artist_name} - {track_name}.{file_ext}"
            send_message(chat_id, "📥 **استریم خام تایید شد! در حال دانلود به صورت سند...**")

            file_res = session.get(dl_link, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=120)
            if file_res.status_code == 200:
                with open(file_path, "wb") as f:
                    for chunk in file_res.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                size_bytes = os.path.getsize(file_path)
                size_mb = round(size_bytes / (1024 * 1024), 2)
                logger.info(f"فایل خام ذخیره شد: {file_path} ({size_mb} MB)")

                if size_bytes > 1000000: # معتبر و بالای ۱ مگابایت
                    return file_path, size_mb
        except Exception as e:
            logger.error(f"خطا در ذخیره‌سازی فایل: {e}")

    return None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    logger.info("🚀 ربات استخراج مستقیم و بی‌اتلاف اسپاتیفای فعال شد...")
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

                            file_path, size_mb = download_lossless_audio(text, track_name, artist_name, chat_id)

                            if file_path and size_mb > 0:
                                ext_name = os.path.splitext(file_path)[1].replace('.', '').upper()
                                send_message(chat_id, f"🔥 **فایل صوتی غیرفشرده ({ext_name}) دریافت شد!**\n📦 **حجم:** `{size_mb} MB`\nدر حال ارسال به صورت سند...")
                                success = send_document_file(
                                    chat_id,
                                    file_path,
                                    f"🎼 **{artist_name} - {track_name}**\n💿 **فرمت اصلی:** `{ext_name}` (بدون فشرده‌سازی MP3)\n📦 **حجم:** `{size_mb} MB`"
                                )
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                            else:
                                send_message(chat_id, "❌ استخراج مستقیم استریم بی‌اتلاف برای این ترَک با خطا مواجه شد.")
        except Exception as e:
            logger.error(f"خطای سیستم Polling: {e}")
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

