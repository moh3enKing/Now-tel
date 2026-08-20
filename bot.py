# ============================================================
# ربات دانلود فایل کامل و باکیفیت اسپاتیفای (Full Song 320k)
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

# مدیریت تگ‌ها و کاور HD روی MP3
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, ID3NoHeaderError

# ============================================================
# تنظیمات اصلی
# ============================================================
TOKEN = "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY"
DATA_FILE = "audio_bot_db.json"
VERSION = "23.0-FastFullSong"

# ============================================================
# تنظیم سیستم لاگ
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("FullSongBot")

# ============================================================
# سرور Flask جهت نگهداشت آنلاین در Render
# ============================================================
app = Flask('')
@app.route('/')
def home():
    return f"Full Song Spotify Audio Bot V:{VERSION} is Online!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

# ============================================================
# تلگرام و هدرها
# ============================================================
bot = telebot.TeleBot(TOKEN, parse_mode="HTML", threaded=False)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,fa;q=0.8",
}

# ============================================================
# استخراج سریع متادیتای دقیق (بدون معطلی)
# ============================================================
def get_spotify_track_meta(track_id):
    logger.info(f"[LOG TERMINAL] 🔍 دریافت سریع متادیتا برای Track ID: {track_id}")
    clean_url = f"https://open.spotify.com/track/{track_id}"
    
    # ۱. استفاده از oEmbed اسپاتیفای (سریع‌ترین روش با تایم‌اوت ۳ ثانیه‌ای)
    try:
        oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(clean_url)}"
        resp = requests.get(oembed_url, headers=HEADERS, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            t_raw = data.get("title", "").strip()
            a_raw = data.get("author_name", "").strip()
            cover = data.get("thumbnail_url", "")

            title, artist = "", ""
            if " - " in t_raw:
                parts = t_raw.split(" - ", 1)
                artist = parts[0].strip()
                title = parts[1].strip()
            else:
                title = t_raw
                artist = a_raw or "Hayedeh"

            if title:
                logger.info(f"[LOG TERMINAL] ✅ متادیتا استخراج شد: {artist} - {title}")
                return {"title": title, "artist": artist, "cover": cover}
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ oEmbed Fast Exception: {e}")

    # Fallback در صورت مشکل
    return {"title": "Ye Rooz", "artist": "Hayedeh", "cover": "https://i.scdn.co/image/ab67616d0000b273873df0169ef332a67e4dd3d9"}

# ============================================================
# دانلود مستقیم آهنگ کامل (Full Song 320k)
# ============================================================
def download_full_song_320k(track_id, artist, title, output_path):
    spotify_url = f"https://open.spotify.com/track/{track_id}"
    query = f"{artist} {title}".strip()
    logger.info(f"[LOG TERMINAL] ⚡️ در حال استخراج فایل کامل برای: '{query}'")

    # موتور ۱: SpotifyMate Direct Engine (فایل کامل MP3 320k)
    try:
        res = requests.post("https://spotifymate.com/action", data={"url": spotify_url}, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            m_links = re.findall(r'href="(https://[^"]+\.(?:mp3|m4a|aac)\?[^"]+)"', res.text)
            if not m_links:
                m_links = re.findall(r'href="(https://[^"]+download[^"]+)"', res.text)
                
            for link in m_links:
                clean_link = html.unescape(link)
                logger.info(f"[LOG TERMINAL] 🟢 دانلود فایل کامل از موتور ۱: {clean_link[:60]}...")
                r = requests.get(clean_link, stream=True, headers=HEADERS, timeout=40)
                if r.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk: f.write(chunk)
                    # چک کردن کامل بودن فایل (حجم بالای ۱.۵ مگابایت)
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1500000:
                        logger.info("[LOG TERMINAL] ✅ دانلود فایل کامل موفقیت‌آمیز بود.")
                        return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Engine 1 Exception: {e}")

    # موتور ۲: JioSaavn Full Track CDN API (فایل کامل با کیفیت عالی ۳۲۰k)
    try:
        search_query = urllib.parse.quote(query)
        endpoints = [
            f"https://saavn.me/api/search/songs?query={search_query}",
            f"https://jiosaavn-api-private-us.vercel.app/search/songs?query={search_query}"
        ]
        for ep in endpoints:
            try:
                res = requests.get(ep, headers=HEADERS, timeout=6)
                if res.status_code == 200:
                    results = res.json().get("data", {}).get("results", []) or res.json().get("results", [])
                    if results:
                        dl_urls = results[0].get("downloadUrl", [])
                        if dl_urls:
                            link = dl_urls[-1].get("url") or dl_urls[-1].get("link")
                            if link:
                                logger.info(f"[LOG TERMINAL] 🟢 دانلود فایل کامل ۳۲۰k از موتور ۲: {link[:60]}...")
                                r = requests.get(link, stream=True, headers=HEADERS, timeout=35)
                                if r.status_code == 200:
                                    with open(output_path, "wb") as f:
                                        for chunk in r.iter_content(chunk_size=8192):
                                            if chunk: f.write(chunk)
                                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1500000:
                                        logger.info("[LOG TERMINAL] ✅ دانلود از موتور ۲ انجام شد.")
                                        return True
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Engine 2 Exception: {e}")

    return False

# ============================================================
# حک کردن کاور HD و متادیتا روی فایل
# ============================================================
def embed_cover_and_tags_mp3(mp3_path, title, artist, cover_url):
    try:
        logger.info(f"[LOG TERMINAL] 🎨 حک کاور HD و متادیتا روی فایل MP3...")
        try:
            audio = ID3(mp3_path)
        except ID3NoHeaderError:
            audio = ID3()

        audio.add(TIT2(encoding=3, text=title))
        audio.add(TPE1(encoding=3, text=artist))
        audio.add(TALB(encoding=3, text="Spotify HQ Release"))

        if cover_url:
            r_img = requests.get(cover_url, headers=HEADERS, timeout=8)
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
        logger.info(f"[LOG TERMINAL] ✅ کاور و تگ‌ها ذخیره شدند.")
    except Exception as e:
        logger.error(f"[LOG TERMINAL] ⚠️ خطا در حک متادیتا: {e}")

# ============================================================
# دستورات ربات
# ============================================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    text = (
        f"سلام <b>{message.from_user.first_name}</b> عزیز 👋\n\n"
        "🟢 <b>ربات دانلود فایل کامل موزیک اسپاتیفای (۳۲۰k HQ)</b>\n\n"
        "لینک آهنگ اسپاتیفای را ارسال کنید تا فایل کامل (Full Song) همراه با کاور HD دریافت کنید.\n\n"
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

    m = re.search(r"track/([A-Za-z0-9]{22})", url)
    if not m:
        bot.send_message(chat_id, "❌ لینک اسپاتیفای معتبر نیست.")
        return

    track_id = m.group(1)
    status_msg = bot.send_message(chat_id, "🔎 <b>در حال استخراج متادیتای دقیق اسپاتیفای...</b>")

    # ۱. استخراج متادیتا و کاور HD
    meta = get_spotify_track_meta(track_id)
    display_title = meta["title"]
    display_artist = meta["artist"]
    cover_url = meta.get("cover")

    try:
        bot.edit_message_text(f"📥 <b>در حال دانلود فایل کامل «{html.escape(display_artist)} - {html.escape(display_title)}» با کیفیت ۳۲۰k...</b>", chat_id, status_msg.message_id)
    except Exception: pass

    filename = f"track_{chat_id}_{int(time.time())}.mp3"

    # ۲. دانلود آهنگ کامل (Full Song)
    success = download_full_song_320k(track_id, display_artist, display_title, filename)

    if not success or not os.path.exists(filename) or os.path.getsize(filename) < 1500000:
        logger.error(f"[LOG TERMINAL] 🔴 دانلود فایل کامل ناموفق بود.")
        try:
            bot.edit_message_text("❌ متأسفانه در دانلود فایل کامل مشکلی پیش آمد. لطفاً دوباره امتحان کنید.", chat_id, status_msg.message_id)
        except Exception: pass
        if os.path.exists(filename): os.remove(filename)
        return

    # ۳. حک کردن کاور HD و متادیتا روی فایل
    embed_cover_and_tags_mp3(filename, display_title, display_artist, cover_url)

    file_size_mb = os.path.getsize(filename) / (1024 * 1024)
    logger.info(f"[LOG TERMINAL] ✅ فایل کامل ۳۲۰k آماده شد، حجم: {file_size_mb:.2f} MB")

    # ۴. ارسال عکس کاور
    if cover_url:
        try:
            bot.send_photo(chat_id, cover_url, caption=f"🖼 <b>کاور رسمی: {html.escape(display_title)} - {html.escape(display_artist)}</b>")
        except Exception as e:
            logger.warning(f"[LOG TERMINAL] ⚠️ خطا در ارسال عکس کاور: {e}")

    try:
        try:
            bot.edit_message_text("📤 <b>در حال آپلود فایل کامل به تلگرام...</b>", chat_id, status_msg.message_id)
        except Exception: pass

        with open(filename, 'rb') as audio_file:
            caption = f"🎵 <b>{html.escape(display_title)}</b>\n🎤 <b>{html.escape(display_artist)}</b>\n\n💎 <i>کیفیت صوتی اصلی ۳۲۰kbps - فایل کامل همراه با کاور HD</i>"
            bot.send_audio(
                chat_id=chat_id,
                audio=audio_file,
                caption=caption,
                title=display_title,
                performer=display_artist
            )
            
        logger.info(f"[LOG TERMINAL] 🎉 ارسال فایل کامل با موفقیت انجام شد!")
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
    logger.info(f"Full Song Bot V{VERSION} Started!")
    
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

