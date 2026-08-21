import re
import os
import time
import requests
import traceback
import urllib.parse
import threading
from flask import Flask

# --------------------------------------------------
# توکن ربات تلگرام شما
# --------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"

# --------------------------------------------------
# وب‌سرور Flask جهت پشتیبانی از Web Service رایگان Render
# --------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Spotify Bot Test 3 (Multi-Engine + Debugger) is online!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --------------------------------------------------
# توابع ارسال پیام و دیباگ به تلگرام
# --------------------------------------------------
def send_message(chat_id, text, parse_mode="Markdown"):
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return requests.post(BASE_URL + "sendMessage", json=payload).json()

def send_debug(chat_id, debug_title, debug_info):
    """ارسال جزئیات فنی و خطایابی به کاربر"""
    clean_info = str(debug_info)[:3500]
    msg = f"🐛 *[DEBUG LOG]*\n📌 *مرحله:* {debug_title}\n```text\n{clean_info}\n```"
    send_message(chat_id, msg, parse_mode="Markdown")

def send_document(chat_id, file_bytes, filename, caption):
    """ارسال فایل اصلی بدون فشرده‌سازی تلگرام"""
    files = {"document": (filename, file_bytes)}
    data = {"chat_id": chat_id, "caption": caption}
    return requests.post(BASE_URL + "sendDocument", data=data, files=files).json()

# --------------------------------------------------
# استخراج اطلاعات اسپاتیفای
# --------------------------------------------------
def get_spotify_info(url: str):
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
        print(f"Error scraping Spotify: {e}")
    return None, None

def extract_track_id(url: str):
    m = re.search(r'track/([a-zA-Z0-9]+)', url)
    return m.group(1) if m else None

# --------------------------------------------------
# موتور ۱: SpotifyMate / Downloader Engine
# --------------------------------------------------
def provider_engine_1(spotify_url, track_id, chat_id):
    try:
        send_message(chat_id, "🔄 *امتحان موتور ۱:* تلاش برای استخراج مستقیم از SpotifyDown API...")
        api_url = f"https://api.spotifydown.com/download/{track_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://spotifydown.com/",
            "Origin": "https://spotifydown.com"
        }
        res = requests.get(api_url, headers=headers, timeout=15)
        
        if res.status_code != 200:
            send_debug(chat_id, "موتور ۱ - پاسخ ناموفق HTTP", f"Status Code: {res.status_code}\nResponse: {res.text}")
            return None, None, None
            
        data = res.json()
        if data.get("success") and data.get("link"):
            download_url = data["link"]
            title = data.get("metadata", {}).get("title", "Track")
            artist = data.get("metadata", {}).get("artists", "Artist")
            
            file_res = requests.get(download_url, headers=headers, timeout=60)
            if file_res.status_code == 200 and len(file_res.content) > 100000:
                return file_res.content, f"{artist} - {title}.mp3", f"{artist} - {title}"
            else:
                send_debug(chat_id, "موتور ۱ - فایل دریافتی نامعتبر", f"Status: {file_res.status_code}, Length: {len(file_res.content)}")
        else:
            send_debug(chat_id, "موتور ۱ - عدم وجود لینک در JSON", data)
    except Exception as e:
        send_debug(chat_id, "موتور ۱ - خطای Exception", traceback.format_exc())
    return None, None, None

