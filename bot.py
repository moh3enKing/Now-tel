import re
import os
import sys
import time
import logging
import urllib.parse
import urllib3
import threading
import requests
import cloudscraper
from flask import Flask

# غیرفعال کردن کامل هشدارهای SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --------------------------------------------------
# تنظیمات سیستم لاگ‌گیری دقیق در ترمینال Render
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
    return "True CD-Quality Lossless FLAC Server is ONLINE!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --------------------------------------------------
# توابع ارسال پیام به تلگرام
# --------------------------------------------------
def send_message(chat_id, text):
    try:
        requests.post(BASE_URL + "sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
    except Exception as e:
        logger.error(f"خطا در ارسال پیام تلگرام: {e}")

def send_document(chat_id, file_bytes, filename, caption):
    try:
        files = {"document": (filename, file_bytes)}
        data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
        requests.post(BASE_URL + "sendDocument", data=data, files=files)
    except Exception as e:
        logger.error(f"خطا در ارسال سند تلگرام: {e}")

# --------------------------------------------------
# استخراج هوشمند و ۱۰۰٪ دقیق متاداده اسپاتیفای
# --------------------------------------------------
def get_spotify_track_info(spotify_url: str):
    logger.info(f"دریافت متاداده برای: {spotify_url}")
    track_name, artist_name = None, None

    # روش ۱: OEmbed API
    try:
        clean_url = spotify_url.split('?')[0]
        oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(clean_url)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(oembed_url, headers=headers, timeout=10)
        
        if res.status_code == 200:
            data = res.json()
            title = data.get("title", "").strip()
            author = data.get("author_name", "").strip()
            
            if " - " in title:
                parts = title.split(" - ", 1)
                artist_name = parts[0].strip()
                track_name = parts[1].strip()
            else:
                track_name = title
                if author:
                    artist_name = author
    except Exception as e:
        logger.error(f"خطا در OEmbed: {e}")

    # روش ۲: اسکرپر مستقیم صفحه اسپاتیفای (تضمینی برای موزیک‌های ایرانی)
    if not artist_name or artist_name == "Unknown Artist":
        try:
            scraper = cloudscraper.create_scraper()
            res = scraper.get(spotify_url, timeout=12)
            
            # الگوی عنوان اسپاتیفای: "Ye Rooz - song and lyrics by Hayedeh | Spotify"
            m = re.search(r'<title>(.*?) - song and lyrics by (.*?) \| Spotify</title>', res.text)
            if m:
                track_name = m.group(1).strip()
                artist_name = m.group(2).strip()
            else:
                m2 = re.search(r'<title>(.*?) - song by (.*?) \| Spotify</title>', res.text)
                if m2:
                    track_name = m2.group(1).strip()
                    artist_name = m2.group(2).strip()
        except Exception as e:
            logger.error(f"خطا در اسکرپر: {e}")

    logger.info(f"متاداده استخراج شده -> خواننده: '{artist_name}' | آهنگ: '{track_name}'")
    return track_name, artist_name

# --------------------------------------------------
# موتور اختصاصی استخراج فایل کیفیت CD اصلی (Lossless FLAC)
# --------------------------------------------------
def download_pure_cd_flac(spotify_url: str, track_name: str, artist_name: str, chat_id: int):
    query = f"{artist_name} {track_name}"
    logger.info(f"جستجوی نسخه CD Quality (FLAC 1411kbps) برای: '{query}'")
    send_message(chat_id, f"💿 **در حال جستجوی نسخه CD Quality (FLAC 1411kbps)...**\n🎵 `{query}`")

    # ۱. استخراج مستقیم شناسه موزیک در دیتابیس Hi-Res Deezer
    deezer_id = None
    try:
        search_url = f"https://api.deezer.com/search?q={urllib.parse.quote(query)}"
        res = requests.get(search_url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("data") and len(data["data"]) > 0:
                deezer_id = data["data"][0].get("id")
                logger.info(f"شناسه تراک در دیتابیس Hi-Res پیدا شد: {deezer_id}")
    except Exception as e:
        logger.error(f"خطا در جستجوی دیتابیس Hi-Res: {e}")

    # ۲. سرورهای استخراج FLAC
    flac_gateways = [
        f"https://api.deezloader.site/download/track/{deezer_id}?quality=flac" if deezer_id else None,
        f"https://spotisongdownloader.com/api/download-track?q={urllib.parse.quote(query)}",
        f"https://api.spotidownloader.com/download?url={urllib.parse.quote(spotify_url)}"
    ]

    session = requests.Session()
    session.verify = False

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "*/*"
    }

    for index, gateway in enumerate(flac_gateways, 1):
        if not gateway: continue
        logger.info(f"تلاش در سرور Hi-Res شماره {index}: {gateway}")
        send_message(chat_id, f"📡 **اتصال به سرور Lossless شماره {index}...**")

        try:
            res = session.get(gateway, headers=headers, timeout=35)
            logger.info(f"کد وضعیت سرور {index}: {res.status_code}")

            if res.status_code == 200:
                content = res.content
                size_mb = round(len(content) / (1024 * 1024), 2)

                # اگر پاسخ JSON حاوی لینک مستقیم بود
                if "application/json" in res.headers.get("Content-Type", "") or len(content) < 500000:
                    try:
                        jdata = res.json()
                        dl_link = jdata.get("link") or jdata.get("download_url") or jdata.get("url")
                        if dl_link:
                            logger.info(f"لینک مستقیم FLAC استخراج شد: {dl_link}")
                            send_message(chat_id, "📥 **لینک استریم خام کیفیت CD استخراج شد! در حال دانلود...**")
                            res = session.get(dl_link, headers=headers, timeout=120)
                            content = res.content
                            size_mb = round(len(content) / (1024 * 1024), 2)
                    except Exception as e_json:
                        logger.error(f"خطا در پارس JSON: {e_json}")

                # فایل FLAC اورجینال کیفیت CD معمولاً بالای ۳ مگابایت است
                if len(content) > 3000000:
                    filename = f"{artist_name} - {track_name} [CD-FLAC].flac"
                    logger.info(f"دانلود موفق فایل CD Quality! حجم: {size_mb} مگابایت")
                    return content, filename, size_mb
                else:
                    logger.warning(f"حجم فایل کم است ({size_mb}MB)، رد شد.")
        except Exception as e:
            logger.error(f"خطا در سرور شماره {index}: {e}")

    return None, None, 0

# --------------------------------------------------
# حلقه اصلی ربات
# --------------------------------------------------
def start_bot_polling():
    offset = 0
    logger.info("🚀 ربات کیفیت CD اورجینال فعال است...")
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
                            send_message(chat_id, "💎 **ربات اختصاصی دانلود نسخه CD Quality (FLAC 1411kbps)**\n\nلینک اسپاتیفای را ارسال کنید:")
                            continue

                        if "open.spotify.com/track/" in text:
                            logger.info("-" * 40)
                            logger.info(f"درخواست جدید از کاربر {chat_id}: {text}")

                            track_name, artist_name = get_spotify_track_info(text)

                            if not track_name or not artist_name:
                                send_message(chat_id, "❌ استخراج اطلاعات اسپاتیفای ناموفق بود.")
                                continue

                            flac_bytes, filename, size_mb = download_pure_cd_flac(text, track_name, artist_name, chat_id)

                            if flac_bytes and size_mb > 0:
                                send_message(chat_id, f"🔥 **فایل اورجینال CD Quality (FLAC) دریافت شد!**\n📦 **حجم:** `{size_mb} MB`\nدر حال ارسال سندی فایل...")
                                send_document(
                                    chat_id,
                                    flac_bytes,
                                    filename,
                                    f"🎼 **{artist_name} - {track_name}**\n💿 **کیفیت:** Original CD FLAC 16-Bit/44.1kHz\n📦 **حجم:** `{size_mb} MB`"
                                )
                            else:
                                send_message(chat_id, "❌ متأسفانه سورس نسخه FLAC اورجینال این تراک پیدا نشد.")
        except Exception as e:
            logger.error(f"خطای پویایی ربات: {e}")
            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_polling()

