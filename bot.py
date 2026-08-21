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
    return "Spotify Hi-Res Bot with OEmbed is ONLINE!"

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
# استخراج ۱۰۰٪ تضمینی متاداده با Spotify OEmbed API
# --------------------------------------------------
def get_spotify_track_info(spotify_url: str):
    logger.info(f"Fetching metadata via Spotify OEmbed API: {spotify_url}")
    try:
        clean_url = spotify_url.split('?')[0]
        oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(clean_url)}"
        
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(oembed_url, headers=headers, timeout=10)
        
        if res.status_code == 200:
            data = res.json()
            title = data.get("title", "")
            # عنوان معمولاً به صورت "Track Name" یا "Artist - Track Name" است
            if " - " in title:
                parts = title.split(" - ", 1)
                return parts[1].strip(), parts[0].strip()
            elif title:
                # اگر فقط اسم تراک بود، از نام صاحب کنسرت/آلبوم استفاده می‌کنیم
                author = data.get("author_name", "").strip()
                return title.strip(), author if author else "Unknown Artist"
    except Exception as e:
        logger.error(f"OEmbed Error: {e}")

    # Fallback به اسکرپر در صورت ناموفق بودن OEmbed
    try:
        scraper = cloudscraper.create_scraper()
        res = scraper.get(spotify_url, timeout=10)
        m = re.search(r'<title>(.*?) - song and lyrics by (.*?) \| Spotify</title>', res.text)
        if m: return m.group(1).strip(), m.group(2).strip()
    except Exception as e:
        logger.error(f"Scraper Fallback Error: {e}")

    return None, None

# --------------------------------------------------
# دریافت فایل صوتی اصلی با کیفیت بالا
# --------------------------------------------------
def download_exact_track(track_name: str, artist_name: str, chat_id: int):
    query = f"{artist_name} - {track_name}"
    logger.info(f"Searching audio stream for: '{query}'")
    send_message(chat_id, f"🔍 **در حال دریافت سورس اصلی موزیک:**\n🎵 `{query}`")

    os.makedirs("downloads", exist_ok=True)
    output_template = f"downloads/{artist_name} - {track_name}.%(ext)s"

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
                logger.info(f"Search query: {target}")
                info = ydl.extract_info(target, download=False)
                entries = info.get('entries', []) if info else []
                
                for entry in entries:
                    if not entry: continue
                    title = entry.get('title', '').lower()
                    uploader = entry.get('uploader', '').lower()
                    url = entry.get('url') or entry.get('webpage_url')
                    
                    if artist_clean in title or artist_clean in uploader or len(entries) == 1:
                        selected_url = url
                        logger.info(f"[MATCHED] Title: {entry.get('title')} | URL: {url}")
                        break
                
                if selected_url:
                    break
            except Exception as e:
                logger.error(f"Search error: {e}")

    if not selected_url:
        selected_url = f"ytsearch1:{artist_name} {track_name}"

    send_message(chat_id, "📥 **در حال ذخیره فایل اصلی صوتی بدون افت کیفیت...**")
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            dl_info = ydl.extract_info(selected_url, download=True)
            
            if 'entries' in dl_info and dl_info['entries']:
                dl_info = dl_info['entries'][0]
            
            out_file = ydl.prepare_filename(dl_info)
            
            # تغییر پسوند ظاهری mp4 به m4a بدون دست زدن به کیفیت صوتی
            if out_file.endswith('.mp4'):
                new_m4a_path = out_file[:-4] + '.m4a'
                os.rename(out_file, new_m4a_path)
                out_file = new_m4a_path

            if os.path.exists(out_file) and os.path.getsize(out_file) > 1000000:
                size_mb = round(os.path.getsize(out_file) / (1024 * 1024), 2)
                logger.info(f"File saved successfully: {out_file} ({size_mb} MB)")
                return out_file, size_mb
    except Exception as e:
        logger.error(f"Download execution failed: {e}")

    return None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    logger.info("🚀 [Render Spotify OEmbed Bot] Active and listening...")
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
                            logger.info(f"New request from {chat_id}: {text}")

                            track_name, artist_name = get_spotify_track_info(text)
                            logger.info(f"Parsed Metadata -> Artist: '{artist_name}', Track: '{track_name}'")

                            if not track_name or not artist_name:
                                send_message(chat_id, "❌ استخراج اطلاعات از لینک اسپاتیفای ناموفق بود.")
                                continue

                            file_path, size_mb = download_exact_track(track_name, artist_name, chat_id)

                            if file_path and size_mb > 0:
                                send_message(chat_id, f"⚡️ **فایل اصلی موزیک دانلود شد!**\n📦 **حجم:** `{size_mb} MB`\nدر حال ارسال فایل سند...")
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

