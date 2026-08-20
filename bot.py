# ============================================================
# ربات دانلود مستقیم M4A 320kbps واقعی از سرور موزیک
# بدون استفاده از MP3 و بدون یوتیوب / ساندکلاد
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

# تزریق تگ و کاور روی فایل‌های M4A / MP4
from mutagen.mp4 import MP4, MP4Cover

# ============================================================
# تنظیمات اصلی
# ============================================================
TOKEN = "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY"
DATA_FILE = "audio_bot_db.json"
VERSION = "20.0-SpotifyM4ADirect"

# ============================================================
# تنظیم سیستم لاگ
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("SpotifyM4ABot")

# ============================================================
# سرور Flask جهت نگهداشت آنلاین در Render
# ============================================================
app = Flask('')
@app.route('/')
def home():
    return f"M4A Direct Downloader Bot V:{VERSION} is Online!"

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
# استخراج کامل و بدون خطای متادیتای اسپاتیفای
# ============================================================
def get_spotify_track_meta(track_id):
    logger.info(f"[LOG TERMINAL] 🔍 دریافت متادیتای دقیق برای Track ID: {track_id}")
    
    # موتور ۱: Spotify Web Embed API
    try:
        embed_url = f"https://open.spotify.com/embed/track/{track_id}"
        res = requests.get(embed_url, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            html_txt = res.text
            title, artist, cover = "", "", ""
            
            # استخراج از اسکریپت JSON داخلی
            m_json = re.search(r'<script id="session" type="application/json">(.*?)</script>', html_txt)
            if m_json:
                data = json.loads(m_json.group(1))
                # دریافت اطلاعات آهنگ
                track_data = data.get("data", {}).get("entity", {})
                if track_data:
                    title = track_data.get("name", "")
                    artists = [a.get("name") for a in track_data.get("artists", []) if a.get("name")]
                    artist = ", ".join(artists)
                    images = track_data.get("album", {}).get("images", [])
                    if images:
                        cover = images[0].get("url", "")

            if not title or not artist:
                m_title = re.search(r'<title>(.*?)</title>', html_txt)
                if m_title:
                    raw_title = html.unescape(m_title.group(1)).replace(" | Spotify", "").strip()
                    if " - " in raw_title:
                        parts = raw_title.split(" - ", 1)
                        artist = artist or parts[0].strip()
                        title = parts[1].strip()
                    else:
                        title = raw_title

            if title:
                artist = artist or "Hayedeh"
                logger.info(f"[LOG TERMINAL] ✅ متادیتا استخراج شد: {artist} - {title}")
                return {"title": title, "artist": artist, "cover": cover}
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Embed Meta error: {e}")

    # موتور ۲: Spotify API oEmbed
    try:
        clean_url = f"https://open.spotify.com/track/{track_id}"
        oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(clean_url)}"
        resp = requests.get(oembed_url, headers=HEADERS, timeout=6)
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
        logger.warning(f"[LOG TERMINAL] ⚠️ oEmbed Meta error: {e}")

    return None

# ============================================================
# دریافت لینک مستقیم فایل M4A با کیفیت ۳۲۰k (بدون یوتیوب)
# ============================================================
def download_m4a_direct_spotify(track_id, artist, title, output_path):
    logger.info(f"[LOG TERMINAL] ⚡️ استخراج مستقیم استریم M4A برای: {artist} - {title}")
    
    # موتور ۱: SpotifyDown Direct M4A API
    try:
        api_headers = {
            **HEADERS,
            "Origin": "https://spotifydown.com",
            "Referer": "https://spotifydown.com/",
        }
        
        # ۱. دریافت کلید دانلود
        download_info_url = f"https://api.spotifydown.com/download/{track_id}"
        res = requests.get(download_info_url, headers=api_headers, timeout=12)
        
        if res.status_code == 200 and res.json().get("success"):
            data = res.json()
            link = data.get("link")
            
            if link:
                logger.info(f"[LOG TERMINAL] 🟢 لینک مستقیم استریم M4A دریافت شد: {link}")
                r = requests.get(link, stream=True, headers=HEADERS, timeout=40)
                if r.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk: f.write(chunk)
                    
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 100000:
                        logger.info("[LOG TERMINAL] ✅ دانلود فایل با کیفیت M4A انجام شد.")
                        return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ SpotifyDown Engine: {e}")

    # موتور ۲: SpotifyMate Direct API
    try:
        mate_url = "https://spotifymate.com/action"
        payload = {"url": f"https://open.spotify.com/track/{track_id}"}
        res = requests.post(mate_url, data=payload, headers=HEADERS, timeout=10)
        
        if res.status_code == 200:
            m_link = re.search(r'href="(https://[^"]+\.(?:m4a|aac|mp4)\?[^"]+)"', res.text)
            if not m_link:
                m_link = re.search(r'href="(https://[^"]+dl[^"]+)"', res.text)
                
            if m_link:
                dl_url = html.unescape(m_link.group(1))
                logger.info(f"[LOG TERMINAL] 🟢 دریافت لینک از موتور ۲: {dl_url}")
                r = requests.get(dl_url, stream=True, headers=HEADERS, timeout=40)
                if r.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk: f.write(chunk)
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 100000:
                        logger.info("[LOG TERMINAL] ✅ دانلود مستقیم M4A انجام شد.")
                        return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ SpotifyMate Engine: {e}")

    return False

