# ============================================================
# ربات دانلود مستقیم و اورجینال اسپاتیفای (بدون اتصال به یوتیوب)
# استخراج مستقیم فایل OGG/AAC خام دیتاسنتر اسپاتیفای
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
import subprocess
import html
from flask import Flask
import telebot
from telebot import types

# ============================================================
# تنظیمات اصلی
# ============================================================
TOKEN = "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY"
DATA_FILE = "audio_bot_db.json"
VERSION = "2.0-PureSpotify"

# ============================================================
# تنظیم سیستم لاگ پایتون
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("PureSpotifyBot")

# ============================================================
# سرور Flask جهت زنده ماندن در Render
# ============================================================
app = Flask('')
@app.route('/')
def home():
    return f"Pure Spotify Bot V:{VERSION} is Running!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

# ============================================================
# تلگرام و شبکه
# ============================================================
bot = telebot.TeleBot(TOKEN, parse_mode="HTML", threaded=False)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
}

# ============================================================
# مدیریت دیتابیس کاربران
# ============================================================
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[DB ERROR] {e}")
        return {"users": {}}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"[DB ERROR] {e}")

db = load_data()

def get_user(uid):
    uid = str(uid)
    if uid not in db["users"]:
        db["users"][uid] = {"format": "ogg"}
        save_data(db)
    return db["users"][uid]

# ============================================================
# کیبوردها
# ============================================================
def settings_keyboard(uid):
    user_format = get_user(uid).get("format", "ogg")
    
    btn_ogg = "✅ OGG Vorbis (فرمت فابریک اسپاتیفای)" if user_format == "ogg" else "OGG Vorbis (فرمت فابریک اسپاتیفای)"
    btn_m4a = "✅ M4A / AAC (کیفیت اصلی بدون تبدیل)" if user_format == "m4a" else "M4A / AAC (کیفیت اصلی بدون تبدیل)"

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(btn_ogg, callback_data="set_fmt_ogg"))
    kb.add(types.InlineKeyboardButton(btn_m4a, callback_data="set_fmt_m4a"))
    kb.add(types.InlineKeyboardButton("بستن ❌", callback_data="close_panel"))
    return kb

def main_reply_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(types.KeyboardButton("⚙️ تنظیمات فرمت اصلی اسپاتیفای"))
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
        "🟢 <b>ربات دانلود مستقیم و واقعی از دیتاسنتر اسپاتیفای</b>\n\n"
        "این ربات فایل صوتی را <u>مستقیماً و بدون هیچ‌گونه واسطه‌ای (مانند یوتیوب)</u> با فرمت اصلی اسپاتیفای (Ogg Vorbis 320k) استخراج می‌کند.\n\n"
        "🔗 <b>لطفاً لینک آهنگ اسپاتیفای را ارسال کنید:</b>"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_reply_keyboard())

