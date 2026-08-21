import re
import os
import sys
import time
import logging
import urllib.parse
import urllib3
import threading
import requests
import cloudscraper
from flask import Flask

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
    return "Hi-Res Audio Server is ONLINE!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --------------------------------------------------
# توابع ارسال پیام تلگرام
# --------------------------------------------------
def send_message(chat_id, text):
    try:
        requests.post(BASE_URL + "sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
    except Exception as e:
        logger.error(f"خطا در ارسال پیام: {e}")

def send_document(chat_id, file_bytes, filename, caption):
    try:
        files = {"document": (filename, file_bytes)}
        data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
        requests.post(BASE_URL + "sendDocument", data=data, files=files)
    except Exception as e:
        logger.error(f"خطا در ارسال فایل: {e}")

# --------------------------------------------------
# استخراج هوشمند متاداده اسپاتیفای
# --------------------------------------------------
def get_spotify_track_info(spotify_url: str):
    logger.info(f"دریافت متاداده برای: {spotify_url}")
    track_name, artist_name = None, None

    try:
        clean_url = spotify_url.split('?')[0]
        oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(clean_url)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(oembed_url, headers=headers, timeout=10)
        
        if res.status_code == 200:
            data = res.json()
            title = data.get("title", "").strip()
            author = data.get("author_name", "").strip()
            
            if " - " in title:
                parts = title.split(" - ", 1)
                artist_name = parts[0].strip()
                track_name = parts[1].strip()
            else:
                track_name = title
                if author: artist_name = author
    except Exception as e:
        logger.error(f"خطا در OEmbed: {e}")

    if not artist_name or artist_name == "Unknown Artist":
        try:
            scraper = cloudscraper.create_scraper()
            res = scraper.get(spotify_url, timeout=12)
            m = re.search(r'<title>(.*?) - song and lyrics by (.*?) \| Spotify</title>', res.text)
            if m:
                track_name = m.group(1).strip()
                artist_name = m.group(2).strip()
            else:
                m2 = re.search(r'<title>(.*?) - song by (.*?) \| Spotify</title>', res.text)
                if m2:
                    track_name = m2.group(1).strip()
                    artist_name = m2.group(2).strip()
        except Exception as e:
            logger.error(f"خطا در اسکرپر: {e}")

    logger.info(f"متاداده استخراج شده -> خواننده: '{artist_name}' | آهنگ: '{track_name}'")
    return track_name, artist_name

# --------------------------------------------------
# دانلود مستقیم کیفیت عالی از دیتابیس مستقیم
# --------------------------------------------------
def download_audio_hifi(spotify_url: str, track_name: str, artist_name: str, chat_id: int):
    query = f"{artist_name} {track_name}"
    logger.info(f"در حال استخراج مستقیم فایل اصلی برای: '{query}'")
    send_message(chat_id, f"🔍 **در حال دریافت سورس اصلی موزیک کیفیت بالا...**\n🎵 `{query}`")

    session = requests.Session()
    session.verify = False

    # ۱. گرفتن آی‌دی موزیک از Deezer
    deezer_id = None
    try:
        search_url = f"https://api.deezer.com/search?q={urllib.parse.quote(query)}"
        res = session.get(search_url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("data") and len(data["data"]) > 0:
                deezer_id = data["data"][0].get("id")
                preview_link = data["data"][0].get("preview")
                logger.info(f"Deezer ID: {deezer_id}")
    except Exception as e:
        logger.error(f"Deezer search error: {e}")

    # ۲. لیست گیت‌وی‌های مستقیم
    gateways = [
        f"https://api.fabdl.com/spotify/get?url={urllib.parse.quote(spotify_url)}",
        f"https://spotidownloader.com/api/download-track?q={urllib.parse.quote(query)}",
        f"https://spotify-downloader-api.vercel.app/api/download?url={urllib.parse.quote(spotify_url)}"
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://spotidownloader.com/"
    }

    for index, gw in enumerate(gateways, 1):
        try:
            logger.info(f"Testing Gateway {index}: {gw}")
            res = session.get(gw, headers=headers, timeout=25)
            logger.info(f"Gateway {index} status: {res.status_code}")

            if res.status_code == 200:
                try:
                    j = res.json()
                    dl_url = j.get("link") or j.get("download_url") or j.get("url") or j.get("audio")
                    if dl_url:
                        logger.info(f"Found Direct URL: {dl_url}")
                        send_message(chat_id, "📥 **فایل با کیفیت اصلی دریافت شد! در حال دانلود...**")

                        file_res = session.get(dl_url, headers=headers, timeout=120)
                        content = file_res.content
                        size_mb = round(len(content) / (1024 * 1024), 2)

                        if len(content) > 1500000:
                            ext = "flac" if "flac" in dl_url.lower() else "mp3"
                            filename = f"{artist_name} - {track_name}.{ext}"
                            return content, filename, size_mb
                except Exception as e_j:
                    logger.error(f"JSON Error: {e_j}")
        except Exception as e:
            logger.error(f"Gateway {index} error: {e}")

    return None, None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    logger.info("🚀 ربات فعال است...")
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
                            logger.info(f"درخواست جدید از کاربر {chat_id}: {text}")

                            track_name, artist_name = get_spotify_track_info(text)

                            if not track_name or not artist_name:
                                send_message(chat_id, "❌ استخراج اطلاعات اسپاتیفای ناموفق بود.")
                                continue

                            audio_bytes, filename, size_mb = download_audio_hifi(text, track_name, artist_name, chat_id)

                            if audio_bytes and size_mb > 0:
                                send_message(chat_id, f"🔥 **دانلود موفقیت‌آمیز بود!**\n📦 **حجم:** `{size_mb} MB`\nدر حال ارسال فایل سند...")
                                send_document(
                                    chat_id,
                                    audio_bytes,
                                    filename,
                                    f"🎼 **{artist_name} - {track_name}**\n📦 **حجم:** `{size_mb} MB`"
                                )
                            else:
                                send_message(chat_id, "❌ متأسفانه دریافت مستقیم این ترک با خطا مواجه شد.")
        except Exception as e:
            logger.error(f"خطای پویایی ربات: {e}")
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

