# ============================================================
# ربات دانلود مستقیم صوتی اسپاتیفای - نسخه ۳.۱ (اصلاح کامل متادیتای خواننده)
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
import yt_dlp
from flask import Flask
import telebot
from telebot import types

# ============================================================
# تنظیمات اصلی
# ============================================================
TOKEN = "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY"
DATA_FILE = "audio_bot_db.json"
VERSION = "3.1-FixMetadata"

# ============================================================
# تنظیم سیستم لاگ پایتون
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("PureAudioBot")

# ============================================================
# سرور Flask جهت نگهداشت آنلاین در Render
# ============================================================
app = Flask('')
@app.route('/')
def home():
    return f"Pure Audio Bot V:{VERSION} is Online!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

# ============================================================
# تلگرام و هدرهای واقعی مرورگر
# ============================================================
bot = telebot.TeleBot(TOKEN, parse_mode="HTML", threaded=False)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
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
        db["users"][uid] = {"format": "auto"}
        save_data(db)
    return db["users"][uid]

# ============================================================
# استخراج هوشمند متادیتای اسپاتیفای (تضمین دریافت خواننده)
# ============================================================
def get_spotify_track_meta(url):
    logger.info(f"[LOG TERMINAL] 🔍 دریافت متادیتای مستقیم اسپاتیفای: {url}")
    
    m = re.search(r"track/([A-Za-z0-9]{22})", url)
    clean_url = f"https://open.spotify.com/track/{m.group(1)}" if m else url

    title, artist, cover = "", "", ""

    # ۱. متد اول: اسکرپ مستقیم HTML (بسیار دقیق برای آهنگ‌های ایرانی)
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
                # اسپاتیفای توضیحات را با · یا by جدا می‌کند
                parts = [p.strip() for p in desc.split("·") if p.strip()]
                if parts:
                    artist = parts[0]
                    # پاک‌سازی کلمات اضافه مانند Song یا Single
                    if artist.lower() in ["song", "single", "album"] and len(parts) > 1:
                        artist = parts[1]

            if title and artist and artist.lower() not in ["song", "single", "album"]:
                logger.info(f"[LOG TERMINAL] ✅ HTML Scraping موفق: خواننده='{artist}', آهنگ='{title}'")
                return {"title": title, "artist": artist, "cover": cover}
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ HTML Scraping ناموفق: {e}")

    # ۲. متد دوم: oEmbed Fallback
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
                return {"title": title, "artist": artist, "cover": cover}
    except Exception as e:
        logger.error(f"[LOG TERMINAL] ❌ oEmbed ناموفق: {e}")

    if title:
        return {"title": title, "artist": artist, "cover": cover}

    return None

# ============================================================
# کیبوردها
# ============================================================
def settings_keyboard(uid):
    user_format = get_user(uid).get("format", "auto")
    
    btn_auto = "✅ Auto (بالاترین کیفیت استریم نیتیو)" if user_format == "auto" else "Auto (بالاترین کیفیت استریم نیتیو)"
    btn_m4a = "✅ M4A (فرمت AAC)" if user_format == "m4a" else "M4A (فرمت AAC)"
    btn_webm = "✅ WEBM (فرمت Opus)" if user_format == "webm" else "WEBM (فرمت Opus)"

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(btn_auto, callback_data="set_fmt_auto"))
    kb.add(types.InlineKeyboardButton(btn_m4a, callback_data="set_fmt_m4a"))
    kb.add(types.InlineKeyboardButton(btn_webm, callback_data="set_fmt_webm"))
    kb.add(types.InlineKeyboardButton("بستن ❌", callback_data="close_panel"))
    return kb

def main_reply_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(types.KeyboardButton("⚙️ تنظیمات فرمت"))
    return kb

# ============================================================
# دستورات
# ============================================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    uid = message.from_user.id
    get_user(uid)
    logger.info(f"[LOG TERMINAL] کاربر استارت زد: ID={uid}, Name='{message.from_user.first_name}'")
    
    text = (
        f"سلام <b>{message.from_user.first_name}</b> عزیز 👋\n\n"
        "من ربات دانلود <b>مستقیم و اورجینال</b> فایل‌های صوتی اسپاتیفای هستم.\n"
        "فایل‌ها <u>بدون هیچ‌گونه تبدیل فرمت یا افت کیفیت</u>، مستقیماً از استریم خام دریافت و ارسال می‌شوند.\n\n"
        "🔗 <b>لطفاً لینک آهنگ اسپاتیفای خود را بفرستید:</b>"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_reply_keyboard())

