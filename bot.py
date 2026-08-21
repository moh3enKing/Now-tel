import re
import os
import sys
import time
import logging
import urllib.parse
import threading
import requests
import cloudscraper
import yt_dlp
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
    return "Exact Music Match Server is ONLINE!"

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

def send_document(chat_id, file_path, caption):
    try:
        with open(file_path, "rb") as f:
            files = {"document": (os.path.basename(file_path), f.read())}
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
# موتور هوشمند دانلود با تطبیق دقیق خواننده و آهنگ
# --------------------------------------------------
def download_exact_track(track_name: str, artist_name: str, chat_id: int):
    query = f"{artist_name} - {track_name}"
    logger.info(f"Exact Search Query: '{query}'")
    send_message(chat_id, f"🔍 **در حال جستجوی دقیق دیتابیس برای:**\n🎵 `{query}`")

    output_template = f"downloads/{artist_name} - {track_name}.%(ext)s"
    os.makedirs("downloads", exist_ok=True)

    # گزینه‌های موتور جستجو و دانلود yt-dlp
    ydl_search_opts = {
        'extract_flat': True,
        'quiet': True,
        'no_warnings': True,
    }

    selected_video_url = None
    search_queries = [
        f"ytmsearch5:{artist_name} {track_name}",
        f"ytsearch5:{artist_name} {track_name} audio"
    ]

    artist_clean = artist_name.lower().strip()
    track_clean = track_name.lower().strip()

    # فاز ۱: پیدا کردن دقیق‌ترین نتیجه بر اساس خواننده
    with yt_dlp.YoutubeDL(ydl_search_opts) as ydl:
        for sq in search_queries:
            try:
                info = ydl.extract_info(sq, download=False)
                entries = info.get('entries', [])
                
                for entry in entries:
                    if not entry: continue
                    title = entry.get('title', '').lower()
                    uploader = entry.get('uploader', '').lower()
                    url = entry.get('url') or entry.get('webpage_url')
                    
                    # شرط انطباق دقیق: اسم خواننده باید حتماً در عنوان یا خواننده باشد
                    if artist_clean in title or artist_clean in uploader:
                        selected_video_url = url
                        logger.info(f"[MATCH FOUND] Title: '{entry.get('title')}' | URL: {url}")
                        break
                
                if selected_video_url:
                    break
            except Exception as e:
                logger.error(f"Search error for '{sq}': {e}")

    # اگر تطبیق ۱۰۰٪ پیدا نشد، از نتایج اول اولویت‌بندی استفاده کن
    if not selected_video_url:
        logger.info("No strict artist match found, taking top result...")
        try:
            with yt_dlp.YoutubeDL(ydl_search_opts) as ydl:
                info = ydl.extract_info(f"ytmsearch1:{artist_name} {track_name}", download=False)
                entries = info.get('entries', [])
                if entries and entries[0]:
                    selected_video_url = entries[0].get('url') or entries[0].get('webpage_url')
        except Exception as e:
            logger.error(f"Top result fallback error: {e}")

    if not selected_video_url:
        logger.error("No stream URL found at all.")
        return None, 0

    # فاز ۲: دانلود بهترین کیفیت صوتی
    send_message(chat_id, "📥 **موزیک اصلی یافت شد! در حال دانلود با بالاترین کیفیت...**")
    
    out_file_path = None
    ydl_download_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_download_opts) as ydl:
            dl_info = ydl.extract_info(selected_video_url, download=True)
            out_file_path = ydl.prepare_filename(dl_info)

        if out_file_path and os.path.exists(out_file_path):
            size_bytes = os.path.getsize(out_file_path)
            size_mb = round(size_bytes / (1024 * 1024), 2)
            logger.info(f"Successfully downloaded: {out_file_path} ({size_mb} MB)")
            return out_file_path, size_mb
    except Exception as e:
        logger.error(f"Download Execution Error: {e}")

    return None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    logger.info("🚀 [Render Direct Match Bot] Listening for messages...")
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
                            send_message(chat_id, "👋 **سلام!** لینک اسپاتیفای را بفرستید تا دقیقاً همان موزیک اصلی با کیفیت عالی دانلود و ارسال شود:")
                            continue

                        if "open.spotify.com/track/" in text:
                            logger.info("-" * 40)
                            logger.info(f"NEW REQUEST from {chat_id}: {text}")

                            track_name, artist_name = get_spotify_track_info(text)
                            logger.info(f"Parsed Metadata -> Artist: '{artist_name}', Track: '{track_name}'")

                            if not track_name or not artist_name:
                                send_message(chat_id, "❌ خواندن لینک اسپاتیفای ناموفق بود.")
                                continue

                            file_path, size_mb = download_exact_track(track_name, artist_name, chat_id)

                            if file_path and size_mb > 0:
                                send_message(chat_id, f"⚡️ **دانلود آهنگ اصلی با موفقیت انجام شد!**\n📦 **حجم:** `{size_mb} MB`\nدر حال ارسال به صورت سند (Document)...")
                                send_document(
                                    chat_id,
                                    file_path,
                                    f"🎼 **{artist_name} - {track_name}**\n🔊 **کیفیت:** High Quality / Original Audio\n📦 **حجم:** `{size_mb} MB`"
                                )
                                # پاک‌سازی فایل از حافظه سرور
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                            else:
                                send_message(chat_id, "❌ خطایی در دانلود این تراک رخ داد.")
        except Exception as e:
            logger.error(f"Polling Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

