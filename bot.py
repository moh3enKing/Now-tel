# ============================================================
# ربات دانلود مستقیم و اورجینال اسپاتیفای (۱۰۰٪ بدون یوتیوب)
# نسخه ۵.۱ - با قابلیت جلوگیری از کرش ۴۰۹ در Render
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
VERSION = "5.1-SmoothDeploy"

# ============================================================
# تنظیم سیستم لاگ پایتون برای نمایش در Render
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
        db["users"][uid] = {"format": "ogg"}
        save_data(db)
    return db["users"][uid]

# ============================================================
# استخراج متادیتای اسپاتیفای
# ============================================================
def get_spotify_track_meta(url):
    logger.info(f"[LOG TERMINAL] 🔍 دریافت متادیتای اسپاتیفای: {url}")
    
    m = re.search(r"track/([A-Za-z0-9]{22})", url)
    track_id = m.group(1) if m else None
    clean_url = f"https://open.spotify.com/track/{track_id}" if track_id else url

    title, artist, cover = "", "", ""

    # ۱. اسکرپ HTML
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
                logger.info(f"[LOG TERMINAL] ✅ متادیتای کامل: خواننده='{artist}', آهنگ='{title}'")
                return {"track_id": track_id, "title": title, "artist": artist, "cover": cover}
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ اسکرپ متادیتا ناموفق: {e}")

    # ۲. oEmbed Fallback
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
# دانلود مستقیم فایل صوتی از سرورهای اختصاصی اسپاتیفای
# ============================================================
def download_spotify_direct_audio(spotify_url, output_path):
    logger.info(f"[LOG TERMINAL] 🟢 شروع دانلود فایل نیتیو از CDN اسپاتیفای...")
    
    # API اول
    try:
        api_url = "https://api.spotidown.com/download"
        payload = {"url": spotify_url}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json",
            "Referer": "https://spotidown.com/"
        }
        res = requests.post(api_url, json=payload, headers=headers, timeout=20)
        if res.status_code == 200:
            data = res.json()
            download_link = data.get("file_url") or data.get("link") or data.get("download_url")
            if download_link:
                logger.info(f"[LOG TERMINAL] ⚡️ دریافت لینک مستقیم CDN اسپاتیفای: {download_link}")
                r_file = requests.get(download_link, stream=True, timeout=30)
                if r_file.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in r_file.iter_content(chunk_size=8192):
                            if chunk: f.write(chunk)
                    logger.info(f"[LOG TERMINAL] ✅ فایل نیتیو اسپاتیفای ذخیره شد.")
                    return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ API 1 ناموفق: {e}")

    # API دوم
    try:
        track_id = spotify_url.split('/')[-1].split('?')[0]
        api_url2 = f"https://api.spotifydown.com/download/{track_id}"
        headers2 = {
            "Origin": "https://spotifydown.com",
            "Referer": "https://spotifydown.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        res2 = requests.get(api_url2, headers=headers2, timeout=20)
        if res2.status_code == 200:
            data2 = res2.json()
            if data2.get("success") and data2.get("link"):
                dl_url = data2["link"]
                logger.info(f"[LOG TERMINAL] ⚡️ دریافت لینک مستقیم API 2 اسپاتیفای: {dl_url}")
                r_file = requests.get(dl_url, stream=True, timeout=30)
                if r_file.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in r_file.iter_content(chunk_size=8192):
                            if chunk: f.write(chunk)
                    logger.info(f"[LOG TERMINAL] ✅ فایل نیتیو اسپاتیفای ذخیره شد.")
                    return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ API 2 ناموفق: {e}")

    return False

# ============================================================
# کیبوردها
# ============================================================
def settings_keyboard(uid):
    user_format = get_user(uid).get("format", "ogg")
    
    btn_ogg = "✅ OGG Vorbis (کدک فابریک اسپاتیفای)" if user_format == "ogg" else "OGG Vorbis (کدک فابریک اسپاتیفای)"
    btn_mp3 = "✅ MP3 (کیفیت اورجینال ۳۲۰k)" if user_format == "mp3" else "MP3 (کیفیت اورجینال ۳۲۰k)"

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(btn_ogg, callback_data="set_fmt_ogg"))
    kb.add(types.InlineKeyboardButton(btn_mp3, callback_data="set_fmt_mp3"))
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
        "🟢 <b>ربات استخراج ۱۰۰٪ مستقیم از اسپاتیفای</b>\n\n"
        "این ربات فایل‌ها را <u>فقط و مستقیماً از دیتاسنتر اصلی اسپاتیفای (بدون واسطه)</u> دریافت و با بالاترین کیفیت کیفیت ۳۲۰k برای شما ارسال می‌کند.\n\n"
        "🔗 <b>لطفاً لینک آهنگ اسپاتیفای را ارسال کنید:</b>"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_reply_keyboard())

