import re
import os
import sys
import time
import logging
import urllib.parse
import threading
import subprocess
import requests
from flask import Flask

# --------------------------------------------------
# تنظیمات سیستم لاگ‌گیری دقیق در ترمینال Render
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
    return "Direct Audio Downloader Server is LIVE!"

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

def send_document(chat_id, file_path_or_bytes, filename, caption):
    try:
        if isinstance(file_path_or_bytes, bytes):
            files = {"document": (filename, file_path_or_bytes)}
            data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
            requests.post(BASE_URL + "sendDocument", data=data, files=files)
        else:
            with open(file_path_or_bytes, "rb") as f:
                files = {"document": (filename, f.read())}
            data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
            requests.post(BASE_URL + "sendDocument", data=data, files=files)
    except Exception as e:
        logger.error(f"Telegram Send Doc Error: {e}")

# --------------------------------------------------
# استخراج دقیق متاداده از اسپاتیفای
# --------------------------------------------------
def get_spotify_track_info(spotify_url: str):
    logger.info(f"Extracting metadata for Spotify URL: {spotify_url}")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(spotify_url, headers=headers, timeout=12)
        
        m = re.search(r'<title>(.*?) - song and lyrics by (.*?) \| Spotify</title>', res.text)
        if m: return m.group(1).strip(), m.group(2).strip()
            
        m2 = re.search(r'<title>(.*?) - Single by (.*?) \| Spotify</title>', res.text)
        if m2: return m2.group(1).strip(), m2.group(2).strip()
            
        m3 = re.search(r'<title>(.*?) - song by (.*?) \| Spotify</title>', res.text)
        if m3: return m3.group(1).strip(), m3.group(2).strip()
    except Exception as e:
        logger.error(f"Spotify Scrape Error: {e}")
    return None, None

# --------------------------------------------------
# موتور ۱: دانلود مستقیم 320kbps از CDNهای اصلی (Akamai CDN)
# --------------------------------------------------
def download_from_direct_cdn(track_name: str, artist_name: str, chat_id: int):
    query = f"{artist_name} {track_name}"
    logger.info(f"--- ENGINE 1: Direct CDN Search for '{query}' ---")
    send_message(chat_id, f"🔍 **جستجو در CDN مستقیم کیفیت ۳۲۰...**\n🎵 `{query}`")

    # لیست اندپکوینت‌های مستقیم CDN بدون تحریم آی‌پی
    api_endpoints = [
        f"https://saavn.dev/api/search/songs?query={urllib.parse.quote(query)}",
        f"https://saavn.me/search/songs?query={urllib.parse.quote(query)}",
        f"https://jiosaavn-api-murex.vercel.app/api/search/songs?query={urllib.parse.quote(query)}"
    ]

    for api_url in api_endpoints:
        try:
            res = requests.get(api_url, timeout=12)
            if res.status_code == 200:
                json_data = res.json()
                results = json_data.get("data", {}).get("results", []) or json_data.get("results", [])
                
                if results and len(results) > 0:
                    first_match = results[0]
                    dl_urls = first_match.get("downloadUrl", [])
                    
                    if dl_urls and isinstance(dl_urls, list):
                        # گرفتن بالاترین کیفیت موجود (320kbps)
                        best_link = dl_urls[-1].get("url") if isinstance(dl_urls[-1], dict) else dl_urls[-1]
                        
                        if best_link:
                            logger.info(f"[CDN MATCH] Found link: {best_link}")
                            send_message(chat_id, "📥 **فایل با کیفیت ۳۲۰ یافت شد! در حال دانلود...**")
                            
                            file_res = requests.get(best_link, timeout=90)
                            content = file_res.content
                            size_mb = round(len(content) / (1024 * 1024), 2)
                            
                            if len(content) > 1500000: # حداقل ۱.۵ مگابایت
                                filename = f"{artist_name} - {track_name} [320k].mp3"
                                logger.info(f"[CDN SUCCESS] Downloaded {filename} ({size_mb} MB)")
                                return content, filename, size_mb
        except Exception as e:
            logger.error(f"[CDN EXCEPTION] {e}")

    return None, None, 0

