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
    return "Raw Audio Stream Downloader is ONLINE!"

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
# دانلود مستقیم استریم صوتی خام (Raw Audio Stream - بدون تبدیل)
# --------------------------------------------------
def download_exact_track(track_name: str, artist_name: str, chat_id: int):
    query = f"{artist_name} - {track_name}"
    logger.info(f"Searching raw audio stream for: '{query}'")
    send_message(chat_id, f"🔍 **در حال دریافت استریم صوتی خام (بدون هیچ تبدیلی):**\n🎵 `{query}`")

    os.makedirs("downloads", exist_ok=True)
    output_template = f"downloads/{artist_name} - {track_name}.%(ext)s"

    # اولویت دریافت استریم صوتی خام خالص (m4a / opus / webm)
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=opus]/bestaudio/best',
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

    search_targets = [
        f"ytsearch5:{artist_name} {track_name} audio",
        f"scsearch5:{artist_name} {track_name}"
    ]

    selected_url = None
    artist_clean = artist_name.lower().strip()

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

    if not selected_url:
        selected_url = f"ytsearch1:{artist_name} {track_name}"

    send_message(chat_id, "📥 **استریم صوتی خام دریافت شد! در حال ذخیره فایل بدون هیچ تغییر...**")
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            dl_info = ydl.extract_info(selected_url, download=True)
            
            if 'entries' in dl_info and dl_info['entries']:
                dl_info = dl_info['entries'][0]
            
            out_file = ydl.prepare_filename(dl_info)
            
            # اصلاح پسوند ظاهری کانتینر mp4 به m4a بدون دست زدن به دیتای فایل
            if out_file.endswith('.mp4'):
                new_m4a_path = out_file[:-4] + '.m4a'
                os.rename(out_file, new_m4a_path)
                out_file = new_m4a_path

            if os.path.exists(out_file) and os.path.getsize(out_file) > 1000000:
                size_mb = round(os.path.getsize(out_file) / (1024 * 1024), 2)
                logger.info(f"Raw audio stream saved: {out_file} ({size_mb} MB)")
                return out_file, size_mb
    except Exception as e:
        logger.error(f"Download execution failed: {e}")

    return None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    logger.info("🚀 [Render Raw Audio Bot] Active and listening...")
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
                                send_message(chat_id, f"⚡️ **فایل صوتی خام بدون تغییر دانلود شد!**\n📦 **حجم:** `{size_mb} MB`\nدر حال ارسال فایل سند...")
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

