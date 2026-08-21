import re
import os
import sys
import time
import requests
import traceback
import urllib.parse
import urllib3
import threading
from flask import Flask

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --------------------------------------------------
# تنظیمات اصلی ربات تلگرام
# --------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"

app = Flask(__name__)

@app.route('/')
def home():
    return "Lossless Deezer Engine Bot is online!"

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
# دانلود مستقیم از Deezer/Tidal Engine با Songlink
# --------------------------------------------------
def download_lossless_engine(spotify_url: str, track_name: str, artist_name: str, chat_id: int):
    query = f"{artist_name} {track_name}"
    send_message(chat_id, f"🔍 **جستجو در دیتابیس کیفیت اصلی (Lossless Engine)...**\n🎵 `{query}`")

    # ۱. استخراج مستقیم از API معتبر SpotifyToAudio
    endpoints = [
        f"https://api.fabdl.com/spotify/get?url={urllib.parse.quote(spotify_url)}",
        f"https://spotidownloader.com/api/download-track?q={urllib.parse.quote(query)}",
        f"https://api.vocalremover.org/spotify?url={urllib.parse.quote(spotify_url)}"
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }

    for index, url in enumerate(endpoints, 1):
        log_print(f"\n=================== TRY ENGINE {index} ===================")
        log_print(f"[ENGINE-{index}] Requesting: {url}")
        send_message(chat_id, f"📡 **ارتباط با سرور دانلود شماره {index}...**")

        try:
            res = requests.get(url, headers=headers, timeout=20, verify=False)
            log_print(f"[ENGINE-{index}] HTTP Status: {res.status_code}")
            log_print(f"[ENGINE-{index}] Response: {res.text[:300]}")

            if res.status_code == 200:
                data = res.json()
                
                # استخراج لینک دانلود مستقیم
                dl_url = None
                if "result" in data and isinstance(data["result"], dict):
                    dl_url = data["result"].get("download_url") or data["result"].get("gid")
                elif "download_url" in data:
                    dl_url = data["download_url"]
                elif "link" in data:
                    dl_url = data["link"]

                if dl_url:
                    log_print(f"[ENGINE-{index}] Direct Link: {dl_url}")
                    send_message(chat_id, "📥 **لینک فایل دریافت شد!** در حال دانلود فایل خام...")

                    file_res = requests.get(dl_url, headers=headers, timeout=120, verify=False)
                    content = file_res.content
                    size_mb = round(len(content) / (1024 * 1024), 2)

                    log_print(f"[ENGINE-{index}] Size: {size_mb} MB")

                    if len(content) > 1500000: # حداقل ۱.۵ مگابایت
                        ext = "flac" if "flac" in dl_url.lower() else "mp3"
                        filename = f"{artist_name} - {track_name}.{ext}"
                        log_print(f"[ENGINE-{index}-SUCCESS] Downloaded {filename} ({size_mb} MB)")
                        return content, filename, size_mb
        except Exception as e:
            log_print(f"[ENGINE-{index}-EX] {e}")

    return None, None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    log_print("🚀 [Render Direct Lossless Bot] Listening for updates...")
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
                            send_message(chat_id, "💎 **ربات اختصاصی دانلود موزیک با کیفیت بالا (Document)**\n\nلینک اسپاتیفای را ارسال کنید:")
                            continue

                        if "open.spotify.com/track/" in text:
                            log_print("--------------------------------------------------")
                            log_print(f"[NEW REQUEST] User ID: {chat_id} Link: {text}")

                            track_name, artist_name = get_spotify_track_info(text)
                            log_print(f"[PARSED] Track: '{track_name}' | Artist: '{artist_name}'")

                            if not track_name or not artist_name:
                                send_message(chat_id, "❌ استخراج لینک اسپاتیفای ناموفق بود.")
                                continue

                            audio_bytes, filename, size_mb = download_lossless_engine(text, track_name, artist_name, chat_id)

                            if audio_bytes and size_mb > 0:
                                send_message(chat_id, f"⚡️ **دانلود فایل با موفقیت انجام شد!**\n📦 **حجم فایل:** `{size_mb} MB`\nدر حال ارسال فایل سندی...")
                                send_document(
                                    chat_id,
                                    audio_bytes,
                                    filename,
                                    f"🎼 **{artist_name} - {track_name}**\n📦 **حجم:** `{size_mb} MB`"
                                )
                            else:
                                send_message(chat_id, "❌ متأسفانه دریافت فایل کامل با خطا مواجه شد.")
        except Exception as e:
            log_print(f"[POLLING ERROR] {e}")
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

