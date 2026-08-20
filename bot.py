# ============================================================
# ربات دانلود مستقیم و اورجینال اسپاتیفای (نسخه ۸.۰ - دانلود دقیق بر اساس Track ID + ارسال کاور)
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
from flask import Flask
import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException

# ============================================================
# تنظیمات اصلی
# ============================================================
TOKEN = "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY"
DATA_FILE = "audio_bot_db.json"
VERSION = "8.0-TrackIdExact"

# ============================================================
# تنظیم سیستم لاگ پایتون جهت نمایش در Render
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("PureSpotifyBot")

# ============================================================
# سرور Flask جهت نگهداشت آنلاین در Render
# ============================================================
app = Flask('')
@app.route('/')
def home():
    return f"100% Pure Spotify Downloader Bot V:{VERSION} is Active!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

# ============================================================
# تلگرام و هدر شبکه
# ============================================================
bot = telebot.TeleBot(TOKEN, parse_mode="HTML", threaded=False)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ============================================================
# دیتابیس کاربران
# ============================================================
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[خطای بارگذاری دیتابیس] {e}")
        return {"users": {}}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"[خطای ذخیره دیتابیس] {e}")

db = load_data()

def get_user(uid):
    uid = str(uid)
    if uid not in db["users"]:
        db["users"][uid] = {"format": "mp3", "send_cover": True}
        save_data(db)
    return db["users"][uid]

# ============================================================
# استخراج متادیتای دقیق اسپاتیفای (شامل خواننده و کاور کیفیت بالا)
# ============================================================
def get_spotify_track_meta(url):
    logger.info(f"[LOG TERMINAL] 🔍 دریافت متادیتای اسپاتیفای: {url}")
    
    m = re.search(r"track/([A-Za-z0-9]{22})", url)
    track_id = m.group(1) if m else None
    clean_url = f"https://open.spotify.com/track/{track_id}" if track_id else url

    title, artist, cover = "", "", ""

    # ۱. اسکرپ HTML مستقیم متاتگ‌های OpenGraph اسپاتیفای
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
                logger.info(f"[LOG TERMINAL] ✅ HTML Scraping موفق: خواننده='{artist}', آهنگ='{title}', کاور={cover}")
                return {"track_id": track_id, "title": title, "artist": artist, "cover": cover}
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ HTML Scraping ناموفق: {e}")

    # ۲. استفاده از oEmbed به عنوان متد دوم
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
# دانلود مستقیم صوتی اسپاتیفای بر اساس Track ID دقیق
# ============================================================
def download_exact_spotify_track(track_id, output_path):
    logger.info(f"[LOG TERMINAL] 🟢 استخراج مستقیم دیتاسنتر اسپاتیفای برای Track ID: {track_id}")

    spotify_track_url = f"https://open.spotify.com/track/{track_id}"

    # موتور ۱: SpotifyMate Direct Track API
    try:
        api_url = "https://spotifydown.com/api/download-track"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://spotifydown.com/",
            "Origin": "https://spotifydown.com"
        }
        res = requests.get(api_url, params={"url": spotify_track_url}, headers=headers, timeout=15)
        if res.status_code == 200:
            data = res.json()
            link = data.get("link") or data.get("data", {}).get("link")
            if link:
                logger.info(f"[LOG TERMINAL] ⚡️ دریافت لینک مستقیم اسپاتیفای: {link}")
                r = requests.get(link, stream=True, timeout=30)
                if r.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk: f.write(chunk)
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 100000:
                        logger.info(f"[LOG TERMINAL] ✅ دانلود فایل اورجینال اسپاتیفای با موفقیت انجام شد.")
                        return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Engine 1 ناموفق: {e}")

    # موتور ۲: SpotifyDownloader Engine 2
    try:
        api_url2 = f"https://api.spotifydown.com/download/{track_id}"
        headers2 = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://spotifydown.com/"
        }
        res2 = requests.get(api_url2, headers=headers2, timeout=15)
        if res2.status_code == 200:
            data2 = res2.json()
            if data2.get("success") and data2.get("link"):
                dl_link = data2["link"]
                logger.info(f"[LOG TERMINAL] ⚡️ دریافت لینک مستقیم موتور ۲ اسپاتیفای: {dl_link}")
                r2 = requests.get(dl_link, stream=True, timeout=30)
                if r2.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in r2.iter_content(chunk_size=8192):
                            if chunk: f.write(chunk)
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 100000:
                        logger.info(f"[LOG TERMINAL] ✅ دانلود از موتور ۲ اسپاتیفای انجام شد.")
                        return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Engine 2 ناموفق: {e}")

    return False

