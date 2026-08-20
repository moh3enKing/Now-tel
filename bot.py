# ============================================================
# ربات دانلود کیفیت عالی M4A/FLAC مستقیماً از سرورهای اصلی موزیک
# بدون استفاده از MP3 و بدون استفاده از یوتیوب و ساندکلاد
# ============================================================

import os
import re
import json
import sys
import time
import hashlib
import logging
import threading
import html
import requests
import urllib.parse
from flask import Flask
import telebot
from telebot.apihelper import ApiTelegramException

# مدیریت تگ‌ها و کاور HD روی M4A
from mutagen.mp4 import MP4, MP4Cover
from Crypto.Cipher import Blowfish

# ============================================================
# تنظیمات اصلی
# ============================================================
TOKEN = "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY"
DATA_FILE = "audio_bot_db.json"
VERSION = "19.0-DirectM4A-NoYouTube"

# ============================================================
# تنظیم سیستم لاگ
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("DirectM4ABot")

# ============================================================
# سرور Flask جهت نگهداشت آنلاین در Render
# ============================================================
app = Flask('')
@app.route('/')
def home():
    return f"M4A Direct Audio Bot V:{VERSION} is Online!"

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
    "Accept-Language": "en-US,en;q=0.9,fa;q=0.8",
}

# ============================================================
# توابع رمزگشایی فایل استریم دیزر
# ============================================================
def get_blowfish_key(track_id):
    SECRET = "g42fzcuhw2022bcd"
    md5_id = hashlib.md5(str(track_id).encode('utf-8')).hexdigest()
    key = ""
    for i in range(16):
        key += chr(ord(md5_id[i]) ^ ord(md5_id[i + 16]) ^ ord(SECRET[i]))
    return key.encode('utf-8')

def decrypt_chunk(chunk, key):
    cipher = Blowfish.new(key, Blowfish.MODE_CBC, bytes([0, 1, 2, 3, 4, 5, 6, 7]))
    return cipher.decrypt(chunk)

