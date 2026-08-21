import re
import os
import time
import requests
import threading
from flask import Flask

# --------------------------------------------------
# توکن ربات تلگرام شما
# --------------------------------------------------
BOT_TOKEN = "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"

# --------------------------------------------------
# وب‌سرور Flask برای فعال نگه‌داشتن پلن رایگان Web Service در Render
# --------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Spotify Lossless Bot 1 is running on Render Free Tier!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --------------------------------------------------
# سرویس استخراج لینک و دانلود کیفیت اصلی FLAC
# --------------------------------------------------
def get_spotify_track_info(spotify_url: str):
    """استخراج نام آهنگ و خواننده از لینک اسپاتیفای"""
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

def download_lossless_flac(track_name: str, artist_name: str):
    """دانلود فایل FLAC بدون فشرده‌سازی"""
    try:
        query = f"{artist_name} {track_name}"
        search_api = f"https://spotidownloader.com/api/download-track?q={requests.utils.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0"}
        
        response = requests.get(search_api, headers=headers, timeout=15)
        data = response.json()
        
        if data.get("status") == "success" and data.get("download_url"):
            file_url = data["download_url"]
            file_res = requests.get(file_url, timeout=45)
            if file_res.status_code == 200:
                return file_res.content, f"{artist_name} - {track_name}.flac"
    except Exception as e:
        print(f"Error downloading FLAC: {e}")
    return None, None

def send_document(chat_id, file_bytes, filename, caption):
    """ارسال به صورت Document جهت جلوگیری از فشرده‌سازی تلگرام"""
    files = {"document": (filename, file_bytes)}
    data = {"chat_id": chat_id, "caption": caption}
    return requests.post(BASE_URL + "sendDocument", data=data, files=files).json()

def send_message(chat_id, text):
    return requests.post(BASE_URL + "sendMessage", json={"chat_id": chat_id, "text": text}).json()

def start_bot_polling():
    offset = 0
    print("🚀 [Render] ربات تست شماره ۱ (Lossless FLAC) روی پلن رایگان فعال شد...")
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
                            send_message(chat_id, "⏳ در حال استخراج لینک اسپاتیفای...")
                            track_name, artist_name = get_spotify_track_info(text)
                            
                            if track_name:
                                send_message(chat_id, f"🔍 در حال دریافت فایل اصلی (Lossless FLAC) برای:\n🎵 {artist_name} - {track_name}")
                                file_bytes, filename = download_lossless_flac(track_name, artist_name)
                                
                                if file_bytes:
                                    send_document(
                                        chat_id, 
                                        file_bytes, 
                                        filename, 
                                        f"🔊 **{artist_name} - {track_name}**\n💎 کیفیت: Lossless FLAC (Original Uncompressed)"
                                    )
                                else:
                                    send_message(chat_id, "❌ فایل FLAC در دیتابیس مستقیم یافت نشد.")
                            else:
                                send_message(chat_id, "❌ استخراج اطلاعات از لینک اسپاتیفای ناموفق بود.")
        except Exception as e:
            time.sleep(2)

if __name__ == "__main__":
    # اجرای وب‌سرور جهت پورت رندر
    threading.Thread(target=run_web_server, daemon=True).start()
    # اجرای ربات
    start_bot_polling()

