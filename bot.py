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
    return "Spotify Bot with Live Terminal Logs is running!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# تابع چاپ فوری در ترمینال Render (بدون بافر)
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
# استخراج اطلاعات لینک اسپاتیفای
# --------------------------------------------------
def get_spotify_track_info(spotify_url: str):
    log_print(f"\n[DEBUG-SCRAPE] Starting Spotify scraping for: {spotify_url}")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(spotify_url, headers=headers, timeout=12)
        log_print(f"[DEBUG-SCRAPE] Response status code: {res.status_code}")
        
        m = re.search(r'<title>(.*?) - song and lyrics by (.*?) \| Spotify</title>', res.text)
        if m:
            log_print(f"[DEBUG-SCRAPE] Match 1: {m.group(1)} | {m.group(2)}")
            return m.group(1).strip(), m.group(2).strip()
            
        m2 = re.search(r'<title>(.*?) - Single by (.*?) \| Spotify</title>', res.text)
        if m2:
            log_print(f"[DEBUG-SCRAPE] Match 2: {m2.group(1)} | {m2.group(2)}")
            return m2.group(1).strip(), m2.group(2).strip()
            
        m3 = re.search(r'<title>(.*?) - song by (.*?) \| Spotify</title>', res.text)
        if m3:
            log_print(f"[DEBUG-SCRAPE] Match 3: {m3.group(1)} | {m3.group(2)}")
            return m3.group(1).strip(), m3.group(2).strip()
            
        log_print("[DEBUG-SCRAPE] No match pattern found in HTML title!")
    except Exception as e:
        log_print(f"[DEBUG-SCRAPE-ERROR] Failed scraping: {e}")
        log_print(traceback.format_exc())
    return None, None