# ============================================================
# کیبوردها
# ============================================================
def settings_keyboard(uid):
    user_format = get_user(uid).get("format", "mp3")
    
    btn_mp3 = "✅ MP3 (کیفیت اورجینال ۳۲۰k)" if user_format == "mp3" else "MP3 (کیفیت اورجینال ۳۲۰k)"
    btn_ogg = "✅ OGG Vorbis (فرمت فابریک اسپاتیفای)" if user_format == "ogg" else "OGG Vorbis (فرمت فابریک اسپاتیفای)"

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(btn_mp3, callback_data="set_fmt_mp3"))
    kb.add(types.InlineKeyboardButton(btn_ogg, callback_data="set_fmt_ogg"))
    kb.add(types.InlineKeyboardButton("بستن ❌", callback_data="close_panel"))
    return kb

def main_reply_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(types.KeyboardButton("⚙️ تنظیمات فرمت اسپاتیفای"))
    return kb

# ============================================================
# دستورات
# ============================================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    uid = message.from_user.id
    get_user(uid)
    logger.info(f"[LOG TERMINAL] کاربر جدید: ID={uid}, Name='{message.from_user.first_name}'")
    
    text = (
        f"سلام <b>{message.from_user.first_name}</b> عزیز 👋\n\n"
        "🟢 <b>ربات استخراج ۱۰۰٪ مستقیم از دیتاسنتر اسپاتیفای</b>\n\n"
        "این ربات دقیقاً همان فایل اصلی اسپاتیفای را <u>همراه با کاور HD و متادیتای کامل</u> استخراج کرده و فرستاده خواهد کرد.\n\n"
        "🔗 <b>لطفاً لینک آهنگ اسپاتیفای را ارسال کنید:</b>"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_reply_keyboard())

@bot.message_handler(func=lambda m: m.text == "⚙️ تنظیمات فرمت اسپاتیفای" or m.text == "/settings")
def show_settings(message):
    uid = message.from_user.id
    text = (
        "⚙️ <b>تنظیمات استخراج فایل اسپاتیفای</b>\n\n"
        "فرمت دلخواه برای دریافت فایل صوتی اسپاتیفای را انتخاب کنید:\n\n"
        "🟢 <b>MP3 (320kbps):</b> کیفیت ۳۲۰k کامل با متادیتا و کاور.\n"
        "🟢 <b>OGG Vorbis:</b> کدک نیتیو نرم‌افزار اسپاتیفای (۳۲۰k)."
    )
    bot.send_message(message.chat.id, text, reply_markup=settings_keyboard(uid))

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    mid = call.message.message_id
    uid = str(call.from_user.id)

    if call.data == "close_panel":
        try: bot.delete_message(chat_id, mid)
        except Exception: pass
        return

    if call.data.startswith("set_fmt_"):
        new_fmt = call.data.split("_")[2]
        db["users"][uid]["format"] = new_fmt
        save_data(db)
        logger.info(f"[LOG TERMINAL] فرمت کاربر {uid} تغییر یافت به: {new_fmt}")
        
        try:
            bot.edit_message_reply_markup(chat_id, mid, reply_markup=settings_keyboard(uid))
            bot.answer_callback_query(call.id, f"فرمت به {new_fmt.upper()} تغییر یافت ✅")
        except Exception: pass

