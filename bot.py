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
    return "Exact Spotify Downloader Bot is ONLINE!"

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
# استخراج ID و متاداده از اسپاتیفای
# --------------------------------------------------
def extract_spotify_id(url: str):
    m = re.search(r'track/([a-zA-Z0-9]+)', url)
    return m.group(1) if m else None

def get_spotify_track_info(spotify_url: str):
    logger.info(f"Extracting metadata: {spotify_url}")
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
# موتور مستقیم با ID دقیق اسپاتیفای (بدون جستجوی اشتباه)
# --------------------------------------------------
def download_exact_audio(spotify_url: str, track_id: str, track_name: str, artist_name: str, chat_id: int):
    send_message(chat_id, f"🔍 **در حال استخراج مستقیم دقیقاً برای:**\n🎵 `{artist_name} - {track_name}`")

    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )

    # استفاده از APIهای مستقیم بر پایه ID تراک اسپاتیفای
    direct_apis = [
        # API 1: SpotifyMate Direct Track API
        {
            "url": "https://spotidownloader.com/api/download-track",
            "method": "POST",
            "json": {"url": spotify_url}
        },
        # API 2: Soundloaders Direct Track API
        {
            "url": f"https://api.spotifydown.com/download/{track_id}",
            "method": "GET",
            "headers": {"Referer": "https://spotifydown.com/", "Origin": "https://spotifydown.com"}
        }
    ]

    for index, api_info in enumerate(direct_apis, 1):
        logger.info(f"Trying Direct API {index}...")
        send_message(chat_id, f"📡 **ارتباط با سرور مستقیم {index}...**")

        try:
            if api_info["method"] == "POST":
                res = scraper.post(api_info["url"], json=api_info.get("json"), timeout=20)
            else:
                res = scraper.get(api_info["url"], headers=api_info.get("headers"), timeout=20)

            logger.info(f"API {index} Status: {res.status_code}")

            if res.status_code == 200:
                data = res.json()
                dl_url = data.get("link") or data.get("download_url") or data.get("url")

                if dl_url:
                    logger.info(f"Direct link found: {dl_url}")
                    send_message(chat_id, "📥 **لینک اصلی آهنگ استخراج شد! در حال دانلود...**")

                    file_res = scraper.get(dl_url, timeout=120)
                    content = file_res.content
                    size_mb = round(len(content) / (1024 * 1024), 2)
                    logger.info(f"Downloaded Size: {size_mb} MB")

                    if len(content) > 1500000:
                        filename = f"{artist_name} - {track_name}.mp3"
                        return content, filename, size_mb
        except Exception as e:
            logger.error(f"API {index} Exception: {e}")

    # fallback با جستجوی سخت‌گیرانه (Strict Match)
    logger.info("--- Strict Match Fallback ---")
    query = f"{artist_name} {track_name}"
    try:
        search_api = f"https://saavn.dev/api/search/songs?query={urllib.parse.quote(query)}"
        res = requests.get(search_api, timeout=12)
        if res.status_code == 200:
            results = res.json().get("data", {}).get("results", [])
            for item in results:
                title = item.get("name", "")
                primary_artists = item.get("primaryArtists", "")
                
                # بررسی اینکه آیا نام خواننده هم‌خوانی دارد یا نه
                if artist_name.lower() in primary_artists.lower() or artist_name.lower() in title.lower():
                    dl_urls = item.get("downloadUrl", [])
                    if dl_urls:
                        best_link = dl_urls[-1].get("url") if isinstance(dl_urls[-1], dict) else dl_urls[-1]
                        file_res = requests.get(best_link, timeout=90)
                        content = file_res.content
                        size_mb = round(len(content) / (1024 * 1024), 2)
                        if len(content) > 1500000:
                            return content, f"{artist_name} - {track_name} [320k].mp3", size_mb
    except Exception as e:
        logger.error(f"Strict Fallback Exception: {e}")

    return None, None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    logger.info("🚀 Exact Track Spotify Bot is RUNNING...")
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
                            send_message(chat_id, "👋 **سلام!** لینک اسپاتیفای را بفرستید تا دقیقاً همان آهنگ دانلود شود:")
                            continue

                        if "open.spotify.com/track/" in text:
                            logger.info("-" * 40)
                            logger.info(f"NEW REQUEST from {chat_id}: {text}")

                            track_id = extract_spotify_id(text)
                            track_name, artist_name = get_spotify_track_info(text)
                            logger.info(f"Track ID: {track_id} | Artist: {artist_name} | Track: {track_name}")

                            if not track_name or not artist_name:
                                send_message(chat_id, "❌ استخراج اطلاعات از لینک اسپاتیفای ناموفق بود.")
                                continue

                            flac_bytes, filename, size_mb = download_exact_audio(text, track_id, track_name, artist_name, chat_id)

                            if flac_bytes and size_mb > 0:
                                send_message(chat_id, f"⚡️ **دانلود آهنگ با موفقیت انجام شد!**\n📦 **حجم:** `{size_mb} MB`\nدر حال ارسال فایل سندی...")
                                send_document(
                                    chat_id,
                                    flac_bytes,
                                    filename,
                                    f"🎼 **{artist_name} - {track_name}**\n📦 **حجم:** `{size_mb} MB`"
                                )
                            else:
                                send_message(chat_id, "❌ دریافت دقیق این تراک با خطا مواجه شد.")
        except Exception as e:
            logger.error(f"Polling Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

