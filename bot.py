import re
import os
import time
import requests
import urllib.parse
import threading
from flask import Flask

# --------------------------------------------------
# توکن ربات تلگرام شما
# --------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"

app = Flask(__name__)

@app.route('/')
def home():
    return "Spotify HQ Full Downloader is running!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def send_message(chat_id, text):
    return requests.post(BASE_URL + "sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).json()

def send_document(chat_id, file_bytes, filename, caption):
    files = {"document": (filename, file_bytes)}
    data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
    return requests.post(BASE_URL + "sendDocument", data=data, files=files).json()

def get_spotify_track_info(spotify_url: str):
    """استخراج دقیق عنوان و خواننده از صفحه اسپاتیفای"""
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
        print(f"Error scraping Spotify link: {e}")
    return None, None

def download_full_hq_audio(spotify_url: str, track_name: str, artist_name: str, chat_id: int):
    """
    دانلود فایل کامل آهنگ با حداکثر کیفیت واقعی 320kbps / Lossless
    """
    send_message(chat_id, f"🔍 **ارتباط با سرورهای دانلود مستقیم...**\n🎵 `{artist_name} - {track_name}`")

    # API 1: Spotisongdownloader Direct Engine
    try:
        send_message(chat_id, "📡 **امتحان سرور اول (Spotisong Engine)...**")
        api_url = "https://spotisongdownloader.com/api/composer/spotify/download_song.php"
        payload = {"url": spotify_url}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        res = requests.post(api_url, data=payload, headers=headers, timeout=20)
        if res.status_code == 200:
            data = res.json()
            dl_url = data.get("dlink") or data.get("song")
            if dl_url:
                send_message(chat_id, "⚡️ **لینک مستقیم دریافت شد!** در حال دریافت فایل کامل...")
                file_res = requests.get(dl_url, headers=headers, timeout=90)
                if file_res.status_code == 200 and len(file_res.content) > 2000000: # حداقل ۲ مگابایت (کامل)
                    size_mb = round(len(file_res.content) / (1024 * 1024), 2)
                    filename = f"{artist_name} - {track_name}.mp3"
                    return file_res.content, filename, size_mb
    except Exception as e:
        print(f"Engine 1 failed: {e}")

    # API 2: Soundcloud / High Quality YouTube Search Engine Fallback
    try:
        send_message(chat_id, "📡 **امتحان سرور دوم (HQ Audio Engine)...**")
        query = f"{artist_name} {track_name}"
        search_api = f"https://spotidownloader.com/api/download-track?q={urllib.parse.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(search_api, headers=headers, timeout=20)
        if res.status_code == 200:
            data = res.json()
            dl_url = data.get("download_url")
            if dl_url:
                file_res = requests.get(dl_url, headers=headers, timeout=90)
                if file_res.status_code == 200 and len(file_res.content) > 2000000:
                    size_mb = round(len(file_res.content) / (1024 * 1024), 2)
                    filename = f"{artist_name} - {track_name} [320kbps].mp3"
                    return file_res.content, filename, size_mb
    except Exception as e:
        print(f"Engine 2 failed: {e}")

    return None, None, 0

def start_bot_polling():
    offset = 0
    print("🚀 [Render] ربات دانلود کامل آهنگ‌های اسپاتیفای آنلاین شد...")
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
                            send_message(chat_id, "👋 **ربات دانلود کامل آهنگ از اسپاتیفای**\n\nلینک موزیک مورد نظر را بفرستید:")
                            continue

                        if "open.spotify.com/track/" in text:
                            track_name, artist_name = get_spotify_track_info(text)
                            if not track_name:
                                send_message(chat_id, "❌ استخراج لینک اسپاتیفای ناموفق بود.")
                                continue

                            audio_bytes, filename, size_mb = download_full_hq_audio(text, track_name, artist_name, chat_id)

                            if audio_bytes and filename:
                                send_message(chat_id, f"⚡️ **دانلود آهنگ کامل انجام شد!**\n📦 **حجم فایل:** `{size_mb} MB`\nدر حال ارسال فایل...")
                                send_document(
                                    chat_id,
                                    audio_bytes,
                                    filename,
                                    f"🎼 **{artist_name} - {track_name}**\n🔊 **کیفیت:** 320kbps / Original Audio\n📦 **حجم:** `{size_mb} MB`"
                                )
                            else:
                                send_message(chat_id, "❌ خطایی در استخراج فایل کامل آهنگ از سرورها رخ داد.")
        except Exception as e:
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