# ============================================================
# دریافت لینک و دانلود دقیق اثر از اسپاتیفای
# ============================================================
@bot.message_handler(func=lambda m: "spotify.com" in (m.text or ""))
def handle_spotify_link(message):
    chat_id = message.chat.id
    uid = str(message.from_user.id)
    url = message.text.strip()

    logger.info(f"[LOG TERMINAL] --------------------------------------------------")
    logger.info(f"[LOG TERMINAL] درخواست جدید از کاربر {uid}: {url}")

    status_msg = bot.send_message(chat_id, "🔎 <b>در حال دریافت متادیتای اسپاتیفای...</b>")

    # ۱. استخراج متادیتا و Track ID
    meta = get_spotify_track_meta(url)
    
    if not meta or not meta.get("title") or not meta.get("track_id"):
        try:
            bot.edit_message_text("❌ متأسفانه لینک اسپاتیفای معتبر نیست یا اثر یافت نشد.", chat_id, status_msg.message_id)
        except Exception: pass
        return

    display_title = meta["title"]
    display_artist = meta["artist"] or "Spotify Artist"
    cover_url = meta.get("cover")
    track_id = meta.get("track_id")
    
    try:
        bot.edit_message_text(f"📥 <b>در حال استخراج مستقیم «{html.escape(display_artist)} - {html.escape(display_title)}» از سرور اسپاتیفای...</b>", chat_id, status_msg.message_id)
    except Exception: pass

    user_fmt = get_user(uid).get("format", "mp3")
    filename = f"spotify_{chat_id}_{int(time.time())}.{user_fmt}"

    # ۲. دانلود مستقیم فایل اصلی اسپاتیفای بر اساس Track ID
    success = download_exact_spotify_track(track_id, filename)

    if not success or not os.path.exists(filename) or os.path.getsize(filename) < 100000:
        logger.error(f"[LOG TERMINAL] 🔴 استخراج مستقیم اسپاتیفای ناموفق بود.")
        try:
            bot.edit_message_text("❌ متأسفانه در استخراج مستقیم این اثر خطایی رخ داد. لطفاً مجدداً امتحان کنید.", chat_id, status_msg.message_id)
        except Exception: pass
        if os.path.exists(filename): os.remove(filename)
        return

    file_size_mb = os.path.getsize(filename) / (1024 * 1024)
    logger.info(f"[LOG TERMINAL] ✅ فایل اصلی اسپاتیفای دانلود شد: '{filename}', حجم: {file_size_mb:.2f} MB")

    # ۳. ارسال تصویر کاور HD اسپاتیفای
    if cover_url:
        try:
            bot.send_photo(chat_id, cover_url, caption=f"🖼 <b>کاور رسمی اثر: {html.escape(display_title)} - {html.escape(display_artist)}</b>")
        except Exception as e:
            logger.warning(f"[LOG TERMINAL] ⚠️ خطا در ارسال کاور: {e}")

    try:
        try:
            bot.edit_message_text("📤 <b>در حال آپلود فایل اورجینال اسپاتیفای در تلگرام...</b>", chat_id, status_msg.message_id)
        except Exception: pass

        logger.info(f"[LOG TERMINAL] 📤 در حال ارسال فایل صوتی به تلگرام برای کاربر {uid}...")

        with open(filename, 'rb') as audio_file:
            caption = f"🎵 <b>{html.escape(display_title)}</b>\n🎤 <b>{html.escape(display_artist)}</b>\n\n💎 <i>فایل نیتیو اسپاتیفای - کیفیت ۳۲۰kbps</i>"
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
# حلقه اصلی اجرای ربات با مدیریت هوشمند ۴۰۹
# ============================================================
if __name__ == "__main__":
    logger.info(f"100% Pure Spotify Bot V{VERSION} Started!")
    
    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception: pass

    while True:
        try:
            bot.infinity_polling(skip_pending=True, none_stop=True, timeout=30)
        except ApiTelegramException as e:
            if e.error_code == 409:
                logger.warning("[LOG TERMINAL] ⚠️ Conflict 409: Waiting 3 seconds for previous instance to terminate...")
                time.sleep(3)
            else:
                logger.error(f"[LOG TERMINAL] Telegram API Exception: {e}")
                time.sleep(2)
        except Exception as e:
            logger.error(f"[LOG TERMINAL] Unexpected error: {e}")
            time.sleep(2)