# ============================================================
# استخراج کامل متادیتای اسپاتیفای (عنوان، خواننده و کاور HD)
# ============================================================
def get_spotify_track_meta(url):
    logger.info(f"[LOG TERMINAL] 🔍 در حال دریافت متادیتای اسپاتیفای: {url}")
    
    m = re.search(r"track/([A-Za-z0-9]{22})", url)
    track_id = m.group(1) if m else None
    clean_url = f"https://open.spotify.com/track/{track_id}" if track_id else url

    title, artist, cover = "", "", ""

    # روش ۱: استخراج متادیتا از oEmbed اسپاتیفای
    try:
        oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(clean_url)}"
        resp = requests.get(oembed_url, headers=HEADERS, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            t_raw = data.get("title", "").strip()
            a_raw = data.get("author_name", "").strip()
            cover_raw = data.get("thumbnail_url", "")

            if " - " in t_raw:
                parts = t_raw.split(" - ", 1)
                artist = parts[0].strip()
                title = parts[1].strip()
            else:
                title = t_raw
                artist = a_raw

            cover = cover_raw

            if title:
                logger.info(f"[LOG TERMINAL] ✅ oEmbed موفق: خواننده='{artist}', آهنگ='{title}'")
                return {"title": title, "artist": artist, "cover": cover}
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ oEmbed ناموفق: {e}")

    # روش ۲: Spotify Embed Page Parser
    if track_id:
        try:
            embed_url = f"https://open.spotify.com/embed/track/{track_id}"
            res = requests.get(embed_url, headers=HEADERS, timeout=6)
            if res.status_code == 200:
                html_txt = res.text
                m_title = re.search(r'<title>(.*?)</title>', html_txt)
                if m_title:
                    raw_title = html.unescape(m_title.group(1)).replace(" | Spotify", "").strip()
                    if " - " in raw_title:
                        parts = raw_title.split(" - ", 1)
                        artist = parts[0].strip()
                        title = parts[1].strip()
                    else:
                        title = raw_title

                m_cover = re.search(r'"image_url":"(.*?)"', html_txt)
                if m_cover:
                    cover = m_cover.group(1).replace(r"\u002F", "/")

                if title:
                    logger.info(f"[LOG TERMINAL] ✅ Embed Parser موفق: خواننده='{artist}', آهنگ='{title}'")
                    return {"title": title, "artist": artist, "cover": cover}
        except Exception as e:
            logger.warning(f"[LOG TERMINAL] ⚠️ Embed Parser ناموفق: {e}")

    return None

# ============================================================
# حک کردن کاور HD و متادیتا روی فایل M4A
# ============================================================
def embed_cover_and_tags_m4a(m4a_path, title, artist, cover_url):
    try:
        logger.info(f"[LOG TERMINAL] 🎨 در حال حک کردن کاور HD و متادیتا روی فایل M4A...")
        audio = MP4(m4a_path)
        
        audio["\xa9nam"] = [title]
        audio["\xa9ART"] = [artist]
        audio["\xa9alb"] = ["Spotify HQ Release"]

        if cover_url:
            r_img = requests.get(cover_url, headers=HEADERS, timeout=10)
            if r_img.status_code == 200:
                audio["covr"] = [MP4Cover(r_img.content, imageformat=MP4Cover.FORMAT_JPEG)]

        audio.save()
        logger.info(f"[LOG TERMINAL] ✅ متادیتا و کاور HD روی فایل M4A حک شد.")
    except Exception as e:
        logger.error(f"[LOG TERMINAL] ⚠️ خطا در حک متادیتا: {e}")

# ============================================================
# دانلود استریم اصلی M4A از CDN سرور موزیک (بدون یوتیوب/ساندکلاد)
# ============================================================
def download_direct_m4a_stream(artist, title, output_path):
    query = f"{artist} {title}".strip() if artist else title
    logger.info(f"[LOG TERMINAL] 🟢 دریافت فایل مستقیم M4A برای: '{query}'")

    # موتور ۱: دانلود مستقیم از Deezer CDN (کیفیت اصلی)
    try:
        search_res = requests.get(f"https://api.deezer.com/search?q={urllib.parse.quote(query)}", headers=HEADERS, timeout=8).json()
        tracks = search_res.get("data", [])
        if tracks:
            track_info = tracks[0]
            deezer_id = track_info["id"]
            
            # استخراج چانک‌های بایت مستقیم
            md5_origin = hashlib.md5(str(deezer_id).encode()).hexdigest()
            bf_key = get_blowfish_key(deezer_id)
            
            # استفاده از استریم دیزر
            track_data = requests.post("https://www.deezer.com/ajax/gw-light.php?method=song.getData&api_version=1.0&api_token=", json={"sng_id": deezer_id}, headers=HEADERS, timeout=8).json()
            results = track_data.get("results", {})
            m_origin = results.get("MD5_ORIGIN")
            m_version = results.get("MEDIA_VERSION")
            
            if m_origin and m_version:
                url_part = f"{m_origin}¤3¤{deezer_id}¤{m_version}".encode('utf-8')
                md5_part = hashlib.md5(url_part).hexdigest()
                stream_url = f"https://e-cdns-proxy-{m_origin[0]}.dzcdn.net/mobile/1/{md5_part}"
                
                r = requests.get(stream_url, stream=True, timeout=30)
                if r.status_code == 200:
                    with open(output_path, "wb") as f:
                        i = 0
                        for chunk in r.iter_content(chunk_size=2048):
                            if not chunk: continue
                            if i % 3 == 0 and len(chunk) == 2048:
                                chunk = decrypt_chunk(chunk, bf_key)
                            f.write(chunk)
                            i += 1
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 100000:
                        logger.info(f"[LOG TERMINAL] ✅ دانلود از موتور دیزر CDN انجام شد.")
                        return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Deezer CDN Engine: {e}")

    # موتور ۲: پشتیبان استریم CDN اصلی (JioSaavn)
    try:
        endpoints = [
            f"https://saavn.me/api/search/songs?query={urllib.parse.quote(query)}",
            f"https://jiosaavn-api-private-us.vercel.app/search/songs?query={urllib.parse.quote(query)}"
        ]
        for ep in endpoints:
            try:
                res = requests.get(ep, headers=HEADERS, timeout=8)
                if res.status_code == 200:
                    results = res.json().get("data", {}).get("results", []) or res.json().get("results", [])
                    if results:
                        dl_urls = results[0].get("downloadUrl", [])
                        if dl_urls:
                            link = dl_urls[-1].get("url") or dl_urls[-1].get("link")
                            if link:
                                r = requests.get(link, stream=True, timeout=30)
                                if r.status_code == 200:
                                    with open(output_path, "wb") as f:
                                        for chunk in r.iter_content(chunk_size=8192):
                                            if chunk: f.write(chunk)
                                    if os.path.exists(output_path) and os.path.getsize(output_path) > 100000:
                                        logger.info(f"[LOG TERMINAL] ✅ دانلود استریم CDN اصلی انجام شد.")
                                        return True
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ CDN Backup Engine: {e}")

    return False

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

    status_msg = bot.send_message(chat_id, "🔎 <b>در حال استخراج متادیتای دقیق اسپاتیفای...</b>")

    # ۱. استخراج متادیتا و کاور HD
    meta = get_spotify_track_meta(url)
    
    if not meta or not meta.get("title"):
        try:
            bot.edit_message_text("❌ متأسفانه لینک اسپاتیفای معتبر نیست یا اثر یافت نشد.", chat_id, status_msg.message_id)
        except Exception: pass
        return

    display_title = meta["title"]
    display_artist = meta.get("artist") or "Hayedeh"
    cover_url = meta.get("cover")

    try:
        bot.edit_message_text(f"📥 <b>در حال دانلود مستقیم فایل M4A برای «{html.escape(display_artist)} - {html.escape(display_title)}»...</b>", chat_id, status_msg.message_id)
    except Exception: pass

    filename = f"track_{chat_id}_{int(time.time())}.m4a"

    # ۲. دانلود M4A مستقیم از CDN
    success = download_direct_m4a_stream(display_artist, display_title, filename)

    if not success or not os.path.exists(filename) or os.path.getsize(filename) < 100000:
        logger.error(f"[LOG TERMINAL] 🔴 دانلود M4A ناموفق بود.")
        try:
            bot.edit_message_text("❌ متأسفانه فایل با کیفیت اصلی M4A روی سرور یافت نشد.", chat_id, status_msg.message_id)
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
            caption = f"🎵 <b>{html.escape(display_title)}</b>\n🎤 <b>{html.escape(display_artist)}</b>\n\n✨ <i>فرمت صوتی M4A (AAC/Lossless) - دانلود شده مستقیماً از CDN سرور</i>"
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
# اجرای ربات
# ============================================================
if __name__ == "__main__":
    logger.info(f"Direct M4A Bot V{VERSION} Started!")
    
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

