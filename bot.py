import re
import os
import time
import requests
import threading
from flask import Flask

# --------------------------------------------------
# توکن ربات تلگرام شما
# --------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"

# --------------------------------------------------
# وب‌سرور Flask برای فعال نگه‌داشتن Web Service در Render
# --------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Spotify Bot Test 2 is running online!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --------------------------------------------------
# منطق استخراج و دانلود مستقیم فایل اصلی (تست شماره ۲)
# --------------------------------------------------
def extract_spotify_id(url: str):
    """استخراج ID ترک از لینک اسپاتیفای"""
    match = re.search(r'track/([a-zA-Z0-9]+)', url)
    if match:
        return match.group(1)
    return None

def fetch_lossless_audio(spotify_id: str):
    """استخراج مستقیم فایل خام با بالاترین کیفیت از SpotifyDown Engine"""
    try:
        api_endpoint = f"https://api.spotifydown.com/download/{spotify_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://spotifydown.com/",
            "Origin": "https://spotifydown.com"
        }
        
        response = requests.get(api_endpoint, headers=headers, timeout=20)
        data = response.json()
        
        if data.get("success") and data.get("link"):
            audio_url = data["link"]
            title = data.get("metadata", {}).get("title", "Track")
            artists = data.get("metadata", {}).get("artists", "Artist")
            
            # دانلود فایل خام بدون فشرده‌سازی
            audio_data = requests.get(audio_url, timeout=60).content
            filename = f"{artists} - {title}.mp3"
            return audio_data, filename, title, artists
    except Exception as e:
        print(f"Error fetching audio in test 2: {e}")
    return None, None, None, None

def send_document(chat_id, file_bytes, filename, caption):
    """ارسال فایل به صورت Document خام جهت حفظ تمامیت فایل"""
    files = {"document": (filename, file_bytes)}
    data = {"chat_id": chat_id, "caption": caption}
    return requests.post(BASE_URL + "sendDocument", data=data, files=files).json()

def send_message(chat_id, text):
    return requests.post(BASE_URL + "sendMessage", json={"chat_id": chat_id, "text": text}).json()

def start_bot_polling():
    offset = 0
    print("🚀 [Render] ربات تست شماره ۲ (SpotifyDown Engine) فعال شد...")
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
                            send_message(chat_id, "👋 سلام! لینک اسپاتیفای (Spotify Track Link) را ارسال کنید:")
                            continue

                        if "open.spotify.com/track/" in text:
                            spotify_id = extract_spotify_id(text)
                            if spotify_id:
                                send_message(chat_id, "⚡️ در حال پردازش لینک اسپاتیفای و استخراج فایل اصلی (تست ۲)...")
                                audio_bytes, filename, title, artists = fetch_lossless_audio(spotify_id)
                                
                                if audio_bytes:
                                    send_document(
                                        chat_id,
                                        audio_bytes,
                                        filename,
                                        f"🎧 **{artists} - {title}**\n📦 فایل اصلی (Document) - بدون فشرده‌سازی"
                                    )
                                else:
                                    send_message(chat_id, "❌ خطایی در دانلود فایل اصلی رخ داد.")
                            else:
                                send_message(chat_id, "❌ آی‌دی لینک اسپاتیفای معتبر نیست.")
        except Exception as e:
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