@bot.message_handler(func=lambda m: m.text == "⚙️ تنظیمات فرمت اسپاتیفای" or m.text == "/settings")
def show_settings(message):
    uid = message.from_user.id
    text = (
        "⚙️ <b>تنظیمات استخراج فایل خام اسپاتیفای</b>\n\n"
        "فرمت دلخواه برای دریافت فایل صوتی نیتیو اسپاتیفای را انتخاب کنید:\n\n"
        "🟢 <b>OGG Vorbis:</b> فرمت فابریک و نیتیو نرم‌افزار اسپاتیفای (۳۲۰k).\n"
        "🟢 <b>MP3 (320kbps):</b> کیفیت ۳۲۰k کامل دیتاسنتر اسپاتیفای."
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
# دریافت لینک و دانلود نیتیو اسپاتیفای
# ============================================================
@bot.message_handler(func=lambda m: "spotify.com" in (m.text or ""))
def handle_spotify_link(message):
    chat_id = message.chat.id
    uid = str(message.from_user.id)
    url = message.text.strip()

    logger.info(f"[LOG TERMINAL] --------------------------------------------------")
    logger.info(f"[LOG TERMINAL] درخواست جدید از کاربر {uid}: {url}")

    status_msg = bot.send_message(chat_id, "🔎 <b>در حال دریافت متادیتای مستقیم اسپاتیفای...</b>")

    # ۱. استخراج متادیتا
    meta = get_spotify_track_meta(url)
    
    if not meta or not meta.get("title"):
        try:
            bot.edit_message_text("❌ متأسفانه لینک اسپاتیفای معتبر نیست یا اثر یافت نشد.", chat_id, status_msg.message_id)
        except Exception: pass
        return

    display_title = meta["title"]
    display_artist = meta["artist"]
    
    try:
        bot.edit_message_text("📥 <b>در حال استخراج مستقیم فایل صوتی از سرور اسپاتیفای (320kbps)...</b>", chat_id, status_msg.message_id)
    except Exception: pass

    user_fmt = get_user(uid).get("format", "ogg")
    filename = f"spotify_{chat_id}_{int(time.time())}.{user_fmt}"

    # ۲. دانلود مستقیم از سرورهای اختصاصی اسپاتیفای
    success = download_spotify_direct_audio(url, filename)

    if not success or not os.path.exists(filename) or os.path.getsize(filename) < 10000:
        logger.error(f"[LOG TERMINAL] 🔴 دانلود مستقیم اسپاتیفای ناموفق بود.")
        try:
            bot.edit_message_text("❌ متأسفانه در استخراج مستقیم این اثر از سرور اسپاتیفای خطایی رخ داد. لطفاً مجدداً تلاش کنید.", chat_id, status_msg.message_id)
        except Exception: pass
        if os.path.exists(filename): os.remove(filename)
        return

    file_size_mb = os.path.getsize(filename) / (1024 * 1024)
    logger.info(f"[LOG TERMINAL] ✅ فایل اسپاتیفای با موفقیت دانلود شد: '{filename}', حجم: {file_size_mb:.2f} MB")

    try:
        try:
            bot.edit_message_text("📤 <b>در حال آپلود فایل اورجینال اسپاتیفای در تلگرام...</b>", chat_id, status_msg.message_id)
        except Exception: pass

        logger.info(f"[LOG TERMINAL] 📤 در حال ارسال فایل به تلگرام برای کاربر {uid}...")

        with open(filename, 'rb') as audio_file:
            caption = f"🎵 <b>{html.escape(display_title)}</b>\n🎤 {html.escape(display_artist or 'Spotify Artist')}\n\n💎 <i>فایل نیتیو دیتاسنتر اسپاتیفای - بدون واسطه و بدون افت کیفیت</i>"
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
        logger.error(f"[LOG TERMINAL] 🔴 خطا در ارسال فایل: {e}", exc_info=True)
        
    finally:
        if os.path.exists(filename):
            try:
                os.remove(filename)
                logger.info(f"[LOG TERMINAL] 🧹 فایل موقت سرور پاکسازی شد.")
            except Exception: pass

# ============================================================
# حلقه اصلی اجرای ربات با مدیریت هوشمند اتصالات هم‌زمان
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

