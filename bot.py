import re
import os
import sys
import time
import requests
import traceback
import urllib.parse
import threading
from flask import Flask

# --------------------------------------------------
# تنظیمات اصلی ربات تلگرام
# --------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"

app = Flask(__name__)

@app.route('/')
def home():
    return "Fixed Cobalt FLAC Bot is online!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def log_print(msg):
    print(msg, flush=True)

# --------------------------------------------------
# توابع ارسال پیام تلگرام
# --------------------------------------------------
def send_message(chat_id, text):
    return requests.post(BASE_URL + "sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).json()

def send_document(chat_id, file_bytes, filename, caption):
    files = {"document": (filename, file_bytes)}
    data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
    return requests.post(BASE_URL + "sendDocument", data=data, files=files).json()

# --------------------------------------------------
# استخراج متاداده از اسپاتیفای
# --------------------------------------------------
def get_spotify_track_info(spotify_url: str):
    log_print(f"\n[METADATA] Scraping Spotify: {spotify_url}")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(spotify_url, headers=headers, timeout=12)
        
        m = re.search(r'<title>(.*?) - song and lyrics by (.*?) \| Spotify</title>', res.text)
        if m:
            return m.group(1).strip(), m.group(2).strip()
            
        m2 = re.search(r'<title>(.*?) - Single by (.*?) \| Spotify</title>', res.text)
        if m2:
            return m2.group(1).strip(), m2.group(2).strip()
            
        m3 = re.search(r'<title>(.*?) - song by (.*?) \| Spotify</title>', res.text)
        if m3:
            return m3.group(1).strip(), m3.group(2).strip()
    except Exception as e:
        log_print(f"[METADATA-ERROR] {e}")
    return None, None

# --------------------------------------------------
# دانلود FLAC از API اصلاح‌شده Cobalt
# --------------------------------------------------
def download_cobalt_flac(spotify_url: str, track_name: str, artist_name: str, chat_id: int):
    send_message(chat_id, f"🔍 **استخراج فایل FLAC Lossless از سرور Cobalt...**\n🎵 `{artist_name} - {track_name}`")

    # ۱. استفاده از اندپکوینت اصلی Cobalt API
    cobalt_url = "https://api.cobalt.tools/"
    
    payload = {
        "url": spotify_url,
        "videoQuality": "max",
        "audioFormat": "flac",
        "downloadMode": "audio"
    }

    # اضافه کردن هدرهای کامل جهت جلوگیری از ارور jwt.missing
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Origin": "https://cobalt.tools",
        "Referer": "https://cobalt.tools/"
    }

    log_print(f"\n=================== COBALT API REQUEST ===================")
    log_print(f"[COBALT] Target: {cobalt_url}")
    send_message(chat_id, "📡 **ارتباط با Cobalt API اصلی...**")

    try:
        res = requests.post(cobalt_url, json=payload, headers=headers, timeout=25)
        log_print(f"[COBALT] HTTP Status: {res.status_code}")
        log_print(f"[COBALT] Response Text: {res.text[:400]}")

        if res.status_code == 200:
            data = res.json()
            dl_url = data.get("url") or data.get("picker", [{}])[0].get("url")

            if dl_url:
                log_print(f"[COBALT] Direct FLAC Link: {dl_url}")
                send_message(chat_id, "📥 **لینک دانلود مستقیم FLAC استخراج شد!** در حال دریافت فایل...")

                file_res = requests.get(dl_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
                content = file_res.content
                size_mb = round(len(content) / (1024 * 1024), 2)

                log_print(f"[COBALT] File Size: {size_mb} MB")

                if len(content) > 3000000:
                    filename = f"{artist_name} - {track_name} [FLAC].flac"
                    log_print(f"[COBALT-SUCCESS] Valid FLAC Downloaded! ({size_mb} MB)")
                    return content, filename, size_mb
    except Exception as e:
        log_print(f"[COBALT-EX] Exception: {e}")

    # ۲. منبع رزرو: SpotiFlyer / Double API
    try:
        log_print(f"\n=================== FALLBACK FLAC API ===================")
        send_message(chat_id, "📡 **امتحان سرور رزرو FLAC...**")
        
        query = f"{artist_name} {track_name}"
        search_api = f"https://spotidownloader.com/api/download-track?q={urllib.parse.quote(query)}"
        res = requests.get(search_api, timeout=20)
        
        if res.status_code == 200:
            data = res.json()
            dl_url = data.get("download_url")
            if dl_url:
                file_res = requests.get(dl_url, timeout=120)
                content = file_res.content
                size_mb = round(len(content) / (1024 * 1024), 2)
                
                if len(content) > 3000000:
                    filename = f"{artist_name} - {track_name} [Lossless].flac"
                    log_print(f"[FALLBACK-SUCCESS] Downloaded {size_mb} MB")
                    return content, filename, size_mb
    except Exception as e:
        log_print(f"[FALLBACK-EX] {e}")

    return None, None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    log_print("🚀 [Render Fixed Cobalt FLAC Bot] Listening for updates...")
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
                            send_message(chat_id, "💎 **ربات دانلود اختصاصی FLAC (Lossless)**\n\nلینک اسپاتیفای را ارسال کنید:")
                            continue

                        if "open.spotify.com/track/" in text:
                            log_print("--------------------------------------------------")
                            log_print(f"[NEW REQUEST] User ID: {chat_id} Link: {text}")

                            track_name, artist_name = get_spotify_track_info(text)
                            log_print(f"[PARSED] Track: '{track_name}' | Artist: '{artist_name}'")

                            if not track_name or not artist_name:
                                send_message(chat_id, "❌ استخراج لینک اسپاتیفای ناموفق بود.")
                                continue

                            flac_bytes, filename, size_mb = download_cobalt_flac(text, track_name, artist_name, chat_id)

                            if flac_bytes and size_mb > 0:
                                send_message(chat_id, f"⚡️ **فایل FLAC Lossless با موفقیت دانلود شد!**\n📦 **حجم فایل:** `{size_mb} MB`\nدر حال ارسال به صورت سند (Document)...")
                                send_document(
                                    chat_id,
                                    flac_bytes,
                                    filename,
                                    f"🎼 **{artist_name} - {track_name}**\n💎 **کیفیت:** FLAC Lossless\n📦 **حجم:** `{size_mb} MB`"
                                )
                            else:
                                send_message(chat_id, "❌ متأسفانه این موزیک در سرورهای Lossless FLAC یافت نشد.")
        except Exception as e:
            log_print(f"[POLLING ERROR] {e}")
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