@bot.message_handler(func=lambda m: m.text == "⚙️ تنظیمات فرمت" or m.text == "/settings")
def show_settings(message):
    uid = message.from_user.id
    text = (
        "⚙️ <b>تنظیمات فرمت فایل خروجی</b>\n\n"
        "از آنجا که فایل‌ها تبدیل (Convert) نمی‌شوند، می‌توانید انتخاب کنید کدام استریم خام دانلود شود:\n\n"
        "🔹 <b>Auto:</b> بالاترین کیفیت استریم موجود.\n"
        "🔹 <b>M4A:</b> فرمت خام AAC (پشتیبانی عالی در آیفون، اندروید و تلگرام).\n"
        "🔹 <b>WEBM:</b> فرمت خام Opus (کیفیت بسیار بالا)."
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
        logger.info(f"[LOG TERMINAL] فرمت کاربر {uid} به {new_fmt} تغییر یافت.")
        
        try:
            bot.edit_message_reply_markup(chat_id, mid, reply_markup=settings_keyboard(uid))
            bot.answer_callback_query(call.id, f"فرمت به {new_fmt.upper()} تغییر یافت ✅")
        except Exception: pass

# ============================================================
# پردازش لینک و استخراج نیتیو فایل صوتی
# ============================================================
@bot.message_handler(func=lambda m: "spotify.com" in (m.text or ""))
def handle_spotify_link(message):
    chat_id = message.chat.id
    uid = str(message.from_user.id)
    url = message.text.strip()

    logger.info(f"[LOG TERMINAL] --------------------------------------------------")
    logger.info(f"[LOG TERMINAL] درخواست جدید از کاربر {uid}: {url}")

    status_msg = bot.send_message(chat_id, "🔎 <b>در حال دریافت اطلاعات اثر از اسپاتیفای...</b>")

    # ۱. استخراج مستقیم اطلاعات اسپاتیفای
    meta = get_spotify_track_meta(url)
    
    if not meta or not meta.get("title"):
        try:
            bot.edit_message_text("❌ متأسفانه لینک اسپاتیفای معتبر نیست یا اثر یافت نشد.", chat_id, status_msg.message_id)
        except Exception: pass
        return

    display_title = meta["title"]
    display_artist = meta["artist"]
    
    # ساخت کلمه سرچ دقیق بدون کلمه Spotify
    if display_artist:
        search_query = f"ytsearch1:{display_artist} {display_title}"
    else:
        search_query = f"ytsearch1:{display_title}"

    logger.info(f"[LOG TERMINAL] 🚀 استخراج استریم صوتی برای: '{display_artist} - {display_title}' با عبارت '{search_query}'")
    
    try:
        bot.edit_message_text("📥 <b>در حال استخراج و دانلود مستقیم استریم اورجینال...</b>", chat_id, status_msg.message_id)
    except Exception: pass

    user_fmt = get_user(uid).get("format", "auto")
    
    if user_fmt == "m4a":
        fmt_str = "bestaudio[ext=m4a]/bestaudio"
    elif user_fmt == "webm":
        fmt_str = "bestaudio[ext=webm]/bestaudio"
    else:
        fmt_str = "bestaudio/best"

    out_template = f"pure_audio_{chat_id}_{int(time.time())}.%(ext)s"

    # موتور استخراج هوشمند استریم خام نیتیو
    ydl_opts = {
        'format': fmt_str,
        'outtmpl': out_template,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'headers': HEADERS,
    }

    downloaded_file = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"[LOG TERMINAL] Searching/Downloading via yt-dlp: '{search_query}'")
            info_dict = ydl.extract_info(search_query, download=True)
            
            if 'entries' in info_dict and info_dict['entries']:
                info_dict = info_dict['entries'][0]
                
            downloaded_file = ydl.prepare_filename(info_dict)
            file_size_mb = os.path.getsize(downloaded_file) / (1024 * 1024) if os.path.exists(downloaded_file) else 0
            
            logger.info(f"[LOG TERMINAL] ✅ فایل صوتی آماده شد: '{downloaded_file}', حجم: {file_size_mb:.2f} MB")

        try:
            bot.edit_message_text("📤 <b>در حال آپلود فایل صوتی به تلگرام...</b>", chat_id, status_msg.message_id)
        except Exception: pass

        logger.info(f"[LOG TERMINAL] 📤 در حال آپلود فایل به تلگرام برای کاربر {uid}...")

        with open(downloaded_file, 'rb') as audio_file:
            caption = f"🎵 <b>{html.escape(display_title)}</b>\n🎤 {html.escape(display_artist or 'Unknown Artist')}\n\n💎 <i>استریم خام - بدون حتی ۱٪ تبدیل یا افت کیفیت</i>"
            bot.send_audio(
                chat_id=chat_id,
                audio=audio_file,
                caption=caption,
                title=display_title,
                performer=display_artist or "Spotify Artist"
            )
            
        logger.info(f"[LOG TERMINAL] 🎉 ارسال فایل با موفقیت انجام شد!")
        try: bot.delete_message(chat_id, status_msg.message_id)
        except Exception: pass

    except Exception as e:
        logger.error(f"[LOG TERMINAL] 🔴 خطا در فرایند استخراج: {e}", exc_info=True)
        try:
            bot.edit_message_text("❌ متأسفانه در دریافت فایل صوتی مشکلی پیش آمد. لطفاً مجدداً امتحان کنید.", chat_id, status_msg.message_id)
        except Exception: pass
        
    finally:
        if downloaded_file and os.path.exists(downloaded_file):
            try:
                os.remove(downloaded_file)
                logger.info(f"[LOG TERMINAL] 🧹 فایل موقت پاکسازی شد.")
            except Exception: pass

if __name__ == "__main__":
    logger.info(f"Pure Audio Bot V{VERSION} Started!")
    
    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception: pass

    bot.infinity_polling(skip_pending=True, none_stop=True, timeout=30)

