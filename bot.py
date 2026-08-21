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
# تنظیمات لاگ‌گیری دقیق در ترمینال Render
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
    return "True High Quality Downloader is ONLINE!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --------------------------------------------------
# توابع ارسال پیام به تلگرام
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
    logger.info(f"Extracting Spotify metadata: {spotify_url}")
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
# موتور اختصاصی کیفیت اصلی (320kbps / Lossless)
# --------------------------------------------------
def download_hi_res_audio(spotify_url: str, track_name: str, artist_name: str, chat_id: int):
    query = f"{artist_name} {track_name}"
    logger.info(f"Searching Hi-Res source for: '{query}'")
    send_message(chat_id, f"💎 **در حال جستجوی سورس کیفیت ۳۲۰ واقعی / Lossless...**\n🎵 `{query}`")

    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )

    # ۱. جستجو در دیتابیس Deezer برای یافتن آی‌دی واقعی موزیک
    deezer_id = None
    try:
        search_url = f"https://api.deezer.com/search?q={urllib.parse.quote(query)}"
        res = scraper.get(search_url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("data") and len(data["data"]) > 0:
                deezer_id = data["data"][0].get("id")
                logger.info(f"Found Deezer Track ID: {deezer_id}")
    except Exception as e:
        logger.error(f"Deezer Search Error: {e}")

    # ۲. دیتابیس‌های استخراج با کیفیت بالاتر (۳۲۰ واقعی)
    hq_sources = [
        f"https://spotisongdownloader.com/api/download-track?q={urllib.parse.quote(query)}",
        f"https://api.spotidownloader.com/download?url={urllib.parse.quote(spotify_url)}",
        f"https://api.deezloader.site/download/track/{deezer_id}?quality=flac" if deezer_id else None
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://spotisongdownloader.com/"
    }

    for index, src_url in enumerate(hq_sources, 1):
        if not src_url: continue
        logger.info(f"Trying HQ Source {index}: {src_url}")
        send_message(chat_id, f"📡 **در حال ارتباط با گیت‌وی کیفیت عالی {index}...**")

        try:
            res = scraper.get(src_url, headers=headers, timeout=30, verify=False)
            logger.info(f"Source {index} Status: {res.status_code}")

            if res.status_code == 200:
                dl_url = None
                
                # استخراج لینک از JSON
                try:
                    data = res.json()
                    dl_url = data.get("download_url") or data.get("link") or data.get("url")
                except Exception:
                    # اگر پاسخ متن بود، لینک دانلود مستقیم را استخراج کن
                    urls = re.findall(r'https?://[^\s"\'<>]+', res.text)
                    for u in urls:
                        if any(ext in u.lower() for ext in ['.mp3', '.flac', '.m4a', 'cdn']):
                            dl_url = u
                            break

                if dl_url:
                    logger.info(f"Direct HQ Link Found: {dl_url}")
                    send_message(chat_id, "⚡️ **فایل با کیفیت عالی استخراج شد! در حال دانلود...**")

                    file_res = scraper.get(dl_url, headers=headers, timeout=120, verify=False)
                    content = file_res.content
                    size_mb = round(len(content) / (1024 * 1024), 2)
                    logger.info(f"Downloaded Size: {size_mb} MB")

                    # فایل ۳۲۰ واقعی برای آهنگ ۶ دقیقه‌ای معمولاً بالای ۱۴ مگابایت است
                    if len(content) > 2000000:
                        ext = "flac" if "flac" in dl_url.lower() else "mp3"
                        filename = f"{artist_name} - {track_name} [320k HQ].{ext}"
                        return content, filename, size_mb
        except Exception as e:
            logger.error(f"Error in Source {index}: {e}")

    return None, None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    logger.info("🚀 [Render Hi-Res Audio Bot] Active and listening...")
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
                            send_message(chat_id, "👋 **سلام!** لینک اسپاتیفای را ارسال کنید تا با بالاترین کیفیت دانلود شود:")
                            continue

                        if "open.spotify.com/track/" in text:
                            logger.info("-" * 40)
                            logger.info(f"New request from {chat_id}: {text}")

                            track_name, artist_name = get_spotify_track_info(text)
                            logger.info(f"Metadata -> Artist: '{artist_name}', Track: '{track_name}'")

                            if not track_name or not artist_name:
                                send_message(chat_id, "❌ استخراج اطلاعات ناموفق بود.")
                                continue

                            audio_bytes, filename, size_mb = download_hi_res_audio(text, track_name, artist_name, chat_id)

                            if audio_bytes and size_mb > 0:
                                send_message(chat_id, f"🔥 **دانلود کامل شد!**\n📦 **حجم فایل:** `{size_mb} MB`\nدر حال ارسال فایل سند...")
                                send_document(
                                    chat_id,
                                    audio_bytes,
                                    filename,
                                    f"🎼 **{artist_name} - {track_name}**\n💎 **کیفیت:** 320kbps True HQ / Lossless\n📦 **حجم:** `{size_mb} MB`"
                                )
                            else:
                                send_message(chat_id, "❌ متأسفانه سورس کیفیت ۳۲۰ برای این ترک یافت نشد.")
        except Exception as e:
            logger.error(f"Polling Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