# ============================================================
# حک کردن کاور HD و متادیتا روی فایل M4A
# ============================================================
def embed_cover_and_tags_m4a(m4a_path, title, artist, cover_url):
    try:
        logger.info(f"[LOG TERMINAL] 🎨 در حال حک کردن کاور HD و متادیتا روی فایل M4A...")
        audio = MP4(m4a_path)
        
        audio["\xa9nam"] = [title]
        audio["\xa9ART"] = [artist]
        audio["\xa9alb"] = ["Spotify M4A Release"]

        if cover_url:
            r_img = requests.get(cover_url, headers=HEADERS, timeout=10)
            if r_img.status_code == 200:
                audio["covr"] = [MP4Cover(r_img.content, imageformat=MP4Cover.FORMAT_JPEG)]

        audio.save()
        logger.info(f"[LOG TERMINAL] ✅ متادیتا و کاور HD روی M4A حک شد.")
    except Exception as e:
        logger.error(f"[LOG TERMINAL] ⚠️ خطا در حک متادیتا روی M4A: {e}")

# ============================================================
# دستورات ربات
# ============================================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    text = (
        f"سلام <b>{message.from_user.first_name}</b> عزیز 👋\n\n"
        "🟢 <b>ربات دانلود مستقیم کیفیت عالی M4A (بدون MP3 و بدون یوتیوب)</b>\n\n"
        "لینک آهنگ اسپاتیفای را ارسال کنید تا فایل M4A اصلی همراه با کاور HD دریافت کنید.\n\n"
        "🔗 <b>لطفاً لینک آهنگ اسپاتیفای را ارسال کنید:</b>"
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

    # استخراج شناسه Track ID
    m = re.search(r"track/([A-Za-z0-9]{22})", url)
    if not m:
        bot.send_message(chat_id, "❌ لینک اسپاتیفای معتبر نیست.")
        return

    track_id = m.group(1)
    status_msg = bot.send_message(chat_id, "🔎 <b>در حال استخراج متادیتای دقیق اسپاتیفای...</b>")

    # ۱. استخراج متادیتا و کاور HD
    meta = get_spotify_track_meta(track_id)
    
    if not meta or not meta.get("title"):
        try:
            bot.edit_message_text("❌ متأسفانه اطلاعات این اثر دریافت نشد.", chat_id, status_msg.message_id)
        except Exception: pass
        return

    display_title = meta["title"]
    display_artist = meta.get("artist") or "Hayedeh"
    cover_url = meta.get("cover")

    try:
        bot.edit_message_text(f"📥 <b>در حال دانلود مستقیم M4A کیفیت عالی برای «{html.escape(display_artist)} - {html.escape(display_title)}»...</b>", chat_id, status_msg.message_id)
    except Exception: pass

    filename = f"track_{chat_id}_{int(time.time())}.m4a"

    # ۲. دانلود استریم اصلی M4A مستقیماً بر اساس Track ID
    success = download_m4a_direct_spotify(track_id, display_artist, display_title, filename)

    if not success or not os.path.exists(filename) or os.path.getsize(filename) < 100000:
        logger.error(f"[LOG TERMINAL] 🔴 دانلود M4A ناموفق بود.")
        try:
            bot.edit_message_text("❌ متأسفانه در دانلود فایل M4A مشکلی پیش آمد. لطفاً دوباره تلاش کنید.", chat_id, status_msg.message_id)
        except Exception: pass
        if os.path.exists(filename): os.remove(filename)
        return

    # ۳. حک کردن کاور HD اسپاتیفای و متادیتا روی فایل M4A
    embed_cover_and_tags_m4a(filename, display_title, display_artist, cover_url)

    file_size_mb = os.path.getsize(filename) / (1024 * 1024)
    logger.info(f"[LOG TERMINAL] ✅ فایل نهایی M4A آماده شد، حجم: {file_size_mb:.2f} MB")

    # ۴. ارسال عکس کاور جداگانه
    if cover_url:
        try:
            bot.send_photo(chat_id, cover_url, caption=f"🖼 <b>کاور رسمی: {html.escape(display_title)} - {html.escape(display_artist)}</b>")
        except Exception as e:
            logger.warning(f"[LOG TERMINAL] ⚠️ خطا در ارسال عکس کاور: {e}")

    try:
        try:
            bot.edit_message_text("📤 <b>در حال آپلود فایل M4A به تلگرام...</b>", chat_id, status_msg.message_id)
        except Exception: pass

        with open(filename, 'rb') as audio_file:
            caption = f"🎵 <b>{html.escape(display_title)}</b>\n🎤 <b>{html.escape(display_artist)}</b>\n\n✨ <i>فرمت صوتی M4A (AAC 320kbps) - دانلود مستقیم از سرور بدون یوتیوب</i>"
            bot.send_audio(
                chat_id=chat_id,
                audio=audio_file,
                caption=caption,
                title=display_title,
                performer=display_artist
            )
            
        logger.info(f"[LOG TERMINAL] 🎉 ارسال فایل M4A با موفقیت انجام شد!")
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
    logger.info(f"M4A Direct Bot V{VERSION} Started!")
    
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

