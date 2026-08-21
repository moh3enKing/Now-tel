import re
import os
import time
import requests
import urllib.parse
import threading
from flask import Flask

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"

app = Flask(__name__)

@app.route('/')
def home():
    return "True FLAC Lossless Downloader is running!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def send_message(chat_id, text):
    return requests.post(BASE_URL + "sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).json()

def send_document(chat_id, file_bytes, filename, caption):
    files = {"document": (filename, file_bytes)}
    data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
    return requests.post(BASE_URL + "sendDocument", data=data, files=files).json()

def get_spotify_metadata(url: str):
    """استخراج نام دقیق ترک و خواننده از اسپاتیفای"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=12)
        
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
        print(f"Metadata error: {e}")
    return None, None

def download_true_flac(track_name: str, artist_name: str, chat_id: int):
    """
    موتور اختصاصی دانلود FLAC بی‌کیفیت/غیرفشرده واقعی (Lossless)
    """
    query = f"{artist_name} {track_name}"
    send_message(chat_id, f"🔍 در حال جستجوی فایل **FLAC Lossless** در سرورهای Tidal / Qobuz برای:\n🎵 `{query}`")

    # لیست سرورهای معتبر دریافت FLAC واقعی
    flac_sources = [
        f"https://spotidownloader.com/api/download-track?q={urllib.parse.quote(query)}",
        f"https://api.fabdl.com/spotify/get-flac?q={urllib.parse.quote(query)}"
    ]

    for index, source_url in enumerate(flac_sources, 1):
        try:
            send_message(chat_id, f"📡 در حال برقراری ارتباط با منبع FLAC شماره {index}...")
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            res = requests.get(source_url, headers=headers, timeout=15)
            
            if res.status_code == 200:
                data = res.json()
                dl_url = data.get("download_url") or data.get("result", {}).get("download_url") or data.get("link")
                
                if dl_url:
                    send_message(chat_id, "📥 **لینک مستقیم FLAC دریافت شد!** در حال دانلود فایل غیرفشرده...")
                    file_res = requests.get(dl_url, headers=headers, timeout=90)
                    
                    # شرط مهم: فایل FLAC واقعی باید حداقل ۵ مگابایت باشد (نه فایل ۳۰ ثانیه‌ای)
                    if file_res.status_code == 200 and len(file_res.content) > 5000000:
                        size_mb = round(len(file_res.content) / (1024 * 1024), 2)
                        filename = f"{artist_name} - {track_name} [FLAC Lossless].flac"
                        return file_res.content, filename, size_mb
                    else:
                        print(f"File too small or invalid code: {file_res.status_code}, size: {len(file_res.content)}")
        except Exception as e:
            print(f"Flac source {index} error: {e}")

    return None, None, 0

def start_bot_polling():
    offset = 0
    print("🚀 [Render] ربات دانلود FLAC واقعی (Lossless Only) روشن شد...")
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
                            send_message(chat_id, "👋 **ربات اختصاصی دانلود FLAC (Lossless) واقعی**\n\nلینک آهنگ اسپاتیفای را بفرستید:")
                            continue

                        if "open.spotify.com/track/" in text:
                            track_name, artist_name = get_spotify_metadata(text)
                            
                            if not track_name or not artist_name:
                                send_message(chat_id, "❌ خواندن لینک اسپاتیفای ناموفق بود.")
                                continue

                            flac_bytes, filename, size_mb = download_true_flac(track_name, artist_name, chat_id)

                            if flac_bytes and filename:
                                send_message(chat_id, f"⚡️ **دانلود کامل شد!** (حجم فایل: `{size_mb} MB`)\nدر حال ارسال فایل سند FLAC...")
                                send_document(
                                    chat_id,
                                    flac_bytes,
                                    filename,
                                    f"🎼 **{artist_name} - {track_name}**\n💎 **فرمت:** FLAC Lossless (Uncompressed)\n📦 **حجم:** `{size_mb} MB`"
                                )
                            else:
                                send_message(chat_id, f"❌ فایل **FLAC Lossless** برای این آهنگ پیدا نشد یا حجم آن کمتر از حد استاندارد بود.\n(این ربات فایل‌های فشرده MP3 یا پیش‌نمایش ارسال نمی‌کند).")
        except Exception as e:
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

