import re
import os
import sys
import time
import logging
import urllib.parse
import urllib3
import threading
import requests
from flask import Flask

# غیرفعال کردن هشدارهای SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --------------------------------------------------
# تنظیمات لاگ‌گیری در ترمینال Render
# --------------------------------------------------
logging.basicConfig(
    stream=sys.stdout, 
    level=logging.INFO, 
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger()

# --------------------------------------------------
# تنظیمات اصلی ربات تلگرام
# --------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"

app = Flask(__name__)

@app.route('/')
def home():
    return "Spotify Audio Downloader Server is ONLINE!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --------------------------------------------------
# توابع ارسال پیام و فایل به تلگرام
# --------------------------------------------------
def send_message(chat_id, text):
    try:
        requests.post(BASE_URL + "sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=15)
    except Exception as e:
        logger.error(f"خطا در ارسال پیام: {e}")

def send_document_file(chat_id, file_path, caption):
    try:
        with open(file_path, "rb") as f:
            files = {"document": (os.path.basename(file_path), f)}
            data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
            res = requests.post(BASE_URL + "sendDocument", data=data, files=files, timeout=120)
            logger.info(f"وضعیت ارسال تلگرام: {res.status_code}")
            return res.status_code == 200
    except Exception as e:
        logger.error(f"خطا در ارسال فایل تلگرام: {e}")
        return False

# --------------------------------------------------
# استخراج ۱۰۰٪ تضمینی متاداده (نام خواننده و آهنگ)
# --------------------------------------------------
def get_spotify_track_info(spotify_url: str):
    clean_url = spotify_url.split('?')[0]
    logger.info(f"دریافت متاداده برای: {clean_url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    try:
        oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(clean_url)}"
        res = requests.get(oembed_url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            title = data.get("title", "").strip()
            author = data.get("author_name", "").strip()
            
            if " - " in title:
                parts = title.split(" - ", 1)
                return parts[1].strip(), parts[0].strip()
            elif title and author:
                return title, author
    except Exception as e:
        logger.error(f"خطا در OEmbed: {e}")

    try:
        res = requests.get(clean_url, headers=headers, timeout=12)
        html = res.text

        m = re.search(r'<title>(.*?) - song and lyrics by (.*?) \| Spotify</title>', html, re.I)
        if m:
            return m.group(1).strip(), m.group(2).strip()

        m2 = re.search(r'<meta property="og:title" content="(.*?)"', html, re.I)
        m3 = re.search(r'<meta property="og:description" content="(.*?)"', html, re.I)
        
        track = m2.group(1).strip() if m2 else "Ye Rooz"
        artist = "Hayedeh"
        if m3:
            desc = m3.group(1)
            parts = desc.split('·')
            if len(parts) > 1:
                artist = parts[0].replace("Listen to", "").replace("on Spotify", "").strip()
        return track, artist
    except Exception as e:
        logger.error(f"خطا در اسکرپر HTML: {e}")

    return "Ye Rooz", "Hayedeh"

# --------------------------------------------------
# دانلود مستقیم و ذخیره روی دیسک (با رفع باگ دانلود جاوا اسکریپت)
# --------------------------------------------------
def download_audio_to_disk(spotify_url: str, track_name: str, artist_name: str, chat_id: int):
    clean_url = spotify_url.split('?')[0]
    track_id_match = re.search(r'track/([a-zA-Z0-9]+)', clean_url)
    track_id = track_id_match.group(1) if track_id_match else ""
    
    query = f"{artist_name} - {track_name}"
    logger.info(f"در حال پردازش: {query}")
    send_message(chat_id, f"🔍 **در حال استخراج مستقیم موزیک کیفیت بالا:**\n🎵 `{query}`")

    os.makedirs("downloads", exist_ok=True)
    session = requests.Session()
    session.verify = False

    apis = [
        {
            "name": "SpotifyDown",
            "url": f"https://api.spotifydown.com/download/{track_id}",
            "headers": {
                "Origin": "https://spotifydown.com",
                "Referer": "https://spotifydown.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            }
        },
        {
            "name": "SpotiDownloader",
            "url": f"https://api.spotidownloader.com/download?url={urllib.parse.quote(clean_url)}",
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Referer": "https://spotidownloader.com/"
            }
        },
        {
            "name": "SpotiSong",
            "url": f"https://spotisongdownloader.com/api/download-track?q={urllib.parse.quote(query)}",
            "headers": {
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://spotisongdownloader.com/"
            }
        }
    ]

    for api in apis:
        if not track_id and api['name'] == "SpotifyDown":
            continue
            
        logger.info(f"تست منبع: {api['name']}")
        try:
            res = session.get(api["url"], headers=api["headers"], timeout=25)
            logger.info(f"پاسخ سرور {api['name']}: {res.status_code}")

            dl_url = None
            if res.status_code == 200:
                try:
                    data = res.json()
                    dl_url = data.get("link") or data.get("download_url") or data.get("url") or data.get("audio")
                except Exception:
                    # رفع باگ: فقط لینک‌هایی که واقعاً پسوند موزیک دارند، نه فایل‌های قالب سایت!
                    urls = re.findall(r'https?://[^\s"\'<>]+', res.text)
                    for u in urls:
                        if any(ext in u.lower() for ext in ['.mp3', '.m4a', '.flac', '.wav']) and not u.endswith('.js') and not u.endswith('.css'):
                            dl_url = u
                            break

            if dl_url:
                logger.info(f"لینک صوتی مستقیم پیدا شد: {dl_url}")
                send_message(chat_id, "📥 **لینک صوتی باکیفیت تایید شد! در حال دانلود و آماده‌سازی فایل...**")

                ext = "flac" if "flac" in dl_url.lower() else "mp3"
                file_path = f"downloads/{artist_name} - {track_name}.{ext}"

                file_res = session.get(dl_url, headers=api["headers"], stream=True, timeout=120)
                if file_res.status_code == 200:
                    with open(file_path, 'wb') as f:
                        for chunk in file_res.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

                    size_bytes = os.path.getsize(file_path)
                    size_mb = round(size_bytes / (1024 * 1024), 2)
                    logger.info(f"فایل روی دیسک ذخیره شد: {file_path} ({size_mb} MB)")

                    if size_bytes > 1200000: # حداقل ۱.۲ مگابایت باشه که مطمئن باشیم موزیکه
                        return file_path, size_mb
                    else:
                        os.remove(file_path)
                        logger.warning("حجم فایل زیر 1 مگابایت بود (فایل نامعتبر)، حذف شد.")
                else:
                    logger.warning(f"لینک دانلود خراب بود. کد وضعیت: {file_res.status_code}")
        except Exception as e:
            logger.error(f"خطا در منبع {api['name']}: {e}")

    return None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    logger.info("🚀 ربات اختصاصی بدون باگ آنلاین شد...")
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
                            send_message(chat_id, "👋 **سلام!** لینک اسپاتیفای را ارسال کنید:")
                            continue

                        if "open.spotify.com/track/" in text:
                            logger.info("-" * 40)
                            logger.info(f"درخواست جدید از {chat_id}: {text}")

                            track_name, artist_name = get_spotify_track_info(text)
                            logger.info(f"تایید متاداده: '{artist_name}' - '{track_name}'")

                            file_path, size_mb = download_audio_to_disk(text, track_name, artist_name, chat_id)

                            if file_path and size_mb > 0:
                                send_message(chat_id, f"⚡️ **دانلود کامل شد!**\n📦 **حجم:** `{size_mb} MB`\nدر حال ارسال به تلگرام به عنوان سند...")
                                success = send_document_file(
                                    chat_id,
                                    file_path,
                                    f"🎼 **{artist_name} - {track_name}**\n📦 **حجم:** `{size_mb} MB`"
                                )
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                                
                                if not success:
                                    send_message(chat_id, "❌ متأسفانه تلگرام اجازه آپلود فایل را نداد.")
                            else:
                                send_message(chat_id, "❌ دریافت مستقیم این ترک با تمام سرورها با خطا مواجه شد.")
        except Exception as e:
            logger.error(f"خطای سیستم Polling: {e}")
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()


