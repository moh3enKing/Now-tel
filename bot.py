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

# غیرفعال کردن هشدارهای SSL به خاطر verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --------------------------------------------------
# تنظیمات اصلی ربات تلگرام
# --------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"

app = Flask(__name__)

@app.route('/')
def home():
    return "Deezer HiFi FLAC Bot with SSL Fix is online!"

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
# دریافت فایل FLAC واقعی با بای‌پاس SSL
# --------------------------------------------------
def download_deezer_hifi_flac(track_name: str, artist_name: str, chat_id: int):
    query = f"{artist_name} {track_name}"
    send_message(chat_id, f"🔍 **استخراج فایل FLAC Lossless از دیتابیس Deezer HiFi...**\n🎵 `{query}`")

    # ۱. پیدا کردن ID تراک در Deezer
    deezer_id = None
    try:
        log_print(f"[DEEZER-SEARCH] Searching: {query}")
        search_url = f"https://api.deezer.com/search?q={urllib.parse.quote(query)}"
        res = requests.get(search_url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("data") and len(data["data"]) > 0:
                deezer_id = data["data"][0].get("id")
                log_print(f"[DEEZER-FOUND] Track ID: {deezer_id}")
    except Exception as e:
        log_print(f"[DEEZER-SEARCH-ERROR] {e}")

    if not deezer_id:
        log_print("[DEEZER-FAIL] No track ID found.")
        return None, None, 0

    # ۲. لیست گیت‌وی‌های مستقیم FLAC با verify=False برای رد کردن خطای SSL
    flac_sources = [
        f"https://api.deezloader.site/download/track/{deezer_id}?quality=flac",
        f"https://deezloader.app/api/download/track/{deezer_id}?quality=flac",
        f"https://api.dzzloader.site/track/{deezer_id}/flac"
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*"
    }

    for index, source_url in enumerate(flac_sources, 1):
        log_print(f"\n=================== FLAC TRY {index} (SSL BYPASS) ===================")
        log_print(f"[FLAC-TRY-{index}] URL: {source_url}")
        send_message(chat_id, f"📡 **در حال دریافت فایل FLAC واقعی از گیت‌وی {index}...**")

        try:
            # استفاده از verify=False جهت حل مشکل SSLCertVerificationError
            res = requests.get(source_url, headers=headers, timeout=45, verify=False, allow_redirects=True)
            log_print(f"[FLAC-TRY-{index}] Status Code: {res.status_code}")

            if res.status_code == 200:
                content = res.content
                size_mb = round(len(content) / (1024 * 1024), 2)
                log_print(f"[FLAC-TRY-{index}] Downloaded Content Size: {size_mb} MB")

                # اگر پاسخ لینک JSON بود
                if "application/json" in res.headers.get("Content-Type", ""):
                    try:
                        jdata = res.json()
                        dl_link = jdata.get("url") or jdata.get("download_url") or jdata.get("link")
                        if dl_link:
                            log_print(f"[FLAC-TRY-{index}] Direct JSON link: {dl_link}")
                            res = requests.get(dl_link, headers=headers, timeout=90, verify=False)
                            content = res.content
                            size_mb = round(len(content) / (1024 * 1024), 2)
                    except Exception as e_json:
                        log_print(f"[FLAC-JSON-ERR] {e_json}")

                # فایل FLAC واقعی باید بالای ۳ مگابایت باشد
                if len(content) > 3000000:
                    filename = f"{artist_name} - {track_name} [FLAC].flac"
                    log_print(f"[FLAC-SUCCESS] Successfully obtained FLAC! Size: {size_mb} MB")
                    return content, filename, size_mb
                else:
                    log_print(f"[FLAC-FAIL] Size too small: {size_mb} MB")
        except Exception as e:
            log_print(f"[FLAC-TRY-{index}-EX] Exception: {e}")

    return None, None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    log_print("🚀 [Render Deezer FLAC Bot SSL-Fix] Listening for updates...")
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
                            send_message(chat_id, "💎 **ربات اختصاصی دانلود فایل Lossless / FLAC**\n\nلینک اسپاتیفای را ارسال کنید:")
                            continue

                        if "open.spotify.com/track/" in text:
                            log_print("--------------------------------------------------")
                            log_print(f"[NEW REQUEST] User ID: {chat_id} Link: {text}")

                            track_name, artist_name = get_spotify_track_info(text)
                            log_print(f"[PARSED] Track: '{track_name}' | Artist: '{artist_name}'")

                            if not track_name or not artist_name:
                                send_message(chat_id, "❌ استخراج لینک اسپاتیفای ناموفق بود.")
                                continue

                            flac_bytes, filename, size_mb = download_deezer_hifi_flac(track_name, artist_name, chat_id)

                            if flac_bytes and size_mb > 0:
                                send_message(chat_id, f"⚡️ **فایل FLAC Lossless با موفقیت دانلود شد!**\n📦 **حجم فایل:** `{size_mb} MB`\nدر حال ارسال به صورت سند (Document)...")
                                send_document(
                                    chat_id,
                                    flac_bytes,
                                    filename,
                                    f"🎼 **{artist_name} - {track_name}**\n💎 **کیفیت:** FLAC Lossless 16-Bit\n📦 **حجم:** `{size_mb} MB`"
                                )
                            else:
                                send_message(chat_id, "❌ متأسفانه دریافت فایل FLAC با خطا مواجه شد.")
        except Exception as e:
            log_print(f"[POLLING ERROR] {e}")
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