def download_full_hq_audio(spotify_url: str, track_name: str, artist_name: str, chat_id: int):
    query = f"{artist_name} {track_name}"
    send_message(chat_id, f"🔍 **ارتباط با سرورهای دانلود مستقیم...**\n🎵 `{query}`")

    # ----------------------------------------------------
    # ENGINE 1: Spotisongdownloader
    # ----------------------------------------------------
    log_print("\n=================== ENGINE 1 TRY ===================")
    log_print(f"[ENGINE-1] Target URL: {spotify_url}")
    try:
        send_message(chat_id, "📡 **امتحان سرور ۱ (Spotisong Engine)...**")
        api_url = "https://spotisongdownloader.com/api/composer/spotify/download_song.php"
        payload = {"url": spotify_url}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        res = requests.post(api_url, data=payload, headers=headers, timeout=20)
        log_print(f"[ENGINE-1] HTTP Status: {res.status_code}")
        log_print(f"[ENGINE-1] Response Raw Text: {res.text[:300]}")
        
        if res.status_code == 200:
            data = res.json()
            dl_url = data.get("dlink") or data.get("song")
            log_print(f"[ENGINE-1] Parsed Download URL: {dl_url}")
            
            if dl_url:
                send_message(chat_id, "⚡️ **لینک دانلود دریافت شد!** در حال دریافت فایل...")
                file_res = requests.get(dl_url, headers=headers, timeout=90)
                log_print(f"[ENGINE-1-FILE] Status: {file_res.status_code}, Length: {len(file_res.content)} bytes")
                
                if file_res.status_code == 200 and len(file_res.content) > 1500000:
                    size_mb = round(len(file_res.content) / (1024 * 1024), 2)
                    filename = f"{artist_name} - {track_name}.mp3"
                    log_print(f"[ENGINE-1] SUCCESS! File Size: {size_mb} MB")
                    return file_res.content, filename, size_mb
                else:
                    log_print("[ENGINE-1-FAIL] File size too small (< 1.5MB).")
    except Exception as e:
        log_print(f"[ENGINE-1-EXCEPTION] Error: {e}")
        log_print(traceback.format_exc())

    # ----------------------------------------------------
    # ENGINE 2: SpotiDownloader API
    # ----------------------------------------------------
    log_print("\n=================== ENGINE 2 TRY ===================")
    log_print(f"[ENGINE-2] Search Query: {query}")
    try:
        send_message(chat_id, "📡 **امتحان سرور ۲ (Spotidownloader Engine)...**")
        search_api = f"https://spotidownloader.com/api/download-track?q={urllib.parse.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(search_api, headers=headers, timeout=20)
        log_print(f"[ENGINE-2] HTTP Status: {res.status_code}")
        log_print(f"[ENGINE-2] Response Raw Text: {res.text[:300]}")
        
        if res.status_code == 200:
            data = res.json()
            dl_url = data.get("download_url")
            log_print(f"[ENGINE-2] Parsed Download URL: {dl_url}")
            
            if dl_url:
                file_res = requests.get(dl_url, headers=headers, timeout=90)
                log_print(f"[ENGINE-2-FILE] Status: {file_res.status_code}, Length: {len(file_res.content)} bytes")
                
                if file_res.status_code == 200 and len(file_res.content) > 1500000:
                    size_mb = round(len(file_res.content) / (1024 * 1024), 2)
                    filename = f"{artist_name} - {track_name} [320k].mp3"
                    log_print(f"[ENGINE-2] SUCCESS! File Size: {size_mb} MB")
                    return file_res.content, filename, size_mb
                else:
                    log_print("[ENGINE-2-FAIL] File size too small (< 1.5MB).")
    except Exception as e:
        log_print(f"[ENGINE-2-EXCEPTION] Error: {e}")
        log_print(traceback.format_exc())

    # ----------------------------------------------------
    # ENGINE 3: Cobalt Engine
    # ----------------------------------------------------
    log_print("\n=================== ENGINE 3 TRY ===================")
    log_print(f"[ENGINE-3] Target URL: {spotify_url}")
    try:
        send_message(chat_id, "📡 **امتحان سرور ۳ (Cobalt Engine)...**")
        cobalt_url = "https://co.wuk.sh/api/json"
        payload = {"url": spotify_url, "aFormat": "mp3"}
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
        res = requests.post(cobalt_url, json=payload, headers=headers, timeout=20)
        log_print(f"[ENGINE-3] HTTP Status: {res.status_code}")
        log_print(f"[ENGINE-3] Response Raw Text: {res.text[:300]}")
        
        if res.status_code == 200:
            data = res.json()
            dl_url = data.get("url")
            log_print(f"[ENGINE-3] Parsed Download URL: {dl_url}")
            
            if dl_url:
                file_res = requests.get(dl_url, timeout=90)
                log_print(f"[ENGINE-3-FILE] Status: {file_res.status_code}, Length: {len(file_res.content)} bytes")
                
                if file_res.status_code == 200 and len(file_res.content) > 1500000:
                    size_mb = round(len(file_res.content) / (1024 * 1024), 2)
                    filename = f"{artist_name} - {track_name}.mp3"
                    log_print(f"[ENGINE-3] SUCCESS! File Size: {size_mb} MB")
                    return file_res.content, filename, size_mb
    except Exception as e:
        log_print(f"[ENGINE-3-EXCEPTION] Error: {e}")
        log_print(traceback.format_exc())

    log_print(f"\n[SUMMARY] ALL ENGINES FAILED FOR QUERY: {query}\n")
    return None, None, 0

def start_bot_polling():
    offset = 0
    log_print("🚀 [Render Live Terminal Debugger] Bot listening for updates...")
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
                            send_message(chat_id, "👋 **ربات دانلود موزیک اسپاتیفای (ورژن دیباگر زنده)**\n\nلینک موزیک را ارسال کنید:")
                            continue

                        if "open.spotify.com/track/" in text:
                            log_print("--------------------------------------------------")
                            log_print(f"[NEW REQUEST] User ID: {chat_id} Sent Link: {text}")
                            
                            track_name, artist_name = get_spotify_track_info(text)
                            log_print(f"[PARSED METADATA] Track: '{track_name}' | Artist: '{artist_name}'")
                            
                            if not track_name:
                                send_message(chat_id, "❌ استخراج لینک اسپاتیفای ناموفق بود.")
                                continue

                            audio_bytes, filename, size_mb = download_full_hq_audio(text, track_name, artist_name, chat_id)

                            if audio_bytes and filename:
                                send_message(chat_id, f"⚡️ **دانلود آهنگ با موفقیت انجام شد!**\n📦 **حجم:** `{size_mb} MB`\nدر حال ارسال فایل...")
                                send_document(
                                    chat_id,
                                    audio_bytes,
                                    filename,
                                    f"🎼 **{artist_name} - {track_name}**\n📦 **حجم:** `{size_mb} MB`"
                                )
                            else:
                                send_message(chat_id, "❌ خطایی در استخراج فایل کامل از سرورها رخ داد.")
        except Exception as e:
            log_print(f"[POLLING ERROR] {e}")
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