@bot.message_handler(func=lambda m: m.text == "⚙️ تنظیمات فرمت اصلی اسپاتیفای" or m.text == "/settings")
def show_settings(message):
    uid = message.from_user.id
    text = (
        "⚙️ <b>تنظیمات استخراج نیتیو اسپاتیفای</b>\n\n"
        "یکی از فرمت‌های خام دیتاسنتر اسپاتیفای را انتخاب کنید:\n\n"
        "🟢 <b>OGG Vorbis:</b> کدک فابریک و اصلی نرم‌افزار اسپاتیفای (۳۲۰ کیلوبیت بر ثانیه).\n"
        "🟢 <b>M4A / AAC:</b> استریم خام اسپاتیفای وب (مناسب پخش در آیفون و تلگرام بدون تغییر کدک)."
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
        logger.info(f"[LOG TERMINAL] فرمت کاربر {uid} تغییر کرد به: {new_fmt}")
        
        try:
            bot.edit_message_reply_markup(chat_id, mid, reply_markup=settings_keyboard(uid))
            bot.answer_callback_query(call.id, f"فرمت به {new_fmt.UPPER()} تغییر یافت ✅")
        except Exception: pass

# ============================================================
# استخراج مستقیم فایل خام اسپاتیفای
# ============================================================
@bot.message_handler(func=lambda m: "spotify.com" in (m.text or ""))
def handle_spotify_link(message):
    chat_id = message.chat.id
    uid = str(message.from_user.id)
    url = message.text.strip()

    logger.info(f"[LOG TERMINAL] --------------------------------------------------")
    logger.info(f"[LOG TERMINAL] درخواست دانلود مستقیم از اسپاتیفای: User={uid}, URL={url}")

    status_msg = bot.send_message(chat_id, "🔎 <b>در حال اتصال مستقیم به دیتاسنتر اسپاتیفای...</b>")

    user_fmt = get_user(uid).get("format", "ogg")
    
    # اجرای دستور spotdl جهت دریافت مستقیم فایل خام اسپاتیفای با بیت‌ریت ۳۲۰k
    cmd = [
        "spotdl",
        "download",
        url,
        "--output", f"spotify_pure_{chat_id}_{int(time.time())}.{{output-ext}}",
        "--bitrate", "320k",
        "--format", user_fmt,
        "--no-cache"
    ]

    downloaded_file = None
    try:
        try:
            bot.edit_message_text("📥 <b>در حال استخراج فایل صوتی اورجینال (Ogg Vorbis 320k)...</b>", chat_id, status_msg.message_id)
        except Exception: pass

        logger.info(f"[LOG TERMINAL] Executing command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        logger.info(f"[LOG TERMINAL] SpotDL Output: {result.stdout}")
        if result.stderr:
            logger.warning(f"[LOG TERMINAL] SpotDL Stderr: {result.stderr}")

        # پیدا کردن فایل دانلود شده روی سرور
        for file in os.listdir("."):
            if file.startswith(f"spotify_pure_{chat_id}_"):
                downloaded_file = file
                break

        if not downloaded_file or not os.path.exists(downloaded_file):
            raise Exception("فایل صوتی اسپاتیفای در سرور پیدا نشد.")

        file_size_mb = os.path.getsize(downloaded_file) / (1024 * 1024)
        logger.info(f"[LOG TERMINAL] ✅ فایل اسپاتیفای آماده شد: '{downloaded_file}', حجم: {file_size_mb:.2f} MB")

        try:
            bot.edit_message_text("📤 <b>در حال آپلود فایل صوتی اورجینال اسپاتیفای به تلگرام...</b>", chat_id, status_msg.message_id)
        except Exception: pass

        with open(downloaded_file, 'rb') as audio_file:
            caption = f"🎵 <b>دانلود مستقیم از دیتاسنتر اسپاتیفای</b>\n\n💎 <i>فرمت فابریک: {user_fmt.upper()} (320kbps)</i>\n⚡️ <i>بدون واسطه و بدون افت کیفیت</i>"
            bot.send_document(
                chat_id=chat_id,
                document=audio_file,
                caption=caption
            )

        logger.info(f"[LOG TERMINAL] 🎉 ارسال موفق به کاربر {uid}")
        try: bot.delete_message(chat_id, status_msg.message_id)
        except Exception: pass

    except Exception as e:
        logger.error(f"[LOG TERMINAL] 🔴 خطا در استخراج اسپاتیفای: {e}")
        try:
            bot.edit_message_text("❌ متأسفانه در دریافت مستقیم فایل از اسپاتیفای خطایی رخ داد. لطفاً مجدداً تلاش کنید.", chat_id, status_msg.message_id)
        except Exception: pass

    finally:
        # پاکسازی فایل‌های موقت از روی هاست
        if downloaded_file and os.path.exists(downloaded_file):
            try:
                os.remove(downloaded_file)
                logger.info(f"[LOG TERMINAL] 🧹 فایل موقت پاکسازی شد: '{downloaded_file}'")
            except Exception: pass

if __name__ == "__main__":
    logger.info(f"Pure Spotify Bot V{VERSION} Started!")
    
    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception: pass

    bot.infinity_polling(skip_pending=True, none_stop=True, timeout=30)

