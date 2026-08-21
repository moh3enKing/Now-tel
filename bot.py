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
    return "Spotify Audio Downloader is ONLINE!"

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
# دانلود کامل با بای‌پاس فایروال (موتور اندروید/آیفون)
# --------------------------------------------------
def download_exact_track(track_name: str, artist_name: str, chat_id: int):
    query = f"{artist_name} - {track_name}"
    logger.info(f"Searching for exact track: '{query}'")
    send_message(chat_id, f"🔍 **جستجو و دریافت موزیک اصلی:**\n🎵 `{query}`")

    os.makedirs("downloads", exist_ok=True)
    output_template = f"downloads/{artist_name} - {track_name}.%(ext)s"

    # تنظیمات اختصاصی yt-dlp برای دور زدن شناسایی بات روی Render
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'mweb']
            }
        }
    }

    # کوئری‌های جستجو: ابتدا YouTube با کلاینت اندروید، سپس SoundCloud به عنوان پشتیبان
    search_targets = [
        f"ytsearch5:{artist_name} {track_name} audio",
        f"scsearch5:{artist_name} {track_name}"
    ]

    selected_url = None
    artist_clean = artist_name.lower().strip()

    # گام ۱: جستجو و تطبیق نام خواننده
    search_ydl_opts = {
        'quiet': True, 
        'no_warnings': True, 
        'extractor_args': {'youtube': {'player_client': ['android', 'ios']}}
    }

    with yt_dlp.YoutubeDL(search_ydl_opts) as ydl:
        for target in search_targets:
            try:
                logger.info(f"Executing search query: {target}")
                info = ydl.extract_info(target, download=False)
                entries = info.get('entries', []) if info else []
                
                for entry in entries:
                    if not entry: continue
                    title = entry.get('title', '').lower()
                    uploader = entry.get('uploader', '').lower()
                    url = entry.get('url') or entry.get('webpage_url')
                    
                    if artist_clean in title or artist_clean in uploader or len(entries) == 1:
                        selected_url = url
                        logger.info(f"[MATCHED TRACK] Title: {entry.get('title')} | URL: {url}")
                        break
                
                if selected_url:
                    break
            except Exception as e:
                logger.error(f"Search error for {target}: {e}")

    # فال‌بک به اولین نتیجه در صورت عدم مطابقت عنوان
    if not selected_url:
        logger.info("Fallback: taking first result from ytsearch1...")
        selected_url = f"ytsearch1:{artist_name} {track_name}"

    # گام ۲: انجام دانلود واقعی
    send_message(chat_id, "📥 **شناسه موزیک تایید شد! در حال دانلود کامل...**")
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            dl_info = ydl.extract_info(selected_url, download=True)
            
            if 'entries' in dl_info and dl_info['entries']:
                dl_info = dl_info['entries'][0]
            
            out_file = ydl.prepare_filename(dl_info)
            
            # برحصور پسوند فایل صوتی خروجی
            possible_files = [
                out_file,
                os.path.splitext(out_file)[0] + ".mp3",
                os.path.splitext(out_file)[0] + ".m4a",
                os.path.splitext(out_file)[0] + ".opus",
                os.path.splitext(out_file)[0] + ".webm"
            ]
            
            final_file = None
            for pf in possible_files:
                if os.path.exists(pf) and os.path.getsize(pf) > 1000000:
                    final_file = pf
                    break

            if final_file:
                size_mb = round(os.path.getsize(final_file) / (1024 * 1024), 2)
                logger.info(f"Download completed successfully: {final_file} ({size_mb} MB)")
                return final_file, size_mb
    except Exception as e:
        logger.error(f"Download execution failed: {e}")

    return None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    logger.info("🚀 [Render Fixed Bot] Active and listening...")
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
                            logger.info(f"New download request from {chat_id}: {text}")

                            track_name, artist_name = get_spotify_track_info(text)
                            logger.info(f"Metadata -> Artist: '{artist_name}', Track: '{track_name}'")

                            if not track_name or not artist_name:
                                send_message(chat_id, "❌ استخراج اطلاعات از لینک اسپاتیفای ناموفق بود.")
                                continue

                            file_path, size_mb = download_exact_track(track_name, artist_name, chat_id)

                            if file_path and size_mb > 0:
                                send_message(chat_id, f"⚡️ **دانلود موزیک با موفقیت انجام شد!**\n📦 **حجم:** `{size_mb} MB`\nدر حال ارسال فایل...")
                                send_document(
                                    chat_id,
                                    file_path,
                                    f"🎼 **{artist_name} - {track_name}**\n📦 **حجم:** `{size_mb} MB`"
                                )
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

