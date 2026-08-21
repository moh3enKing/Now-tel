import re
import os
import sys
import time
import logging
import urllib.parse
import threading
import cloudscraper
from flask import Flask

# --------------------------------------------------
# تنظیمات لاگر برای چاپ ۱۰۰٪ تضمینی در ترمینال رندر
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
    return "Ultimate Lossless FLAC Bot is ONLINE!"

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
        # استفاده از کلوداسکریپر برای بای‌پاس کلودفلر
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
# موتور اصلی دانلود FLAC با دور زدن تحریم‌ها
# --------------------------------------------------
def download_flac_bypassed(spotify_url: str, track_name: str, artist_name: str, chat_id: int):
    query = f"{artist_name} {track_name}"
    send_message(chat_id, f"🔍 **در حال عبور از فایروال و جستجوی Lossless...**\n🎵 `{query}`")

    # ساخت یک مرورگر مجازی برای گول زدن کلودفلر
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )

    endpoints = [
        # Engine 1: FabDL (معمولاً FLAC میده)
        f"https://api.fabdl.com/spotify/get?url={urllib.parse.quote(spotify_url)}",
        # Engine 2: SpotiDownloader
        f"https://spotidownloader.com/api/download-track?q={urllib.parse.quote(query)}"
    ]

    for index, api_url in enumerate(endpoints, 1):
        logger.info(f"--- TRYING ENGINE {index} ---")
        logger.info(f"Target API: {api_url}")
        send_message(chat_id, f"📡 **ارتباط با سرور شماره {index}...**")
        
        try:
            res = scraper.get(api_url, timeout=25)
            logger.info(f"Engine {index} Status: {res.status_code}")
            logger.info(f"Engine {index} Response: {res.text[:200]}")

            if res.status_code == 200:
                data = res.json()
                dl_url = None
                
                # پیدا کردن لینک دانلود توی JSON های مختلف
                if "result" in data and isinstance(data["result"], dict):
                    dl_url = data["result"].get("download_url") or data["result"].get("gid")
                elif "download_url" in data:
                    dl_url = data["download_url"]
                
                if dl_url:
                    logger.info(f"Direct Link Found: {dl_url}")
                    send_message(chat_id, "📥 **لینک استخراج شد! در حال دانلود...**")
                    
                    file_res = scraper.get(dl_url, timeout=120)
                    content = file_res.content
                    size_mb = round(len(content) / (1024 * 1024), 2)
                    logger.info(f"Downloaded File Size: {size_mb} MB")

                    # اگر فایل بزرگتر از ۲ مگابایت بود (یعنی فایل کامله)
                    if len(content) > 2000000:
                        filename = f"{artist_name} - {track_name} [FLAC-Lossless].flac"
                        logger.info(f"SUCCESS! Returning {filename}")
                        return content, filename, size_mb
                    else:
                        logger.warning("File too small, skipping.")
        except Exception as e:
            logger.error(f"Engine {index} Failed: {e}")

    return None, None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    logger.info("🚀 Bot is RUNNING and listening for Telegram messages...")
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
                            send_message(chat_id, "💎 **ربات دانلود Lossless (با بای‌پاس کلودفلر)**\n\nلینک اسپاتیفای را بفرستید:")
                            continue

                        if "open.spotify.com/track/" in text:
                            logger.info("-" * 40)
                            logger.info(f"NEW REQUEST from {chat_id}: {text}")

                            track_name, artist_name = get_spotify_track_info(text)
                            logger.info(f"Parsed -> Artist: {artist_name}, Track: {track_name}")

                            if not track_name:
                                send_message(chat_id, "❌ استخراج اطلاعات ناموفق بود.")
                                continue

                            flac_bytes, filename, size_mb = download_flac_bypassed(text, track_name, artist_name, chat_id)

                            if flac_bytes and size_mb > 0:
                                send_message(chat_id, f"⚡️ **دانلود کامل شد!**\n📦 **حجم:** `{size_mb} MB`\nدر حال آپلود به تلگرام...")
                                send_document(
                                    chat_id,
                                    flac_bytes,
                                    filename,
                                    f"🎼 **{artist_name} - {track_name}**\n💎 **کیفیت:** FLAC Lossless\n📦 **حجم:** `{size_mb} MB`"
                                )
                            else:
                                send_message(chat_id, "❌ متأسفانه دریافت فایل با خطا مواجه شد. لطفاً ترمینال Render را چک کنید.")
        except Exception as e:
            logger.error(f"Polling Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()


