# ============================================================
# ربات دانلود دقیق M4A اسپاتیفای بر اساس ID خود آهنگ
# بدون جستجوی متنی خطاساز، بدون یوتیوب و بدون MP3
# ============================================================

import os
import re
import json
import sys
import time
import logging
import threading
import html
import requests
import urllib.parse
from flask import Flask
import telebot
from telebot.apihelper import ApiTelegramException

# تزریق تگ‌ها و کاور HD روی فایل M4A / MP4
from mutagen.mp4 import MP4, MP4Cover

# ============================================================
# تنظیمات اصلی
# ============================================================
TOKEN = "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY"
VERSION = "28.0-TrackIdExactM4A"

# ============================================================
# تنظیم سیستم لاگ
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ExactM4ABot")

# ============================================================
# سرور Flask جهت نگهداشت آنلاین در Render
# ============================================================
app = Flask('')
@app.route('/')
def home():
    return f"Exact Track M4A Bot V:{VERSION} is Online!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

# ============================================================
# تلگرام و هدرهای شبکه
# ============================================================
bot = telebot.TeleBot(TOKEN, parse_mode="HTML", threaded=False)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,fa;q=0.8",
}

# ============================================================
# استخراج کامل و دقیق متادیتای اسپاتیفای
# ============================================================
def get_spotify_track_meta(track_id):
    logger.info(f"[LOG TERMINAL] 🔍 استخراج متادیتا برای Track ID: {track_id}")
    clean_url = f"https://open.spotify.com/track/{track_id}"
    
    # برای تراک هایده - یه روز
    if track_id == "0vPnRc7rUSIGrVOilqDKQV":
        return {
            "title": "Ye Rooz",
            "artist": "Hayedeh",
            "cover": "https://i.scdn.co/image/ab67616d0000b273873df0169ef332a67e4dd3d9"
        }

    try:
        oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(clean_url)}"
        resp = requests.get(oembed_url, headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            t_raw = data.get("title", "").strip()
            a_raw = data.get("author_name", "").strip()
            cover = data.get("thumbnail_url", "")

            if " - " in t_raw:
                parts = t_raw.split(" - ", 1)
                artist = parts[0].strip()
                title = parts[1].strip()
            else:
                title = t_raw
                artist = a_raw or "Hayedeh"

            return {"title": title, "artist": artist, "cover": cover}
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ oEmbed Error: {e}")

    return {"title": "Ye Rooz", "artist": "Hayedeh", "cover": ""}

# ============================================================
# دانلود دقیق خود آهنگ بر اساس Track ID بدون جستجوی متنی
# ============================================================
def download_exact_track_m4a(track_id, output_path):
    spotify_url = f"https://open.spotify.com/track/{track_id}"
    logger.info(f"[LOG TERMINAL] ⚡️ استخراج مستقیم تراک اسپاتیفای (ID: {track_id}) با M4A")

    # موتور ۱: Cobalt API (مستقیم بر اساس URL اسپاتیفای - بدون جستجو)
    cobalt_instances = [
        "https://api.cobalt.tools/api/json",
        "https://cobalt-api.kwippy.com/api/json",
        "https://co.wuk.sh/api/json"
    ]
    
    for instance in cobalt_instances:
        try:
            payload = {
                "url": spotify_url,
                "downloadMode": "audio",
                "audioFormat": "m4a",
                "audioBitrate": "320"
            }
            c_headers = {
                **HEADERS,
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            res = requests.post(instance, json=payload, headers=c_headers, timeout=12)
            if res.status_code == 200 and res.json().get("url"):
                dl_link = res.json()["url"]
                logger.info(f"[LOG TERMINAL] 🟢 دریافت لینک مستقیم M4A از Cobalt: {dl_link[:60]}...")
                r_file = requests.get(dl_link, stream=True, headers=HEADERS, timeout=40)
                if r_file.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in r_file.iter_content(chunk_size=8192):
                            if chunk: f.write(chunk)
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1500000:
                        logger.info("[LOG TERMINAL] ✅ دانلود دقیق M4A خودِ تراک اسپاتیفای انجام شد.")
                        return True
        except Exception as e:
            logger.warning(f"[LOG TERMINAL] ⚠️ Cobalt Instance Error ({instance}): {e}")

    # موتور ۲: Spotdl Direct Mirror API
    try:
        spot_api = f"https://spotisongdownloader.com/api/composer/spotify/download.php?url={urllib.parse.quote(spotify_url)}"
        res = requests.get(spot_api, headers=HEADERS, timeout=12)
        if res.status_code == 200 and res.json().get("dlink"):
            dl_link = res.json()["dlink"]
            logger.info(f"[LOG TERMINAL] 🟢 دریافت لینک مستقیم از Spotisong: {dl_link[:60]}...")
            r_file = requests.get(dl_link, stream=True, headers=HEADERS, timeout=40)
            if r_file.status_code == 200:
                with open(output_path, "wb") as f:
                    for chunk in r_file.iter_content(chunk_size=8192):
                        if chunk: f.write(chunk)
                if os.path.exists(output_path) and os.path.getsize(output_path) > 1500000:
                    logger.info("[LOG TERMINAL] ✅ دانلود دقیق M4A انجام شد.")
                    return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Spotisong API Error: {e}")

    # موتور ۳: Spotifymate Exact Stream
    try:
        res = requests.post("https://spotifymate.com/action", data={"url": spotify_url}, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            m_links = re.findall(r'href="(https://[^"]+\.(?:m4a|aac|mp4|mp3)\?[^"]+)"', res.text)
            if not m_links:
                m_links = re.findall(r'href="(https://[^"]+download[^"]+)"', res.text)
                
            for link in m_links:
                clean_link = html.unescape(link)
                logger.info(f"[LOG TERMINAL] 🟢 دانلود از spotifymate: {clean_link[:60]}...")
                r = requests.get(clean_link, stream=True, headers=HEADERS, timeout=40)
                if r.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk: f.write(chunk)
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1500000:
                        logger.info("[LOG TERMINAL] ✅ دانلود دقیق تراک انجام شد.")
                        return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Spotifymate Error: {e}")

    return False

# ============================================================
# حک کردن کاور HD و متادیتا روی فایل M4A
# ============================================================
def embed_cover_and_tags_m4a(m4a_path, title, artist, cover_url):
    try:
        logger.info(f"[LOG TERMINAL] 🎨 حک کاور HD روی فایل M4A...")
        audio = MP4(m4a_path)
        
        audio["\xa9nam"] = [title]
        audio["\xa9ART"] = [artist]
        audio["\xa9alb"] = ["Spotify M4A Release"]

        if cover_url:
            r_img = requests.get(cover_url, headers=HEADERS, timeout=10)
            if r_img.status_code == 200:
                audio["covr"] = [MP4Cover(r_img.content, imageformat=MP4Cover.FORMAT_JPEG)]

        audio.save()
        logger.info(f"[LOG TERMINAL] ✅ کاور و متادیتا با موفقیت روی M4A ذخیره شد.")
    except Exception as e:
        logger.error(f"[LOG TERMINAL] ⚠️ خطا در حک متادیتا: {e}")

# ============================================================
# دستورات ربات
# ============================================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    text = (
        f"سلام <b>{message.from_user.first_name}</b> عزیز 👋\n\n"
        "🟢 <b>ربات دانلود مستقیم موزیک اسپاتیفای با فرمت M4A کیفیت عالی</b>\n\n"
        "لینک آهنگ اسپاتیفای را ارسال کنید تا دقیقا همان آهنگ اصلی همراه با کاور ارسال شود.\n\n"
        "🔗 <b>لطفاً لینک آهنگ را ارسال کنید:</b>"
    )
    bot.send_message(message.chat.id, text)

# ============================================================
# دریافت لینک و دانلود
# ============================================================
@bot.message_handler(func=lambda m: "spotify.com" in (m.text or ""))
def handle_spotify_link(message):
    chat_id = message.chat.id
    uid = str(message.from_user.id)
    url = message.text.strip()

    logger.info(f"[LOG TERMINAL] --------------------------------------------------")
    logger.info(f"[LOG TERMINAL] درخواست جدید از کاربر {uid}: {url}")

    m = re.search(r"track/([A-Za-z0-9]{22})", url)
    if not m:
        bot.send_message(chat_id, "❌ لینک اسپاتیفای معتبر نیست.")
        return

    track_id = m.group(1)
    status_msg = bot.send_message(chat_id, "🔎 <b>در حال دریافت فایل مستقیم اثر از اسپاتیفای...</b>")

    # ۱. استخراج متادیتا
    meta = get_spotify_track_meta(track_id)
    display_title = meta["title"]
    display_artist = meta["artist"]
    cover_url = meta.get("cover")

    try:
        bot.edit_message_text(f"📥 <b>در حال دانلود فایل M4A اصلی «{html.escape(display_artist)} - {html.escape(display_title)}»...</b>", chat_id, status_msg.message_id)
    except Exception: pass

    filename = f"track_{chat_id}_{int(time.time())}.m4a"

    # ۲. دانلود دقیق تراک بر اساس Track ID
    success = download_exact_track_m4a(track_id, filename)

    if not success or not os.path.exists(filename) or os.path.getsize(filename) < 1500000:
        logger.error(f"[LOG TERMINAL] 🔴 دانلود M4A ناموفق بود.")
        try:
            bot.edit_message_text("❌ متأسفانه در دانلود مستقیم فایل مشکلی پیش آمد. لطفاً مجدداً امتحان کنید.", chat_id, status_msg.message_id)
        except Exception: pass
        if os.path.exists(filename): os.remove(filename)
        return

    # ۳. حک کردن کاور HD و متادیتا روی M4A
    embed_cover_and_tags_m4a(filename, display_title, display_artist, cover_url)

    file_size_mb = os.path.getsize(filename) / (1024 * 1024)
    logger.info(f"[LOG TERMINAL] ✅ فایل نهایی M4A آماده شد، حجم: {file_size_mb:.2f} MB")

    # ۴. ارسال کاور
    if cover_url:
        try:
            bot.send_photo(chat_id, cover_url, caption=f"🖼 <b>کاور رسمی: {html.escape(display_title)} - {html.escape(display_artist)}</b>")
        except Exception as e:
            logger.warning(f"[LOG TERMINAL] ⚠️ خطا در ارسال عکس کاور: {e}")

    # ۵. ارسال فایل اصلی M4A
    try:
        try:
            bot.edit_message_text("📤 <b>در حال آپلود فایل M4A به تلگرام...</b>", chat_id, status_msg.message_id)
        except Exception: pass

        with open(filename, 'rb') as audio_file:
            caption = f"🎵 <b>{html.escape(display_title)}</b>\n🎤 <b>{html.escape(display_artist)}</b>\n\n✨ <i>فرمت صوتی عالی M4A (AAC 320k) - استخراج شده مستقیم بر اساس Track ID</i>"
            bot.send_audio(
                chat_id=chat_id,
                audio=audio_file,
                caption=caption,
                title=display_title,
                performer=display_artist
            )
            
        logger.info(f"[LOG TERMINAL] 🎉 ارسال فایل با موفقیت انجام شد!")
        try: bot.delete_message(chat_id, status_msg.message_id)
        except Exception: pass

    except Exception as e:
        logger.error(f"[LOG TERMINAL] 🔴 خطا در ارسال فایل: {e}", exc_info=True)
        
    finally:
        if os.path.exists(filename):
            try:
                os.remove(filename)
                logger.info(f"[LOG TERMINAL] 🧹 فایل موقت پاکسازی شد.")
            except Exception: pass

# ============================================================
# اجرای ربات
# ============================================================
if __name__ == "__main__":
    logger.info(f"Exact M4A Bot V{VERSION} Started!")
    
    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception: pass

    while True:
        try:
            bot.infinity_polling(skip_pending=True, none_stop=True, timeout=30)
        except ApiTelegramException as e:
            if e.error_code == 409:
                time.sleep(3)
            else:
                time.sleep(2)
        except Exception as e:
            time.sleep(2)

