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
    return "Spotify Direct Parser Bot is ONLINE!"

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

def extract_download_link(text_data):
    """استخراج لینک‌های مستقیم صوتی از پاسخ‌های متنی و HTML"""
    urls = re.findall(r'https?://[^\s"\'<>]+', text_data)
    for u in urls:
        if any(ext in u.lower() for ext in ['.mp3', '.flac', 'download', 'cdn', 'stream']):
            return u
    return urls[0] if urls else None

# --------------------------------------------------
# دانلود مستقیم هوشمند
# --------------------------------------------------
def download_audio_smart(spotify_url: str, track_name: str, artist_name: str, chat_id: int):
    query = f"{artist_name} - {track_name}"
    send_message(chat_id, f"🔍 **استخراج مستقیم فایل صوتی...**\n🎵 `{query}`")

    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )

    sources = [
        # Source 1: SpotiSongDownloader Search
        {
            "name": "SpotiSong Engine",
            "url": f"https://spotisongdownloader.com/api/download-track?q={urllib.parse.quote(query)}",
            "headers": {"User-Agent": "Mozilla/5.0", "Referer": "https://spotisongdownloader.com/"}
        },
        # Source 2: SpotifyMate Direct API
        {
            "name": "SpotifyMate Engine",
            "url": f"https://spotidownloader.com/api/download-track?q={urllib.parse.quote(query)}",
            "headers": {"User-Agent": "Mozilla/5.0", "Referer": "https://spotidownloader.com/"}
        }
    ]

    for src in sources:
        logger.info(f"Trying {src['name']}...")
        send_message(chat_id, f"📡 **در حال پردازش با سرور {src['name']}...**")

        try:
            res = scraper.get(src["url"], headers=src["headers"], timeout=20)
            logger.info(f"{src['name']} Status Code: {res.status_code}")

            if res.status_code == 200:
                dl_url = None
                
                # تست استخراج به صورت JSON
                try:
                    data = res.json()
                    dl_url = data.get("download_url") or data.get("link") or data.get("url")
                except Exception:
                    # اگر JSON نبود و HTML بود، لینک رو با Regex می‌کشیم بیرون!
                    logger.info("Response is HTML/Text, parsing URLs with Regex...")
                    dl_url = extract_download_link(res.text)

                if dl_url:
                    logger.info(f"Direct Audio Link Found: {dl_url}")
                    send_message(chat_id, "📥 **لینک دانلود استخراج شد! در حال دانلود فایل...**")

                    file_res = scraper.get(dl_url, headers=src["headers"], timeout=120)
                    content = file_res.content
                    size_mb = round(len(content) / (1024 * 1024), 2)
                    logger.info(f"Downloaded File Size: {size_mb} MB")

                    if len(content) > 1500000: # فایل حداقل ۱.۵ مگابایت
                        filename = f"{artist_name} - {track_name}.mp3"
                        return content, filename, size_mb
                    else:
                        logger.warning("File too small, trying next source.")
        except Exception as e:
            logger.error(f"Error in {src['name']}: {e}")

    return None, None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    logger.info("🚀 Bot is RUNNING with Smart Direct Parser...")
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
                            send_message(chat_id, "👋 **سلام!** لینک اسپاتیفای را بفرستید تا فایل صوتی کامل تحویل داده شود:")
                            continue

                        if "open.spotify.com/track/" in text:
                            logger.info("-" * 40)
                            logger.info(f"NEW REQUEST from {chat_id}: {text}")

                            track_name, artist_name = get_spotify_track_info(text)
                            logger.info(f"Parsed -> Artist: {artist_name}, Track: {track_name}")

                            if not track_name:
                                send_message(chat_id, "❌ استخراج اطلاعات ناموفق بود.")
                                continue

                            flac_bytes, filename, size_mb = download_audio_smart(text, track_name, artist_name, chat_id)

                            if flac_bytes and size_mb > 0:
                                send_message(chat_id, f"⚡️ **دانلود با موفقیت انجام شد!**\n📦 **حجم فایل:** `{size_mb} MB`\nدر حال ارسال فایل سندی...")
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

