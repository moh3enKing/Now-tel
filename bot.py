# ============================================================
# ربات دانلود صوتی اورجینال اسپاتیفای - نسخه ۱.۰ (با لاگ ترمینال)
# استخراج مستقیم استریم نیتیو بدون هیچ‌گونه تبدیل فرمت
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
import yt_dlp
from flask import Flask
import telebot
from telebot import types

# ============================================================
# تنظیمات اصلی
# ============================================================
TOKEN = "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY"
DATA_FILE = "audio_bot_db.json"
VERSION = "1.0"

# ============================================================
# تنظیم سیستم لاگ پایتون جهت نمایش لحظه‌ای در ترمینال Render
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("AudioBot")

# ============================================================
# سرور Flask جهت نگهداشت آنلاین در Render
# ============================================================
app = Flask('')
@app.route('/')
def home():
    return f"Spotify Audio Bot V:{VERSION} is Online!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

# ============================================================
# تلگرام و هدرهای شبکه
# ============================================================
bot = telebot.TeleBot(TOKEN, parse_mode="HTML", threaded=False)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
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
        logger.error(f"[LOG TERMINAL] DB Load Error: {e}")
        return {"users": {}}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"[LOG TERMINAL] DB Save Error: {e}")

db = load_data()

def get_user(uid):
    uid = str(uid)
    if uid not in db["users"]:
        db["users"][uid] = {"format": "auto"}
        save_data(db)
    return db["users"][uid]

# ============================================================
# استخراج متادیتای اسپاتیفای
# ============================================================
def get_spotify_metadata(url):
    logger.info(f"[LOG TERMINAL] 🔍 Step 1: Extracting Spotify metadata for URL: {url}")
    
    # روش ۱: oEmbed API
    try:
        api_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(url)}"
        req = urllib.request.Request(api_url, headers=HEADERS)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            title = data.get("title", "").strip()
            artist = data.get("author_name", "").strip()
            thumbnail = data.get("thumbnail_url", "")
            
            if " - " in title and not artist:
                parts = title.split(" - ")
                title = parts[0].strip()
                artist = parts[1].strip()
                
            logger.info(f"[LOG TERMINAL] ✅ oEmbed Success: Artist='{artist}', Title='{title}'")
            if title:
                return {"title": title, "artist": artist, "thumbnail": thumbnail}
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ oEmbed failed: {e}")

    # روش ۲: HTML Scraping
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            html_text = resp.read().decode("utf-8", errors="ignore")
            
            m_title = re.search(r'<meta property="og:title" content="(.*?)"', html_text)
            m_desc = re.search(r'<meta property="og:description" content="(.*?)"', html_text)
            m_img = re.search(r'<meta property="og:image" content="(.*?)"', html_text)
            
            t = m_title.group(1).strip() if m_title else ""
            d = m_desc.group(1).strip() if m_desc else ""
            img = m_img.group(1) if m_img else ""
            
            artist = d.split("·")[0].strip() if "·" in d else ""
            logger.info(f"[LOG TERMINAL] ✅ HTML Scraping Success: Artist='{artist}', Title='{t}'")
            if t:
                return {"title": t, "artist": artist, "thumbnail": img}
    except Exception as e:
        logger.error(f"[LOG TERMINAL] ❌ HTML Scraping failed: {e}")

    return None

# ============================================================
# کیبوردها
# ============================================================
def settings_keyboard(uid):
    user_format = get_user(uid).get("format", "auto")
    
    btn_auto = "✅ Auto (بهترین استریم نیتیو)" if user_format == "auto" else "Auto (بهترین استریم نیتیو)"
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
    logger.info(f"[LOG TERMINAL] New user start: ID={uid}, Name='{message.from_user.first_name}'")
    
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
        logger.info(f"[LOG TERMINAL] User {uid} changed format to: {new_fmt}")
        
        try:
            bot.edit_message_reply_markup(chat_id, mid, reply_markup=settings_keyboard(uid))
            bot.answer_callback_query(call.id, f"فرمت به {new_fmt.upper()} تغییر یافت ✅")
        except Exception: pass

