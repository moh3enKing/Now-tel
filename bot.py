import re
import os
import sys
import time
import logging
import urllib.parse
import threading
import requests
import cloudscraper
from flask import Flask

# --------------------------------------------------
# تنظیمات لاگر
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
    return "FabDL Fixed Lossless Bot is ONLINE!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --------------------------------------------------
# توابع ارسال پیام
# --------------------------------------------------
def send_message(chat_id, text):
    try:
        requests.post(BASE_URL + "sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
    except Exception as e:
        logger.error(f"Telegram Send Msg Error: {e}")

def send_document(chat_id, file_bytes, filename, caption):
    try:
        files = {"document": (filename, file_bytes)}
        data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
        requests.post(BASE_URL + "sendDocument", data=data, files=files)
    except Exception as e:
        logger.error(f"Telegram Send Doc Error: {e}")

# --------------------------------------------------
# استخراج متاداده از اسپاتیفای
# --------------------------------------------------
def get_spotify_track_info(spotify_url: str):
    logger.info(f"Scraping Spotify URL: {spotify_url}")
    try:
        scraper = cloudscraper.create_scraper()
        res = scraper.get(spotify_url, timeout=15)
        
        m = re.search(r'<title>(.*?) - song and lyrics by (.*?) \| Spotify</title>', res.text)
        if m: return m.group(1).strip(), m.group(2).strip()
            
        m2 = re.search(r'<title>(.*?) - Single by (.*?) \| Spotify</title>', res.text)
        if m2: return m2.group(1).strip(), m2.group(2).strip()
            
        m3 = re.search(r'<title>(.*?) - song by (.*?) \| Spotify</title>', res.text)
        if m3: return m3.group(1).strip(), m3.group(2).strip()
    except Exception as e:
        logger.error(f"Scrape Error: {e}")
    return None, None

# --------------------------------------------------
# دانلود FLAC/HQ با موتور اصلاح‌شده FabDL
# --------------------------------------------------
def download_flac_fabdl(spotify_url: str, track_name: str, artist_name: str, chat_id: int):
    send_message(chat_id, f"🔍 **استخراج از موتور FabDL (با هدرهای اختصاصی)...**\n🎵 `{artist_name} - {track_name}`")

    scraper = cloudscraper.create_scraper()

    # هدرهای اصلی برای دور زدن "invalid origin"
    fabdl_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Origin": "https://fabdl.com",
        "Referer": "https://fabdl.com/",
        "Accept": "application/json, text/plain, */*"
    }

    # گام اول: گرفتن Task GID
    get_api = f"https://api.fabdl.com/spotify/get?url={urllib.parse.quote(spotify_url)}"
    logger.info(f"FabDL Step 1: GET {get_api}")
    send_message(chat_id, "📡 **گام ۱: دریافت شناسه فایل از FabDL...**")

    try:
        res = scraper.get(get_api, headers=fabdl_headers, timeout=20)
        logger.info(f"FabDL Step 1 Status: {res.status_code}")
        logger.info(f"FabDL Step 1 Response: {res.text[:300]}")

        if res.status_code == 200:
            data = res.json()
            result = data.get("result", {})
            gid = result.get("gid")
            task_id = result.get("id")

            if gid and task_id:
                # گام دوم: تبدیل و گرفتن لینک دانلود مستقیم
                convert_api = f"https://api.fabdl.com/spotify/mp3-convert-task/{gid}/{task_id}"
                logger.info(f"FabDL Step 2: GET {convert_api}")
                send_message(chat_id, "📥 **گام ۲: دریافت لینک دانلود مستقیم...**")

                # چند ثانیه مکث برای پردازش سرور FabDL
                time.sleep(2)
                conv_res = scraper.get(convert_api, headers=fabdl_headers, timeout=25)
                logger.info(f"FabDL Step 2 Status: {conv_res.status_code}")
                logger.info(f"FabDL Step 2 Response: {conv_res.text[:300]}")

                if conv_res.status_code == 200:
                    conv_data = conv_res.json()
                    dl_path = conv_data.get("result", {}).get("download_url")

                    if dl_path:
                        full_dl_url = f"https://api.fabdl.com{dl_path}" if dl_path.startswith("/") else dl_path
                        logger.info(f"Downloading final file from: {full_dl_url}")
                        send_message(chat_id, "⚡️ **در حال دانلود فایل اصلی...**")

                        file_res = scraper.get(full_dl_url, headers=fabdl_headers, timeout=120)
                        content = file_res.content
                        size_mb = round(len(content) / (1024 * 1024), 2)
                        logger.info(f"Final File Size: {size_mb} MB")

                        if len(content) > 1500000:
                            filename = f"{artist_name} - {track_name} [HQ].mp3"
                            return content, filename, size_mb
    except Exception as e:
        logger.error(f"FabDL Engine Error: {e}")

    # Fallback به روش جستجوی مستقیم در صورت شکست
    try:
        logger.info("--- Trying Backup Engine ---")
        q = f"{artist_name} {track_name}"
        search_url = f"https://spotidownloader.com/api/download-track?q={urllib.parse.quote(q)}"
        res = scraper.get(search_url, timeout=20)
        if res.status_code == 200 and "download_url" in res.text:
            data = res.json()
            dl_url = data.get("download_url")
            if dl_url:
                file_res = scraper.get(dl_url, timeout=120)
                content = file_res.content
                size_mb = round(len(content) / (1024 * 1024), 2)
                if len(content) > 1500000:
                    return content, f"{artist_name} - {track_name}.mp3", size_mb
    except Exception as e:
        logger.error(f"Backup Engine Error: {e}")

    return None, None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    logger.info("🚀 Bot is RUNNING with Fixed FabDL Origin Headers...")
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
                            send_message(chat_id, "💎 **ربات دانلود موزیک اسپاتیفای (FabDL Engine)**\n\nلینک اسپاتیفای را بفرستید:")
                            continue

                        if "open.spotify.com/track/" in text:
                            logger.info("-" * 40)
                            logger.info(f"NEW REQUEST from {chat_id}: {text}")

                            track_name, artist_name = get_spotify_track_info(text)
                            logger.info(f"Parsed -> Artist: {artist_name}, Track: {track_name}")

                            if not track_name:
                                send_message(chat_id, "❌ استخراج اطلاعات ناموفق بود.")
                                continue

                            flac_bytes, filename, size_mb = download_flac_fabdl(text, track_name, artist_name, chat_id)

                            if flac_bytes and size_mb > 0:
                                send_message(chat_id, f"⚡️ **دانلود کامل شد!**\n📦 **حجم:** `{size_mb} MB`\nدر حال آپلود فایل سند به تلگرام...")
                                send_document(
                                    chat_id,
                                    flac_bytes,
                                    filename,
                                    f"🎼 **{artist_name} - {track_name}**\n📦 **حجم:** `{size_mb} MB`"
                                )
                            else:
                                send_message(chat_id, "❌ متأسفانه دریافت فایل با خطا مواجه شد. لاگ ترمینال را بررسی کنید.")
        except Exception as e:
            logger.error(f"Polling Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

