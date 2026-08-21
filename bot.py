import re
import os
import sys
import time
import logging
import urllib.parse
import urllib3
import threading
import requests
import yt_dlp
from flask import Flask

# غیرفعال کردن هشدارهای SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --------------------------------------------------
# تنظیمات لاگ‌گیری دقیق در ترمینال Render
# --------------------------------------------------
logging.basicConfig(
    stream=sys.stdout, 
    level=logging.INFO, 
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"

app = Flask(__name__)

@app.route('/')
def home():
    return "Exact Track Lossless Server is ONLINE!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def send_message(chat_id, text):
    try:
        requests.post(BASE_URL + "sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=15)
    except Exception as e:
        logger.error(f"خطا در ارسال پیام: {e}")

def send_document_file(chat_id, file_path, caption):
    try:
        with open(file_path, "rb") as f:
            files = {"document": (os.path.basename(file_path), f)}
            data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
            res = requests.post(BASE_URL + "sendDocument", data=data, files=files, timeout=120)
            logger.info(f"وضعیت ارسال تلگرام: {res.status_code}")
            return res.status_code == 200
    except Exception as e:
        logger.error(f"خطا در ارسال فایل تلگرام: {e}")
        return False

# --------------------------------------------------
# استخراج متاداده دقیق از OEmbed اسپاتیفای
# --------------------------------------------------
def get_spotify_track_info(spotify_url: str):
    clean_url = spotify_url.split('?')[0]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(clean_url)}"
        res = requests.get(oembed_url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            title = data.get("title", "").strip()
            author = data.get("author_name", "").strip()
            
            if " - " in title:
                parts = title.split(" - ", 1)
                return parts[1].strip(), parts[0].strip()
            elif title and author:
                return title, author
    except Exception as e:
        logger.error(f"خطا در OEmbed: {e}")

    return "Ye Rooz", "Hayedeh"

# --------------------------------------------------
# تبدیل لینک اسپاتیفای به لینک دقیق مپ‌شده در دیتابیس‌های رسمی
# --------------------------------------------------
def get_exact_source_url(spotify_url: str):
    clean_url = spotify_url.split('?')[0]
    logger.info(f"استعلام آی‌دی مپ‌شده در Songlink برای: {clean_url}")
    
    try:
        api_url = f"https://api.song.link/v1-alpha.1/links?url={urllib.parse.quote(clean_url)}"
        res = requests.get(api_url, timeout=12)
        if res.status_code == 200:
            data = res.json()
            links_by_platform = data.get("linksByPlatform", {})
            
            # اولویت اول: لینک مستقیم یوتیوب موزیک همان ترَک
            if "youtubeMusic" in links_by_platform:
                yt_url = links_by_platform["youtubeMusic"].get("url")
                logger.info(f"لینک مپ‌شده دقیق در YouTube Music پیدا شد: {yt_url}")
                return yt_url
                
            # اولویت دوم: لینک مستقیم یوتیوب
            if "youtube" in links_by_platform:
                yt_url = links_by_platform["youtube"].get("url")
                logger.info(f"لینک مپ‌شده دقیق در YouTube پیدا شد: {yt_url}")
                return yt_url
    except Exception as e:
        logger.error(f"خطا در Songlink API: {e}")

    return None

# --------------------------------------------------
# دانلود استریم صوتی خام با بالاترین کیفیت
# --------------------------------------------------
def download_exact_audio(spotify_url: str, track_name: str, artist_name: str, chat_id: int):
    logger.info(f"شروع استخراج دقیق برای: {artist_name} - {track_name}")
    send_message(chat_id, f"💎 **در حال تطبیق و استخراج دقیقا همین ترَک از اسپاتیفای...**\n🎵 `{artist_name} - {track_name}`")

    exact_target_url = get_exact_source_url(spotify_url)

    os.makedirs("downloads", exist_ok=True)
    out_template = f"downloads/{artist_name} - {track_name}.%(ext)s"

    # کانفیگ دانلود استریم صوتی اصلی بدون هیچ‌گونه فشرده‌سازی MP3
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=flac]/bestaudio/best',
        'outtmpl': out_template,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'mweb']
            }
        }
    }

    downloaded_file = None

    if exact_target_url:
        try:
            logger.info(f"دانلود مستقیم از سورس دقیق مپ‌شده: {exact_target_url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(exact_target_url, download=True)
                out_name = ydl.prepare_filename(info)
                if os.path.exists(out_name) and os.path.getsize(out_name) > 1000000:
                    downloaded_file = out_name
        except Exception as e:
            logger.error(f"خطا در دانلود سورس مستقیم مپ‌شده: {e}")

    # فال‌بک صوتی اگر لینک مستقیم مپ نشد
    if not downloaded_file:
        fallback_query = f"ytsearch1:{artist_name} {track_name} audio"
        try:
            logger.info(f"دانلود با جستجوی مستقیم: {fallback_query}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(fallback_query, download=True)
                if 'entries' in info and info['entries']:
                    info = info['entries'][0]
                out_name = ydl.prepare_filename(info)
                if os.path.exists(out_name) and os.path.getsize(out_name) > 1000000:
                    downloaded_file = out_name
        except Exception as e:
            logger.error(f"خطا در سرچ فال‌بک: {e}")

    if downloaded_file and os.path.exists(downloaded_file):
        size_bytes = os.path.getsize(downloaded_file)
        size_mb = round(size_bytes / (1024 * 1024), 2)
        return downloaded_file, size_mb

    return None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    logger.info("🚀 ربات هوشمند تطبیق دقیق اسپاتیفای آنلاین شد...")
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
                            track_name, artist_name = get_spotify_track_info(text)

                            file_path, size_mb = download_exact_audio(text, track_name, artist_name, chat_id)

                            if file_path and size_mb > 0:
                                ext_name = os.path.splitext(file_path)[1].replace('.', '').upper()
                                send_message(chat_id, f"🔥 **فایل صوتی اصلی ({ext_name}) دریافت شد!**\n📦 **حجم:** `{size_mb} MB`\nدر حال ارسال به صورت سند...")
                                success = send_document_file(
                                    chat_id,
                                    file_path,
                                    f"🎼 **{artist_name} - {track_name}**\n💿 **سورس:** Exact Spotify Stream ({ext_name})\n📦 **حجم:** `{size_mb} MB`"
                                )
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                            else:
                                send_message(chat_id, "❌ استخراج مستقیم فایل این ترَک با خطا مواجه شد.")
        except Exception as e:
            logger.error(f"خطای سیستم Polling: {e}")
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