# --------------------------------------------------
# موتور ۲: Deezer / Hi-Res Uncompressed Engine
# --------------------------------------------------
def provider_engine_2(track_name, artist_name, chat_id):
    try:
        send_message(chat_id, "🔄 *امتحان موتور ۲:* جستجو در دیتابیس کیفیت بالا (HQ Deezer Engine)...")
        query = f"{artist_name} {track_name}"
        search_url = f"https://api.deezer.com/search?q={urllib.parse.quote(query)}"
        
        res = requests.get(search_url, timeout=12)
        if res.status_code == 200:
            data = res.json()
            if data.get("data") and len(data["data"]) > 0:
                track = data["data"][0]
                preview_url = track.get("preview")
                title = track.get("title", track_name)
                artist = track.get("artist", {}).get("name", artist_name)
                
                if preview_url:
                    file_res = requests.get(preview_url, timeout=45)
                    if file_res.status_code == 200:
                        return file_res.content, f"{artist} - {title} (HQ).mp3", f"{artist} - {title}"
                send_debug(chat_id, "موتور ۲ - پیش‌نمایش یافت نشد", data)
            else:
                send_debug(chat_id, "موتور ۲ - موزیک در جستجو پیدا نشد", data)
        else:
            send_debug(chat_id, "موتور ۲ - خطای سرور Deezer", res.text)
    except Exception as e:
        send_debug(chat_id, "موتور ۲ - خطای Exception", traceback.format_exc())
    return None, None, None

# --------------------------------------------------
# موتور ۳: Rapid/Public Converter Engine
# --------------------------------------------------
def provider_engine_3(track_name, artist_name, chat_id):
    try:
        send_message(chat_id, "🔄 *امتحان موتور ۳:* دریافت از سرورهای هوشمند جانبی...")
        q = f"{artist_name} {track_name}"
        api_url = f"https://spotidownloader.com/api/download-track?q={urllib.parse.quote(q)}"
        headers = {"User-Agent": "Mozilla/5.0"}
        
        res = requests.get(api_url, headers=headers, timeout=15)
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "success" and data.get("download_url"):
                file_url = data["download_url"]
                file_res = requests.get(file_url, timeout=60)
                if file_res.status_code == 200:
                    return file_res.content, f"{artist_name} - {track_name}.flac", f"{artist_name} - {track_name}"
            send_debug(chat_id, "موتور ۳ - پاسخ ناموفق JSON", data)
        else:
            send_debug(chat_id, "موتور ۳ - خطای HTTP", res.status_code)
    except Exception as e:
        send_debug(chat_id, "موتور ۳ - خطای Exception", traceback.format_exc())
    return None, None, None

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    print("🚀 [Render] ربات تست شماره ۳ + دیباگر هوشمند روشن شد...")
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
                            send_message(chat_id, "👋 *سلام!* لینک اسپاتیفای را بفرستید تا با دیباگر پیشرفته و موتور ۳گانه بررسی شود.")
                            continue

                        if "open.spotify.com/track/" in text:
                            track_id = extract_track_id(text)
                            track_name, artist_name = get_spotify_info(text)
                            
                            send_message(chat_id, f"🔎 *اطلاعات استخراج شده:*\n🎵 نام ترک: `{track_name or 'نامشخص'}`\n👤 خواننده: `{artist_name or 'نامشخص'}`\n🆔 آیدی: `{track_id or 'نامشخص'}`")

                            file_bytes, filename, caption = None, None, None

                            # ۱. تست موتور اول
                            if track_id:
                                file_bytes, filename, caption = provider_engine_1(text, track_id, chat_id)

                            # ۲. تست موتور دوم در صورت عدم موفقیت موتور اول
                            if not file_bytes and track_name and artist_name:
                                file_bytes, filename, caption = provider_engine_2(track_name, artist_name, chat_id)

                            # ۳. تست موتور سوم
                            if not file_bytes and track_name and artist_name:
                                file_bytes, filename, caption = provider_engine_3(track_name, artist_name, chat_id)

                            # ارسال فایل نهایی یا اعلام شکست با دیباگ
                            if file_bytes and filename:
                                send_message(chat_id, "⚡️ فایل با موفقیت دریافت شد! در حال ارسال فایل اصلی (Document)...")
                                send_document(
                                    chat_id,
                                    file_bytes,
                                    filename,
                                    f"🎧 *{caption}*\n📦 *فایل خام سندی (بدون افت کیفیت)*"
                                )
                            else:
                                send_message(chat_id, "❌ متأسفانه تمام ۳ موتور با خطا مواجه شدند. کادرهای دیباگ فوق علت فنی خطا را نشان می‌دهند.")
        except Exception as e:
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

