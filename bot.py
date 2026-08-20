# ============================================================
# ربات دانلود ۳۲۰k اسپاتیفای - نسخه بدون نیاز به اکانت / لاگین
# ============================================================

import os
import re
import json
import sys
import time
import ssl
import urllib.parse
import urllib.request
import logging
import threading
import html
import requests
import yt_dlp
from flask import Flask
import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException

# پکیج تزریق کاور و متادیتا روی فایل MP3
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, ID3NoHeaderError

# ============================================================
# تنظیمات اصلی
# ============================================================
TOKEN = "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY"
DATA_FILE = "audio_bot_db.json"
VERSION = "11.0-NoAuthHQ"

# ============================================================
# تنظیم سیستم لاگ
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("NoAuthAudioBot")

# ============================================================
# سرور Flask جهت نگهداشت آنلاین در Render
# ============================================================
app = Flask('')
@app.route('/')
def home():
    return f"NoAuth Spotify Audio Bot V:{VERSION} is Online!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

# ============================================================
# تلگرام و هدرهای شبکه
# ============================================================
bot = telebot.TeleBot(TOKEN, parse_mode="HTML", threaded=False)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ============================================================
# دیتابیس
# ============================================================
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[DB LOAD ERROR] {e}")
        return {"users": {}}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"[DB SAVE ERROR] {e}")

db = load_data()

def get_user(uid):
    uid = str(uid)
    if uid not in db["users"]:
        db["users"][uid] = {"format": "mp3"}
        save_data(db)
    return db["users"][uid]

# ============================================================
# استخراج متادیتای اسپاتیفای (نام خواننده، عنوان آهنگ و کاور HD)
# ============================================================
def get_spotify_track_meta(url):
    logger.info(f"[LOG TERMINAL] 🔍 دریافت متادیتای اسپاتیفای: {url}")
    
    m = re.search(r"track/([A-Za-z0-9]{22})", url)
    track_id = m.group(1) if m else None
    clean_url = f"https://open.spotify.com/track/{track_id}" if track_id else url

    title, artist, cover = "", "", ""

    # اسکرپ مستقیم متاتگ‌های اسپاتیفای
    try:
        req = urllib.request.Request(clean_url, headers=HEADERS)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            html_content = resp.read().decode("utf-8", errors="ignore")
            
            og_title = re.search(r'<meta property="og:title" content="(.*?)"', html_content)
            og_desc = re.search(r'<meta property="og:description" content="(.*?)"', html_content)
            og_img = re.search(r'<meta property="og:image" content="(.*?)"', html_content)
            
            if og_title: title = html.unescape(og_title.group(1).strip())
            if og_img: cover = og_img.group(1)
            
            if og_desc:
                desc = html.unescape(og_desc.group(1).strip())
                parts = [p.strip() for p in desc.split("·") if p.strip()]
                if parts:
                    artist = parts[0]
                    if artist.lower() in ["song", "single", "album"] and len(parts) > 1:
                        artist = parts[1]

            if title and artist and artist.lower() not in ["song", "single", "album"]:
                logger.info(f"[LOG TERMINAL] ✅ استخراج متادیتا موفق: خواننده='{artist}', آهنگ='{title}'")
                return {"track_id": track_id, "title": title, "artist": artist, "cover": cover}
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ HTML Scraping ناموفق: {e}")

    # Fallback به oEmbed
    try:
        oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(clean_url)}"
        req = urllib.request.Request(oembed_url, headers=HEADERS)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            t_raw = data.get("title", "").strip()
            a_raw = data.get("author_name", "").strip()
            cover_raw = data.get("thumbnail_url", "")
            
            if " - " in t_raw and not a_raw:
                parts = t_raw.split(" - ")
                t_raw, a_raw = parts[0].strip(), parts[1].strip()
                
            title = title or t_raw
            artist = artist or a_raw
            cover = cover or cover_raw
            
            if title:
                logger.info(f"[LOG TERMINAL] ✅ oEmbed موفق: خواننده='{artist}', آهنگ='{title}'")
                return {"track_id": track_id, "title": title, "artist": artist, "cover": cover}
    except Exception as e:
        logger.error(f"[LOG TERMINAL] ❌ oEmbed ناموفق: {e}")

    if title:
        return {"track_id": track_id, "title": title, "artist": artist, "cover": cover}

    return None

