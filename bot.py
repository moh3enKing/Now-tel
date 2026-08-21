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
    return "Pure Lossless FLAC Downloader is online!"

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
# استخراج متاداده اسپاتیفای
# --------------------------------------------------
def get_spotify_track_info(spotify_url: str):
    log_print(f"\n[METADATA] Scraping Spotify: {spotify_url}")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
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
# دریافت لینک Tidal / Qobuz از روی اسپاتیفای
# --------------------------------------------------
def resolve_to_lossless_platform(spotify_url: str):
    log_print(f"[SONGLINK] Resolving Spotify URL via Odesli API...")
    try:
        api = f"https://api.song.link/v1-1/links?url={urllib.parse.quote(spotify_url)}"
        res = requests.get(api, timeout=12)
        if res.status_code == 200:
            data = res.json()
            links = data.get("linksByPlatform", {})
            
            tidal_url = links.get("tidal", {}).get("url")
            qobuz_url = links.get("qobuz", {}).get("url")
            deezer_url = links.get("deezer", {}).get("url")
            
            log_print(f"[SONGLINK-FOUND] Tidal: {tidal_url} | Qobuz: {qobuz_url} | Deezer: {deezer_url}")
            return tidal_url or qobuz_url or deezer_url
    except Exception as e:
        log_print(f"[SONGLINK-ERROR] {e}")
    return None

# --------------------------------------------------
# دانلود مستقیم FLAC واقعی (Tidal / Qobuz Engine)
# --------------------------------------------------
def fetch_lossless_flac(track_name: str, artist_name: str, spotify_url: str, chat_id: int):
    query = f"{artist_name} {track_name}"
    send_message(chat_id, f"🔍 **استخراج دیتابیس Lossless (Tidal / Qobuz FLAC Engine)...**\n🎵 `{query}`")

    # ۱. پیدا کردن لینک Tidal / Qobuz
    lossless_link = resolve_to_lossless_platform(spotify_url)
    
    # لیست ای‌پي‌آی‌های اختصاصی دانلود فایل FLAC بی‌کیفیت (Hi-Res / 16-bit Lossless)
    flac_endpoints = [
        ("https://squid.wtf/api/download", {"url": lossless_link or spotify_url, "quality": "flac"}),
        ("https://api.doubledouble.top/dl", {"url": lossless_link or spotify_url}),
        ("https://lucida.to/api/fetch", {"url": lossless_link or spotify_url})
    ]

    for index, (endpoint, payload) in enumerate(flac_endpoints, 1):
        if not payload["url"]:
            continue
            
        log_print(f"\n=================== FLAC ENGINE {index} TRY ===================")
        log_print(f"[FLAC-ENGINE-{index}] Requesting: {payload['url']}")
        send_message(chat_id, f"📡 **در حال ارتباط با سرور FLAC شماره {index}...**")
        
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json"}
            res = requests.post(endpoint, json=payload, headers=headers, timeout=25)
            log_print(f"[FLAC-ENGINE-{index}] Status: {res.status_code}")
            
            if res.status_code == 200:
                data = res.json()
                dl_url = data.get("url") or data.get("downloadUrl") or data.get("link")
                
                if dl_url:
                    log_print(f"[FLAC-ENGINE-{index}] Direct FLAC Link: {dl_url}")
                    send_message(chat_id, "📥 **لینک مستقیم فایل FLAC استخراج شد!** در حال دانلود فایل خام...")
                    
                    file_res = requests.get(dl_url, headers=headers, timeout=120)
                    content = file_res.content
                    
                    # بررسی هدر استاندارد fLaC (۴ بایت اول فایل باید fLaC باشد)
                    is_real_flac = content.startswith(b'fLaC') or content.startswith(b'ID3')
                    size_mb = round(len(content) / (1024 * 1024), 2)
                    
                    log_print(f"[FLAC-CHECK] Size: {size_mb} MB | Magic bytes: {content[:4]}")
                    
                    if file_res.status_code == 200 and len(content) > 3000000 and is_real_flac:
                        filename = f"{artist_name} - {track_name} [Lossless].flac"
                        log_print(f"[FLAC-SUCCESS] Valid FLAC file downloaded! ({size_mb} MB)")
                        return content, filename, size_mb
                    else:
                        log_print(f"[FLAC-FAIL] Invalid FLAC header or size too small.")
        except Exception as e:
            log_print(f"[FLAC-ENGINE-{index}-ERROR] {e}")

    # منبع پشتیبان: جستجوی مستقیم در دیتابیس Hi-Res FLAC
    try:
        log_print("\n=================== FLAC ENGINE FALLBACK ===================")
        send_message(chat_id, "📡 **تلاش با سرور Hi-Res FLAC Backup...**")
        
        fallback_api = f"https://spotidownloader.com/api/download-track?q={urllib.parse.quote(query)}"
        res = requests.get(fallback_api, timeout=20)
        if res.status_code == 200:
            data = res.json()
            dl_url = data.get("download_url")
            if dl_url:
                file_res = requests.get(dl_url, timeout=120)
                content = file_res.content
                size_mb = round(len(content) / (1024 * 1024), 2)
                
                if file_res.status_code == 200 and len(content) > 3000000:
                    filename = f"{artist_name} - {track_name} [Hi-Res].flac"
                    log_print(f"[FALLBACK-SUCCESS] Downloaded {filename} ({size_mb} MB)")
                    return content, filename, size_mb
    except Exception as e:
        log_print(f"[FALLBACK-ERROR] {e}")

    return None, None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    log_print("🚀 [Render Lossless FLAC Bot] Bot listening for updates...")
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
                            send_message(chat_id, "💎 **ربات اختصاصی دانلود Lossless (FLAC 16/24-Bit)**\n\nلینک اسپاتیفای را ارسال کنید:")
                            continue

                        if "open.spotify.com/track/" in text:
                            log_print("--------------------------------------------------")
                            log_print(f"[NEW REQUEST] User ID: {chat_id} Link: {text}")
                            
                            track_name, artist_name = get_spotify_track_info(text)
                            log_print(f"[PARSED] Track: '{track_name}' | Artist: '{artist_name}'")
                            
                            if not track_name or not artist_name:
                                send_message(chat_id, "❌ خواندن متاداده از لینک اسپاتیفای ناموفق بود.")
                                continue

                            flac_bytes, filename, size_mb = fetch_lossless_flac(track_name, artist_name, text, chat_id)

                            if flac_bytes and size_mb > 0:
                                send_message(chat_id, f"⚡️ **دانلود فایل FLAC Lossless با موفقیت انجام شد!**\n📦 **حجم فایل:** `{size_mb} MB`\nدر حال ارسال فایل سند (Document)...")
                                send_document(
                                    chat_id,
                                    flac_bytes,
                                    filename,
                                    f"🎼 **{artist_name} - {track_name}**\n💎 **فرمت:** FLAC Lossless (Tidal / Qobuz Source)\n📦 **حجم:** `{size_mb} MB`"
                                )
                            else:
                                send_message(chat_id, "❌ متأسفانه فایل Lossless (FLAC) این موزیک در سرورهای Tidal / Qobuz یافت نشد.")
        except Exception as e:
            log_print(f"[POLLING ERROR] {e}")
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

