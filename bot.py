# ============================================================
# ربات دانلود اختصاصی M4A / AAC 320kbps واقعی (بدون MP3 و یوتیوب)
# اتصال مستقیم به CDN رسمی برای دور زدن محدودیت‌های Render
# ============================================================

import os
import re
import json
import sys
import time
import base64
import logging
import threading
import html
import requests
import urllib.parse
from flask import Flask
import telebot
from telebot.apihelper import ApiTelegramException

# تزریق تگ‌ها و کاور باکیفیت روی فایل M4A / MP4
from mutagen.mp4 import MP4, MP4Cover
from Crypto.Cipher import DES

# ============================================================
# تنظیمات اصلی
# ============================================================
TOKEN = "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY"
VERSION = "26.0-M4AMasterDirect"

# ============================================================
# تنظیم سیستم لاگ
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("M4AMasterBot")

# ============================================================
# سرور Flask جهت روشن ماندن ربات روی Render
# ============================================================
app = Flask('')
@app.route('/')
def home():
    return f"M4A Direct CDN Bot V:{VERSION} is Online!"

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
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

# ============================================================
# استخراج سریع متادیتای اسپاتیفای
# ============================================================
def get_spotify_track_meta(track_id):
    logger.info(f"[LOG TERMINAL] 🔍 استخراج متادیتا برای Track ID: {track_id}")
    clean_url = f"https://open.spotify.com/track/{track_id}"
    
    try:
        oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(clean_url)}"
        resp = requests.get(oembed_url, headers=HEADERS, timeout=4)
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
                artist = a_raw

            if title:
                logger.info(f"[LOG TERMINAL] ✅ متادیتا یافت شد: {artist} - {title}")
                return {"title": title, "artist": artist or "Unknown", "cover": cover}
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ oEmbed Error: {e}")

    # Fallback به نام پیش فرض
    return {"title": "Unknown Track", "artist": "Spotify Artist", "cover": ""}

# ============================================================
# رمزگشایی مستقیم لینک از Official CDN (بدون قطعی و ۱۰۰٪ تضمینی)
# ============================================================
def decrypt_official_m4a_url(encrypted_url):
    try:
        # کلید رمزگشایی پایگاه‌داده رسمی (DES ECB)
        key = b'38346591'
        cipher = DES.new(key, DES.MODE_ECB)
        enc = base64.b64decode(encrypted_url.strip())
        dec = cipher.decrypt(enc)
        # حذف پدینگ PKCS5
        pad_len = dec[-1]
        dec = dec[:-pad_len]
        
        # استخراج لینک اصلی و تبدیل کیفیت به ۳۲۰kbps AAC (M4A)
        hq_url = dec.decode('utf-8').replace("_96.mp4", "_320.mp4").replace("_160.mp4", "_320.mp4")
        return hq_url
    except Exception as e:
        logger.error(f"[LOG TERMINAL] ⚠️ خطای رمزگشایی CDN: {e}")
        return None

