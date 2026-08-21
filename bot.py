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
    return "Spotify HQ Downloader Bot is ONLINE!"

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
# موتور اصلی دانلود با Bypass هوشمند
# --------------------------------------------------
def download_audio_guaranteed(spotify_url: str, track_name: str, artist_name: str, chat_id: int):
    query = f"{artist_name} - {track_name}"
    send_message(chat_id, f"🔍 **استخراج فایل با کیفیت اصلی...**\n🎵 `{query}`")

    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )

    # لیست موتورهای دریافت مستقیم با هدرهای شبیه‌سازی مرورگر
    engines = [
        {
            "name": "SpotifyDown Direct",
            "url": "https://api.spotifydown.com/download/" + (re.search(r'track/([a-zA-Z0-9]+)', spotify_url).group(1) if re.search(r'track/([a-zA-Z0-9]+)', spotify_url) else ""),
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Origin": "https://spotifydown.com",
                "Referer": "https://spotifydown.com/"
            }
        },
        {
            "name": "SpotiSongDownloader",
            "url": f"https://spotisongdownloader.com/api/download-track?q={urllib.parse.quote(query)}",
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Referer": "https://spotisongdownloader.com/"
            }
        }
    ]

    for eng in engines:
        if not eng["url"]: continue
        logger.info(f"Trying Engine: {eng['name']}")
        send_message(chat_id, f"📡 **تلاش با سرور {eng['name']}...**")

        try:
            res = scraper.get(eng["url"], headers=eng["headers"], timeout=20)
            logger.info(f"{eng['name']} Status: {res.status_code}")
            
            if res.status_code == 200:
                data = res.json()
                dl_url = data.get("link") or data.get("download_url") or data.get("url")
                
                if dl_url:
                    logger.info(f"Found Direct Link: {dl_url}")
                    send_message(chat_id, "📥 **لینک فایل دریافت شد! در حال دانلود...**")

                    file_res = scraper.get(dl_url, headers=eng["headers"], timeout=120)
                    content = file_res.content
                    size_mb = round(len(content) / (1024 * 1024), 2)
                    logger.info(f"Downloaded Size: {size_mb} MB")

                    if len(content) > 1500000: # حداقل ۱.۵ مگابایت
                        filename = f"{artist_name} - {track_name}.mp3"
                        return content, filename, size_mb
        except Exception as e:
            logger.error(f"Engine {eng['name']} Exception: {e}")

    return None, None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    logger.info("🚀 Bot is RUNNING with Guaranteed Direct Engine...")
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
                            send_message(chat_id, "👋 **سلام!** لینک اسپاتیفای را بفرستید تا فایل اصلی صوتی براتون ارسال بشه:")
                            continue

                        if "open.spotify.com/track/" in text:
                            logger.info("-" * 40)
                            logger.info(f"NEW REQUEST from {chat_id}: {text}")

                            track_name, artist_name = get_spotify_track_info(text)
                            logger.info(f"Parsed -> Artist: {artist_name}, Track: {track_name}")

                            if not track_name:
                                send_message(chat_id, "❌ استخراج اطلاعات از اسپاتیفای ناموفق بود.")
                                continue

                            flac_bytes, filename, size_mb = download_audio_guaranteed(text, track_name, artist_name, chat_id)

                            if flac_bytes and size_mb > 0:
                                send_message(chat_id, f"⚡️ **دانلود کامل شد!**\n📦 **حجم:** `{size_mb} MB`\nدر حال ارسال فایل سند (Document)...")
                                send_document(
                                    chat_id,
                                    flac_bytes,
                                    filename,
                                    f"🎼 **{artist_name} - {track_name}**\n📦 **حجم:** `{size_mb} MB`"
                                )
                            else:
                                send_message(chat_id, "❌ خطایی در استخراج فایل صوتی رخ داد.")
        except Exception as e:
            logger.error(f"Polling Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

