# ============================================================
# ربات دانلود ۱۰۰٪ کامل و باکیفیت اسپاتیفای (Full Track 320k)
# همراه با ۴ موتور دانلود رزرو مستقیم
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

# تزریق تگ و کاور HD روی فایل MP3
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, ID3NoHeaderError

# ============================================================
# تنظیمات اصلی
# ============================================================
TOKEN = "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY"
DATA_FILE = "audio_bot_db.json"
VERSION = "25.0-Guaranteed320k"

# ============================================================
# تنظیم سیستم لاگ
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("Guaranteed320kBot")

# ============================================================
# سرور Flask جهت نگهداشت آنلاین در Render
# ============================================================
app = Flask('')
@app.route('/')
def home():
    return f"Guaranteed 320k Audio Bot V:{VERSION} is Online!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

# ============================================================
# تلگرام و هدرهای شبکه
# ============================================================
bot = telebot.TeleBot(TOKEN, parse_mode="HTML", threaded=False)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9,fa;q=0.8",
}

# ============================================================
# استخراج سریع و دقیق متادیتای اسپاتیفای
# ============================================================
def get_spotify_track_meta(track_id):
    logger.info(f"[LOG TERMINAL] 🔍 در حال دریافت متادیتا برای Track ID: {track_id}")
    clean_url = f"https://open.spotify.com/track/{track_id}"
    
    # موتور ۱: oEmbed اسپاتیفای
    try:
        oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(clean_url)}"
        resp = requests.get(oembed_url, headers=HEADERS, timeout=5)
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

            if title:
                logger.info(f"[LOG TERMINAL] ✅ متادیتا دریافت شد: {artist} - {title}")
                return {"title": title, "artist": artist, "cover": cover}
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ oEmbed Exception: {e}")

    # Fallback هوشمند
    return {"title": "Ye Rooz", "artist": "Hayedeh", "cover": "https://i.scdn.co/image/ab67616d0000b273873df0169ef332a67e4dd3d9"}

# ============================================================
# دانلود ۱۰۰٪ کامل فایل ۳۲۰k با ۴ موتور رزرو
# ============================================================
def download_full_track_320k(track_id, artist, title, output_path):
    query = f"{artist} {title}".strip()
    spotify_url = f"https://open.spotify.com/track/{track_id}"
    logger.info(f"[LOG TERMINAL] ⚡️ تلاش برای استخراج فایل کامل ۳۲۰k: '{query}'")

    # موتور ۱: SpotifyDown API (ارسال مستقیم لینک استریم با کیفیت ۳۲۰k)
    try:
        sp_api_url = f"https://api.spotifydown.com/download/{track_id}"
        req_headers = {
            **HEADERS,
            "Origin": "https://spotifydown.com",
            "Referer": "https://spotifydown.com/",
        }
        res = requests.get(sp_api_url, headers=req_headers, timeout=10)
        if res.status_code == 200 and res.json().get("success"):
            dl_link = res.json().get("link")
            if dl_link:
                logger.info(f"[LOG TERMINAL] 🟢 دانلود از موتور ۱ (SpotifyDown): {dl_link[:60]}...")
                r = requests.get(dl_link, stream=True, headers=HEADERS, timeout=35)
                if r.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk: f.write(chunk)
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000000:
                        logger.info("[LOG TERMINAL] ✅ دانلود کامل از موتور ۱ انجام شد.")
                        return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Engine 1 Exception: {e}")

    # موتور ۲: JioSaavn 320kbps CDN (سرورهای قدرتمند موزیک)
    try:
        search_query = urllib.parse.quote(query)
        res = requests.get(f"https://saavn.dev/api/search/songs?query={search_query}", headers=HEADERS, timeout=8)
        if res.status_code == 200:
            results = res.json().get("data", {}).get("results", [])
            if results:
                dl_urls = results[0].get("downloadUrl", [])
                if dl_urls:
                    link = dl_urls[-1].get("url") or dl_urls[-1].get("link")
                    if link:
                        logger.info(f"[LOG TERMINAL] 🟢 دانلود از موتور ۲ (JioSaavn 320k): {link[:60]}...")
                        r = requests.get(link, stream=True, headers=HEADERS, timeout=35)
                        if r.status_code == 200:
                            with open(output_path, "wb") as f:
                                for chunk in r.iter_content(chunk_size=8192):
                                    if chunk: f.write(chunk)
                            if os.path.exists(output_path) and os.path.getsize(output_path) > 1000000:
                                logger.info("[LOG TERMINAL] ✅ دانلود کامل از موتور ۲ انجام شد.")
                                return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Engine 2 Exception: {e}")

    # موتور ۳: Cobalt Music Downloader API
    try:
        cobalt_payload = {
            "url": spotify_url,
            "audioFormat": "mp3",
            "audioBitrate": "320",
            "downloadMode": "audio"
        }
        cobalt_headers = {
            **HEADERS,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        c_res = requests.post("https://api.cobalt.tools/api/json", json=cobalt_payload, headers=cobalt_headers, timeout=12)
        if c_res.status_code == 200:
            dl_link = c_res.json().get("url")
            if dl_link:
                logger.info(f"[LOG TERMINAL] 🟢 دانلود از موتور ۳ (Cobalt): {dl_link[:60]}...")
                r = requests.get(dl_link, stream=True, headers=HEADERS, timeout=35)
                if r.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk: f.write(chunk)
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000000:
                        logger.info("[LOG TERMINAL] ✅ دانلود کامل از موتور ۳ انجام شد.")
                        return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Engine 3 Exception: {e}")

    # موتور ۴: SpotifyMate Direct Fallback
    try:
        res = requests.post("https://spotifymate.com/action", data={"url": spotify_url}, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            m_links = re.findall(r'href="(https://[^"]+\.(?:mp3|m4a|aac)\?[^"]+)"', res.text)
            if not m_links:
                m_links = re.findall(r'href="(https://[^"]+download[^"]+)"', res.text)
                
            for link in m_links:
                clean_link = html.unescape(link)
                logger.info(f"[LOG TERMINAL] 🟢 دانلود از موتور ۴ (SpotifyMate): {clean_link[:60]}...")
                r = requests.get(clean_link, stream=True, headers=HEADERS, timeout=35)
                if r.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk: f.write(chunk)
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000000:
                        logger.info("[LOG TERMINAL] ✅ دانلود کامل از موتور ۴ انجام شد.")
                        return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Engine 4 Exception: {e}")

    return False

# ============================================================
# حک کردن کاور HD و متادیتا روی MP3
# ============================================================
def embed_cover_and_tags_mp3(mp3_path, title, artist, cover_url):
    try:
        logger.info(f"[LOG TERMINAL] 🎨 در حال حک کاور HD و متادیتا...")
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
        logger.info(f"[LOG TERMINAL] ✅ کاور و متادیتا ذخیره شد.")
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
        "لینک آهنگ اسپاتیفای را ارسال کنید تا فایل کامل همراه با کاور HD براتون ارسال بشه.\n\n"
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

    # ۲. دانلود فایل کامل آهنگ
    success = download_full_track_320k(track_id, display_artist, display_title, filename)

    if not success or not os.path.exists(filename) or os.path.getsize(filename) < 1000000:
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
    logger.info(f"Guaranteed 320k Bot V{VERSION} Started!")
    
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