# ============================================================
# حک کردن کاور رسمی HD و متادیتا روی فایل صوتی (ID3 Tagging)
# ============================================================
def embed_cover_and_tags(mp3_path, title, artist, cover_url):
    try:
        logger.info(f"[LOG TERMINAL] 🎨 در حال حک کردن کاور و متادیتا روی فایل MP3...")
        try:
            audio = ID3(mp3_path)
        except ID3NoHeaderError:
            audio = ID3()

        audio.add(TIT2(encoding=3, text=title))
        audio.add(TPE1(encoding=3, text=artist))
        audio.add(TALB(encoding=3, text="Spotify HQ Release"))

        if cover_url:
            r_img = requests.get(cover_url, headers=HEADERS, timeout=15)
            if r_img.status_code == 200:
                audio.add(
                    APIC(
                        encoding=3,
                        mime='image/jpeg',
                        type=3,
                        desc='Cover',
                        data=r_img.content
                    )
                )
        audio.save(mp3_path)
        logger.info(f"[LOG TERMINAL] ✅ کاور و متادیتای ID3 با موفقیت روی فایل حک شد.")
    except Exception as e:
        logger.error(f"[LOG TERMINAL] ⚠️ خطا در حک کاور روی فایل: {e}")

# ============================================================
# استخراج سریع استریم صوتی ۳۲۰k بدون نیاز به اکانت
# ============================================================
def download_audio_stream_320k(artist, title, output_path):
    logger.info(f"[LOG TERMINAL] 🟢 شروع دانلود استریم ۳۲۰k برای: '{artist} - {title}'")

    search_term = f"{artist} {title}".strip()

    # موتور ۱: JioSaavn High Quality 320kbps API
    try:
        search_query = urllib.parse.quote(search_term)
        search_api = f"https://saavn.me/search/songs?query={search_query}&page=1&limit=1"
        res = requests.get(search_api, headers=HEADERS, timeout=15)
        if res.status_code == 200:
            results = res.json().get("data", {}).get("results", [])
            if results:
                dl_urls = results[0].get("downloadUrl", [])
                if dl_urls:
                    dl_320 = dl_urls[-1].get("link") # کیفیت ۳۲۰kbps
                    if dl_320:
                        logger.info(f"[LOG TERMINAL] ⚡️ دریافت مستقیم استریم ۳۲۰k: {dl_320}")
                        r = requests.get(dl_320, stream=True, timeout=30)
                        if r.status_code == 200:
                            with open(output_path, "wb") as f:
                                for chunk in r.iter_content(chunk_size=8192):
                                    if chunk: f.write(chunk)
                            if os.path.exists(output_path) and os.path.getsize(output_path) > 100000:
                                logger.info(f"[LOG TERMINAL] ✅ دانلود فایل ۳۲۰k انجام شد.")
                                return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Engine 1 ناموفق: {e}")

    # موتور ۲: yt-dlp iOS Web Client Bypass
    try:
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': output_path,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'extractor_args': {'youtube': {'player_client': ['ios', 'android']}},
            'headers': HEADERS,
        }
        query = f"scsearch1:{search_term}"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"[LOG TERMINAL] Trying search via yt-dlp SoundCloud: '{query}'")
            ydl.download([query])
            if os.path.exists(output_path) and os.path.getsize(output_path) > 100000:
                logger.info(f"[LOG TERMINAL] ✅ دانلود از موتور ۲ انجام شد.")
                return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Engine 2 ناموفق: {e}")

    return False

