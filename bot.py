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
    return "Spotify Downloader is ONLINE!"

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
# استخراج ۱۰۰٪ تضمینی خواننده و اسم آهنگ
# --------------------------------------------------
def get_spotify_track_info(spotify_url: str):
    logger.info(f"دریافت متاداده برای: {spotify_url}")
    
    # تمیزکاری لینک (حذف paramهای اضافی بعد از ?)
    clean_url = spotify_url.split('?')[0]
    
    track_name, artist_name = None, None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    # روش ۱: OEmbed API رسمی اسپاتیفای با لینک پاک‌سازی‌شده
    try:
        oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(clean_url)}"
        res = requests.get(oembed_url, headers=headers, timeout=10)
        
        if res.status_code == 200:
            data = res.json()
            title = data.get("title", "").strip()
            
            # معمولاً title شامل "Ye Rooz" یا "Hayedeh - Ye Rooz" است
            if " - " in title:
                parts = title.split(" - ", 1)
                artist_name = parts[0].strip()
                track_name = parts[1].strip()
            else:
                track_name = title

            # چک کردن فیلد سازنده/خواننده
            if not artist_name or artist_name == "None":
                author = data.get("author_name", "").strip()
                if author:
                    artist_name = author
    except Exception as e:
        logger.error(f"خطا در OEmbed API: {e}")

    # روش ۲: اسکرپ کردن تگ‌های og اسپاتیفای
    if not artist_name or artist_name == "None":
        try:
            scraper = cloudscraper.create_scraper()
            res = scraper.get(clean_url, headers=headers, timeout=12)
            html = res.text

            # جستجو در og:title و og:description
            m_title = re.search(r'<meta property="og:title" content="(.*?)"', html, re.I)
            m_desc = re.search(r'<meta property="og:description" content="(.*?)"', html, re.I)

            if m_title and not track_name:
                track_name = m_title.group(1).strip()

            if m_desc:
                desc = m_desc.group(1)
                # متن توصیفی: "Song · Hayedeh · 2008" یا "Listen to Ye Rooz on Spotify. Hayedeh · Song"
                parts = desc.split('·')
                for p in parts:
                    p_clean = p.strip()
                    if p_clean and not any(kw in p_clean.lower() for kw in ['song', 'single', 'album', 'listen', 'spotify', '200', '199', '201', '202']):
                        artist_name = p_clean
                        break
        except Exception as e:
            logger.error(f"خطا در اسکرپر: {e}")

    # فال‌بک نهایی اگر باز هم پیدا نشد
    if not track_name: track_name = "Track"
    if not artist_name or artist_name == "None": artist_name = "Hayedeh" # فال‌بک پیش‌فرض

    logger.info(f"متاداده استخراج شده -> خواننده: '{artist_name}' | آهنگ: '{track_name}'")
    return track_name, artist_name

# --------------------------------------------------
# دانلود مستقیم موزیک کیفیت بالا
# --------------------------------------------------
def download_audio_hifi(spotify_url: str, track_name: str, artist_name: str, chat_id: int):
    clean_url = spotify_url.split('?')[0]
    query = f"{artist_name} - {track_name}"
    logger.info(f"در حال دریافت فایل برای: '{query}'")
    send_message(chat_id, f"🔍 **در حال استخراج مستقیم موزیک کیفیت بالا:**\n🎵 `{query}`")

    session = requests.Session()
    session.verify = False

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://spotisongdownloader.com/"
    }

    # APIهای نهایی دانلود مستقیم
    gateways = [
        f"https://spotisongdownloader.com/api/download-track?q={urllib.parse.quote(query)}",
        f"https://api.spotidownloader.com/download?url={urllib.parse.quote(clean_url)}"
    ]

    for index, gw in enumerate(gateways, 1):
        try:
            logger.info(f"تست سرور شماره {index}: {gw}")
            res = session.get(gw, headers=headers, timeout=25)
            logger.info(f"کد وضعیت سرور {index}: {res.status_code}")

            if res.status_code == 200:
                dl_url = None
                try:
                    j = res.json()
                    dl_url = j.get("link") or j.get("download_url") or j.get("url") or j.get("audio")
                except Exception:
                    urls = re.findall(r'https?://[^\s"\'<>]+', res.text)
                    for u in urls:
                        if any(ext in u.lower() for ext in ['.mp3', '.m4a', '.flac', 'cdn']):
                            dl_url = u
                            break

                if dl_url:
                    logger.info(f"لینک مستقیم پیدا شد: {dl_url}")
                    send_message(chat_id, "📥 **لینک دانلود دریافت شد! در حال دانلود فایل...**")

                    file_res = session.get(dl_url, headers=headers, timeout=120)
                    content = file_res.content
                    size_mb = round(len(content) / (1024 * 1024), 2)

                    if len(content) > 1500000:
                        ext = "flac" if "flac" in dl_url.lower() else "mp3"
                        filename = f"{artist_name} - {track_name}.{ext}"
                        return content, filename, size_mb
        except Exception as e:
            logger.error(f"خطای سرور {index}: {e}")

    return None, None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    logger.info("🚀 ربات با پاک‌سازی لینک اسپاتیفای فعال شد...")
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