# --------------------------------------------------
# موتور ۲: دانلود مستقیم از SoundCloud HQ (پشتیبان نهایی)
# --------------------------------------------------
def download_from_soundcloud_engine(track_name: str, artist_name: str, chat_id: int):
    query = f"{artist_name} {track_name}"
    logger.info(f"--- ENGINE 2: SoundCloud HQ Search for '{query}' ---")
    send_message(chat_id, f"📡 **تلاش با موتور SoundCloud HQ...**")

    output_filename = f"{artist_name} - {track_name}.mp3"
    if os.path.exists(output_filename):
        os.remove(output_filename)

    try:
        cmd = [
            sys.executable, "-m", "yt_dlp",
            f"scsearch1:{query}",
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "-o", output_filename,
            "--no-playlist"
        ]
        
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
        
        if os.path.exists(output_filename):
            size_bytes = os.path.getsize(output_filename)
            size_mb = round(size_bytes / (1024 * 1024), 2)
            
            if size_mb > 1.2:
                logger.info(f"[SOUNDCLOUD SUCCESS] Downloaded {output_filename} ({size_mb} MB)")
                return output_filename, size_mb
            else:
                os.remove(output_filename)
    except Exception as e:
        logger.error(f"[SOUNDCLOUD EXCEPTION] {e}")

    return None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    logger.info("🚀 [Render Direct Audio Bot] Listening for Telegram updates...")
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
                            send_message(chat_id, "👋 **سلام!** لینک موزیک اسپاتیفای را بفرستید تا فایل صوتی کیفیت بالا براتون ارسال بشه:")
                            continue

                        if "open.spotify.com/track/" in text:
                            logger.info("--------------------------------------------------")
                            logger.info(f"NEW REQUEST from {chat_id}: {text}")

                            track_name, artist_name = get_spotify_track_info(text)
                            logger.info(f"Parsed Metadata -> Track: '{track_name}', Artist: '{artist_name}'")

                            if not track_name or not artist_name:
                                send_message(chat_id, "❌ خواندن لینک اسپاتیفای ناموفق بود.")
                                continue

                            # ۱. امتحان موتور اول (CDN مستقیم)
                            audio_bytes, filename, size_mb = download_from_direct_cdn(track_name, artist_name, chat_id)

                            # ۲. اگر موتور اول نداشت، امتحان موتور دوم (SoundCloud HQ)
                            if not audio_bytes:
                                file_path, size_mb = download_from_soundcloud_engine(track_name, artist_name, chat_id)
                                if file_path and size_mb > 0:
                                    send_message(chat_id, f"⚡️ **دانلود کامل شد!**\n📦 **حجم:** `{size_mb} MB`\nدر حال ارسال فایل سندی (Document)...")
                                    send_document(
                                        chat_id,
                                        file_path,
                                        f"{artist_name} - {track_name}.mp3",
                                        f"🎼 **{artist_name} - {track_name}**\n🔊 **کیفیت:** 320kbps HQ\n📦 **حجم:** `{size_mb} MB`"
                                    )
                                    if os.path.exists(file_path):
                                        os.remove(file_path)
                                    continue
                            else:
                                send_message(chat_id, f"⚡️ **دانلود کامل شد!**\n📦 **حجم:** `{size_mb} MB`\nدر حال ارسال فایل سندی (Document)...")
                                send_document(
                                    chat_id,
                                    audio_bytes,
                                    filename,
                                    f"🎼 **{artist_name} - {track_name}**\n🔊 **کیفیت:** 320kbps HQ\n📦 **حجم:** `{size_mb} MB`"
                                )
                                continue

                            send_message(chat_id, "❌ متأسفانه دریافت فایل صوتی این تراک ناموفق بود.")
        except Exception as e:
            logger.error(f"Polling Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