# ============================================================
# دستورات ربات
# ============================================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    get_user(message.from_user.id)
    text = (
        f"سلام <b>{message.from_user.first_name}</b> عزیز 👋\n\n"
        "🟢 <b>ربات دانلود موزیک اسپاتیفای با کیفیت ۳۲۰k</b>\n\n"
        "بدون نیاز به لاگین یا حساب کاربری، لینک اسپاتیفای را بفرستید تا فایل ۳۲۰k همراه با کاور HD اصلی ارسال شود.\n\n"
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

    status_msg = bot.send_message(chat_id, "🔎 <b>در حال استخراج متادیتای دقیق اسپاتیفای...</b>")

    # ۱. استخراج متادیتا و کاور HD
    meta = get_spotify_track_meta(url)
    
    if not meta or not meta.get("title"):
        try:
            bot.edit_message_text("❌ متأسفانه لینک اسپاتیفای معتبر نیست یا اثر یافت نشد.", chat_id, status_msg.message_id)
        except Exception: pass
        return

    display_title = meta["title"]
    display_artist = meta["artist"] or "Spotify Artist"
    cover_url = meta.get("cover")
    
    try:
        bot.edit_message_text(f"📥 <b>در حال دانلود «{html.escape(display_artist)} - {html.escape(display_title)}» با کیفیت ۳۲۰k...</b>", chat_id, status_msg.message_id)
    except Exception: pass

    filename = f"spotify_{chat_id}_{int(time.time())}.mp3"

    # ۲. دانلود استریم ۳۲۰k بدون نیاز به لاگین
    success = download_audio_stream_320k(display_artist, display_title, filename)

    if not success or not os.path.exists(filename) or os.path.getsize(filename) < 100000:
        logger.error(f"[LOG TERMINAL] 🔴 دانلود فایل صوتی ناموفق بود.")
        try:
            bot.edit_message_text("❌ متأسفانه در دریافت فایل صوتی خطایی رخ داد. لطفاً مجدداً امتحان کنید.", chat_id, status_msg.message_id)
        except Exception: pass
        if os.path.exists(filename): os.remove(filename)
        return

    # ۳. حک کردن کاور HD اسپاتیفای و تگ‌های اصلی روی فایل صوتی
    embed_cover_and_tags(filename, display_title, display_artist, cover_url)

    file_size_mb = os.path.getsize(filename) / (1024 * 1024)
    logger.info(f"[LOG TERMINAL] ✅ فایل نهایی آماده شد: '{filename}', حجم: {file_size_mb:.2f} MB")

    # ۴. ارسال عکس کاور جداگانه
    if cover_url:
        try:
            bot.send_photo(chat_id, cover_url, caption=f"🖼 <b>کاور رسمی: {html.escape(display_title)} - {html.escape(display_artist)}</b>")
        except Exception as e:
            logger.warning(f"[LOG TERMINAL] ⚠️ خطا در ارسال عکس کاور: {e}")

    try:
        try:
            bot.edit_message_text("📤 <b>در حال آپلود فایل صوتی به تلگرام...</b>", chat_id, status_msg.message_id)
        except Exception: pass

        logger.info(f"[LOG TERMINAL] 📤 در حال ارسال فایل صوتی به تلگرام برای کاربر {uid}...")

        with open(filename, 'rb') as audio_file:
            caption = f"🎵 <b>{html.escape(display_title)}</b>\n🎤 <b>{html.escape(display_artist)}</b>\n\n💎 <i>کیفیت صوتی ۳۲۰kbps - همراه با کاور حک‌شده روی فایل</i>"
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
                logger.info(f"[LOG TERMINAL] 🧹 فایل موقت سرور پاکسازی شد.")
            except Exception: pass

# ============================================================
# اجرای ربات با مدیریت ۴۰۹
# ============================================================
if __name__ == "__main__":
    logger.info(f"NoAuth Spotify Bot V{VERSION} Started!")
    
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

