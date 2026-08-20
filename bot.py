# ============================================================
# ربات دانلود کامل موزیک (Full Track 320k / Full Length)
# بدون استریم‌های ۳۰ ثانیه‌ای پیش‌نمایش و بدون یوتیوب
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

# تزریق کاور و متادیتا هوشمند برای MP3 و M4A
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, ID3NoHeaderError
from mutagen.mp4 import MP4, MP4Cover

# ============================================================
# تنظیمات اصلی
# ============================================================
TOKEN = "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY"
DATA_FILE = "audio_bot_db.json"
VERSION = "22.0-FullTrackHQ"

# ============================================================
# تنظیم سیستم لاگ
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("FullTrackBot")

# ============================================================
# سرور Flask جهت نگهداشت آنلاین در Render
# ============================================================
app = Flask('')
@app.route('/')
def home():
    return f"Full Track HQ Audio Bot V:{VERSION} is Online!"

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
    "Accept-Language": "en-US,en;q=0.9,fa;q=0.8",
}

# ============================================================
# استخراج کامل متادیتای دقیق اسپاتیفای
# ============================================================
def get_spotify_track_meta(track_id):
    logger.info(f"[LOG TERMINAL] 🔍 استخراج متادیتا برای Track ID: {track_id}")
    
    title, artist, cover = "", "", ""

    try:
        embed_url = f"https://open.spotify.com/embed/track/{track_id}"
        res = requests.get(embed_url, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            html_txt = res.text
            
            m_json = re.search(r'<script id="session" type="application/json">(.*?)</script>', html_txt)
            if m_json:
                try:
                    data = json.loads(m_json.group(1))
                    entity = data.get("data", {}).get("entity", {})
                    if entity:
                        title = entity.get("name", "")
                        artists = [a.get("name") for a in entity.get("artists", []) if a.get("name")]
                        artist = ", ".join(artists)
                        images = entity.get("album", {}).get("images", [])
                        if images:
                            cover = images[0].get("url", "")
                except Exception: pass

            if not title or not artist:
                m_title = re.search(r'<title>(.*?)</title>', html_txt)
                if m_title:
                    raw_title = html.unescape(m_title.group(1)).replace(" | Spotify", "").strip()
                    if " - " in raw_title:
                        parts = raw_title.split(" - ", 1)
                        artist = artist or parts[0].strip()
                        title = parts[1].strip()
                    else:
                        title = raw_title

            m_cover = re.search(r'"image_url":"(.*?)"', html_txt)
            if m_cover and not cover:
                cover = m_cover.group(1).replace(r"\u002F", "/")

            if title:
                artist = artist or "Hayedeh"
                logger.info(f"[LOG TERMINAL] ✅ متادیتا یافت شد: {artist} - {title}")
                return {"title": title, "artist": artist, "cover": cover}
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Embed Meta Exception: {e}")

    return None

# ============================================================
# دانلود کامل فایل صوتی (Full Length) از سرورهای اصلی CDN
# ============================================================
def download_full_track(track_id, artist, title, output_path):
    query = f"{artist} {title}".strip()
    spotify_url = f"https://open.spotify.com/track/{track_id}"
    logger.info(f"[LOG TERMINAL] ⚡️ دریافت فایل کامل برای: '{query}'")

    # موتور ۱: JioSaavn CDN (دانلود کامل ۳۲۰kbps بدون محدودیت زمان)
    try:
        search_query = urllib.parse.quote(query)
        endpoints = [
            f"https://saavn.me/api/search/songs?query={search_query}",
            f"https://jiosaavn-api-private-us.vercel.app/search/songs?query={search_query}"
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
                                logger.info(f"[LOG TERMINAL] 🟢 دریافت لینک کامل ۳۲۰k از موتور ۱: {link[:60]}...")
                                r = requests.get(link, stream=True, headers=HEADERS, timeout=35)
                                if r.status_code == 200:
                                    with open(output_path, "wb") as f:
                                        for chunk in r.iter_content(chunk_size=8192):
                                            if chunk: f.write(chunk)
                                    # بررسی حجم فایل (فایل کامل باید بیشتر از ۱.۵ مگابایت باشد)
                                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1500000:
                                        logger.info("[LOG TERMINAL] ✅ دانلود فایل کامل انجام شد.")
                                        return True
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Full Track Engine 1: {e}")

    # موتور ۲: FabDL Full Spotify Converter
    try:
        req_url = f"https://api.fabdl.com/spotify/get?url={urllib.parse.quote(spotify_url)}"
        r_get = requests.get(req_url, headers=HEADERS, timeout=10)
        if r_get.status_code == 200 and r_get.json().get("result"):
            res_data = r_get.json()["result"]
            gid = res_data.get("gid")
            id_val = res_data.get("id")
            if gid and id_val:
                convert_url = f"https://api.fabdl.com/spotify/mp3-convert-task/{gid}/{id_val}"
                c_res = requests.get(convert_url, headers=HEADERS, timeout=15).json()
                dl_url = c_res.get("result", {}).get("download_url")
                if dl_url:
                    full_dl = f"https://api.fabdl.com{dl_url}"
                    logger.info(f"[LOG TERMINAL] 🟢 دانلود فایل کامل از موتور ۲: {full_dl[:60]}...")
                    r = requests.get(full_dl, stream=True, headers=HEADERS, timeout=40)
                    if r.status_code == 200:
                        with open(output_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if chunk: f.write(chunk)
                        if os.path.exists(output_path) and os.path.getsize(output_path) > 1500000:
                            logger.info("[LOG TERMINAL] ✅ دانلود کامل با موفقیت انجام شد.")
                            return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Full Track Engine 2: {e}")

    # موتور ۳: SpotifyMate Direct Full Engine
    try:
        res = requests.post("https://spotifymate.com/action", data={"url": spotify_url}, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            m_links = re.findall(r'href="(https://[^"]+\.(?:mp3|m4a|aac)\?[^"]+)"', res.text)
            if not m_links:
                m_links = re.findall(r'href="(https://[^"]+download[^"]+)"', res.text)
                
            for link in m_links:
                clean_link = html.unescape(link)
                logger.info(f"[LOG TERMINAL] 🟢 دانلود از موتور ۳: {clean_link[:60]}...")
                r = requests.get(clean_link, stream=True, headers=HEADERS, timeout=35)
                if r.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk: f.write(chunk)
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1500000:
                        logger.info("[LOG TERMINAL] ✅ دانلود کامل از موتور ۳ انجام شد.")
                        return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Full Track Engine 3: {e}")

    return False

# ============================================================
# حک هوشمند متادیتا و کاور HD متناسب با فرمت فایل
# ============================================================
def embed_cover_and_tags_smart(file_path, title, artist, cover_url):
    try:
        logger.info(f"[LOG TERMINAL] 🎨 حک کردن کاور HD و متادیتا...")
        
        # ۱. تلاش برای حک کردن بر اساس فرمت M4A
        try:
            audio = MP4(file_path)
            audio["\xa9nam"] = [title]
            audio["\xa9ART"] = [artist]
            audio["\xa9alb"] = ["Spotify HQ Release"]
            if cover_url:
                r_img = requests.get(cover_url, headers=HEADERS, timeout=10)
                if r_img.status_code == 200:
                    audio["covr"] = [MP4Cover(r_img.content, imageformat=MP4Cover.FORMAT_JPEG)]
            audio.save()
            logger.info(f"[LOG TERMINAL] ✅ متادیتا روی M4A ذخیره شد.")
            return
        except Exception: pass

        # ۲. تلاش برای حک کردن بر اساس فرمت MP3
        try:
            try:
                audio = ID3(file_path)
            except ID3NoHeaderError:
                audio = ID3()

            audio.add(TIT2(encoding=3, text=title))
            audio.add(TPE1(encoding=3, text=artist))
            audio.add(TALB(encoding=3, text="Spotify HQ Release"))

            if cover_url:
                r_img = requests.get(cover_url, headers=HEADERS, timeout=10)
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
            audio.save(file_path)
            logger.info(f"[LOG TERMINAL] ✅ متادیتا روی MP3 ذخیره شد.")
        except Exception as ex:
            logger.warning(f"[LOG TERMINAL] ⚠️ ID3 Tagging Warn: {ex}")

    except Exception as e:
        logger.error(f"[LOG TERMINAL] ⚠️ خطا در حک متادیتا: {e}")

# ============================================================
# دستورات ربات
# ============================================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    text = (
        f"سلام <b>{message.from_user.first_name}</b> عزیز 👋\n\n"
        "🟢 <b>ربات دانلود کامل موزیک اسپاتیفای با کیفیت ۳۲۰k</b>\n\n"
        "لینک آهنگ اسپاتیفای را ارسال کنید تا فایل کامل (Full Track) همراه با کاور HD دریافت کنید.\n\n"
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
    
    if not meta or not meta.get("title"):
        try:
            bot.edit_message_text("❌ متأسفانه اطلاعات این اثر دریافت نشد.", chat_id, status_msg.message_id)
        except Exception: pass
        return

    display_title = meta["title"]
    display_artist = meta.get("artist") or "Hayedeh"
    cover_url = meta.get("cover")

    try:
        bot.edit_message_text(f"📥 <b>در حال دانلود فایل کامل «{html.escape(display_artist)} - {html.escape(display_title)}» با کیفیت ۳۲۰k...</b>", chat_id, status_msg.message_id)
    except Exception: pass

    filename = f"track_{chat_id}_{int(time.time())}.audio"

    # ۲. دانلود فایل کامل آهنگ (Full Track)
    success = download_full_track(track_id, display_artist, display_title, filename)

    if not success or not os.path.exists(filename) or os.path.getsize(filename) < 1500000:
        logger.error(f"[LOG TERMINAL] 🔴 دانلود کامل فایل ناموفق بود.")
        try:
            bot.edit_message_text("❌ متأسفانه فایل کامل آهنگ یافت نشد. لطفاً دوباره امتحان کنید.", chat_id, status_msg.message_id)
        except Exception: pass
        if os.path.exists(filename): os.remove(filename)
        return

    # ۳. حک کردن کاور HD و متادیتا روی فایل
    embed_cover_and_tags_smart(filename, display_title, display_artist, cover_url)

    file_size_mb = os.path.getsize(filename) / (1024 * 1024)
    logger.info(f"[LOG TERMINAL] ✅ فایل کامل آماده شد، حجم: {file_size_mb:.2f} MB")

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
    logger.info(f"Full Track HQ Bot V{VERSION} Started!")
    
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