# ============================================================
# دریافت لینک و دانلود نیتیو
# ============================================================
@bot.message_handler(func=lambda m: "spotify.com" in (m.text or ""))
def handle_spotify_link(message):
    chat_id = message.chat.id
    uid = str(message.from_user.id)
    url = message.text.strip()

    logger.info(f"[LOG TERMINAL] --------------------------------------------------")
    logger.info(f"[LOG TERMINAL] New download request from User ID {uid}: {url}")

    status_msg = bot.send_message(chat_id, "🔎 <b>در حال استخراج متادیتای اسپاتیفای...</b>")
    
    # ۱. استخراج متادیتا
    meta = get_spotify_metadata(url)
    
    if meta and meta.get("artist") and meta.get("title"):
        search_query = f"ytsearch1:{meta['artist']} - {meta['title']}"
        display_title = meta["title"]
        display_artist = meta["artist"]
    elif meta and meta.get("title"):
        search_query = f"ytsearch1:{meta['title']}"
        display_title = meta["title"]
        display_artist = "Spotify Artist"
    else:
        search_query = url
        display_title = "Unknown Song"
        display_artist = "Spotify"

    logger.info(f"[LOG TERMINAL] 🚀 Step 2: Querying yt-dlp with search term: '{search_query}'")
    
    try:
        bot.edit_message_text("📥 <b>در حال استخراج و دریافت فایل صوتی نیتیو...</b>", chat_id, status_msg.message_id)
    except Exception: pass

    user_fmt = get_user(uid).get("format", "auto")
    
    if user_fmt == "m4a":
        fmt_str = "bestaudio[ext=m4a]/bestaudio"
    elif user_fmt == "webm":
        fmt_str = "bestaudio[ext=webm]/bestaudio"
    else:
        fmt_str = "bestaudio/best"

    out_template = f"native_audio_{chat_id}_{int(time.time())}.%(ext)s"

    ydl_opts = {
        'format': fmt_str,
        'outtmpl': out_template,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }

    downloaded_file = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"[LOG TERMINAL] Executing yt-dlp download...")
            info_dict = ydl.extract_info(search_query, download=True)
            
            if 'entries' in info_dict and info_dict['entries']:
                info_dict = info_dict['entries'][0]
                
            downloaded_file = ydl.prepare_filename(info_dict)
            file_size_mb = os.path.getsize(downloaded_file) / (1024 * 1024) if os.path.exists(downloaded_file) else 0
            
            logger.info(f"[LOG TERMINAL] ✅ Downloaded File: '{downloaded_file}', Size: {file_size_mb:.2f} MB")

        try:
            bot.edit_message_text("📤 <b>در حال آپلود فایل در تلگرام...</b>", chat_id, status_msg.message_id)
        except Exception: pass

        logger.info(f"[LOG TERMINAL] 📤 Step 3: Uploading audio file to Telegram chat ID: {chat_id}")

        with open(downloaded_file, 'rb') as audio_file:
            caption = f"🎵 <b>{html.escape(display_title)}</b>\n🎤 {html.escape(display_artist)}\n\n💎 <i>فایل اورجینال - استریم خام بدون هیچ‌گونه تبدیل فرمت</i>"
            bot.send_audio(
                chat_id=chat_id,
                audio=audio_file,
                caption=caption,
                title=display_title,
                performer=display_artist
            )
            
        logger.info(f"[LOG TERMINAL] 🎉 SUCCESS: Audio sent to user {uid} successfully!")
        try: bot.delete_message(chat_id, status_msg.message_id)
        except Exception: pass

    except Exception as e:
        logger.error(f"[LOG TERMINAL] 🔴 FAILED to process audio: {e}", exc_info=True)
        try:
            bot.edit_message_text("❌ متأسفانه در استخراج این اثر مشکلی پیش آمد. لطفاً مجدداً امتحان کنید.", chat_id, status_msg.message_id)
        except Exception: pass
        
    finally:
        if downloaded_file and os.path.exists(downloaded_file):
            try:
                os.remove(downloaded_file)
                logger.info(f"[LOG TERMINAL] 🧹 Cleanup: Local file '{downloaded_file}' deleted.")
            except Exception as e:
                logger.error(f"[LOG TERMINAL] Cleanup error: {e}")

if __name__ == "__main__":
    logger.info(f"Audio Bot V{VERSION} Started!")
    
    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception: pass

    bot.infinity_polling(skip_pending=True, none_stop=True, timeout=30)