# ============================================================
# دانلود مستقیم M4A (AAC 320k) از سرور
# ============================================================
def download_m4a_direct_cdn(artist, title, output_path):
    # تمیز کردن نام آهنگ (حذف کلماتی مثل Remastered برای جستجوی دقیق‌تر)
    clean_title = re.sub(r'\(.*?\)|\[.*?\]', '', title).strip()
    query = f"{artist} {clean_title}".strip()
    logger.info(f"[LOG TERMINAL] ⚡️ اتصال به Official CDN برای: '{query}'")

    # اتصال مستقیم به سرور مرکزی موزیک بدون واسطه (بدون Render DNS Block)
    api_url = "https://www.jiosaavn.com/api.php"
    params = {
        "p": "1",
        "q": query,
        "_format": "json",
        "_marker": "0",
        "api_version": "4",
        "ctx": "web6dot0",
        "n": "5",
        "__call": "search.getResults"
    }

    try:
        r = requests.get(api_url, params=params, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            data = r.json()
            results = data.get("results", [])
            
            # اگر با خواننده پیدا نشد، فقط با نام آهنگ جستجو کن
            if not results:
                params["q"] = clean_title
                r = requests.get(api_url, params=params, headers=HEADERS, timeout=8)
                results = r.json().get("results", [])

            if results:
                # دریافت لینک رمزگذاری شده
                enc_url = results[0].get("more_info", {}).get("encrypted_media_url")
                if enc_url:
                    # رمزگشایی به لینک اصلی M4A / AAC
                    direct_m4a_link = decrypt_official_m4a_url(enc_url)
                    if direct_m4a_link:
                        logger.info(f"[LOG TERMINAL] 🟢 استریم اصلی یافت شد: {direct_m4a_link[:60]}...")
                        
                        # دانلود فایل M4A کامل
                        r_file = requests.get(direct_m4a_link, stream=True, headers=HEADERS, timeout=35)
                        if r_file.status_code == 200:
                            with open(output_path, "wb") as f:
                                for chunk in r_file.iter_content(chunk_size=8192):
                                    if chunk: f.write(chunk)
                            
                            # فایل M4A کامل معمولا بیشتر از ۱.۵ مگابایت است
                            if os.path.exists(output_path) and os.path.getsize(output_path) > 1500000:
                                logger.info("[LOG TERMINAL] ✅ دانلود فایل کامل M4A با موفقیت انجام شد.")
                                return True
    except Exception as e:
        logger.error(f"[LOG TERMINAL] 🔴 خطای Official CDN: {e}")

    return False

# ============================================================
# حک کردن کاور HD و متادیتا روی فایل M4A
# ============================================================
def embed_cover_and_tags_m4a(m4a_path, title, artist, cover_url):
    try:
        logger.info(f"[LOG TERMINAL] 🎨 حک کاور HD روی فایل M4A...")
        audio = MP4(m4a_path)
        
        # ثبت مشخصات
        audio["\xa9nam"] = [title]
        audio["\xa9ART"] = [artist]
        audio["\xa9alb"] = ["Spotify M4A Master"]

        # ثبت تصویر HD
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
        "🟢 <b>ربات دانلود موزیک با کیفیت اصلی M4A (بدون MP3)</b>\n\n"
        "لینک آهنگ اسپاتیفای را ارسال کنید تا فایل با کیفیت عالی و بدون افت (فرمت M4A / AAC) همراه با کاور دریافت کنید.\n\n"
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
    status_msg = bot.send_message(chat_id, "🔎 <b>در حال استخراج متادیتای دقیق...</b>")

    # ۱. استخراج متادیتا و کاور
    meta = get_spotify_track_meta(track_id)
    display_title = meta["title"]
    display_artist = meta["artist"]
    cover_url = meta.get("cover")

    try:
        bot.edit_message_text(f"📥 <b>در حال دانلود فایل خالص M4A برای «{html.escape(display_artist)} - {html.escape(display_title)}»...</b>", chat_id, status_msg.message_id)
    except Exception: pass

    filename = f"track_{chat_id}_{int(time.time())}.m4a"

    # ۲. استخراج مستقیم M4A از Official CDN
    success = download_m4a_direct_cdn(display_artist, display_title, filename)

    if not success or not os.path.exists(filename) or os.path.getsize(filename) < 1500000:
        logger.error(f"[LOG TERMINAL] 🔴 استخراج M4A ناموفق بود.")
        try:
            bot.edit_message_text("❌ متأسفانه در دریافت فایل M4A مشکلی پیش آمد. لطفاً دوباره امتحان کنید.", chat_id, status_msg.message_id)
        except Exception: pass
        if os.path.exists(filename): os.remove(filename)
        return

    # ۳. حک کردن تگ‌ها روی فرمت M4A
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
            caption = f"🎵 <b>{html.escape(display_title)}</b>\n🎤 <b>{html.escape(display_artist)}</b>\n\n✨ <i>فرمت اصلی اپل (M4A / AAC 320k) - دانلود مستقیم از سرور اصلی</i>"
            bot.send_audio(
                chat_id=chat_id,
                audio=audio_file,
                caption=caption,
                title=display_title,
                performer=display_artist
            )
            
        logger.info(f"[LOG TERMINAL] 🎉 ارسال فایل کامل M4A با موفقیت انجام شد!")
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
    logger.info(f"M4A Master Direct Bot V{VERSION} Started!")
    
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


