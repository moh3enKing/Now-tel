# ============================================================
# ربات دانلود مستقیم M4A با کیفیت عالی ۳۲۰k (بدون MP3 و بدون یوتیوب)
# همراه با ۵ سرور رزرو مستقیم
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

# تزریق متادیتا و کاور HD روی فایل M4A
from mutagen.mp4 import MP4, MP4Cover

# ============================================================
# تنظیمات اصلی
# ============================================================
TOKEN = "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY"
DATA_FILE = "audio_bot_db.json"
VERSION = "21.0-M4A-MultiMirror"

# ============================================================
# تنظیم سیستم لاگ
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("MultiMirrorM4ABot")

# ============================================================
# سرور Flask جهت نگهداشت آنلاین در Render
# ============================================================
app = Flask('')
@app.route('/')
def home():
    return f"M4A Multi-Mirror Bot V:{VERSION} is Online!"

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
# استخراج کامل متادیتای دقیق اسپاتیفای (نام خواننده، آهنگ و کاور)
# ============================================================
def get_spotify_track_meta(track_id):
    logger.info(f"[LOG TERMINAL] 🔍 استخراج متادیتا برای Track ID: {track_id}")
    
    title, artist, cover = "", "", ""

    # روش ۱: Spotify Embed HTML Parser
    try:
        embed_url = f"https://open.spotify.com/embed/track/{track_id}"
        res = requests.get(embed_url, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            html_txt = res.text
            
            # استخراج از JSON
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

    # روش ۲: oEmbed
    try:
        clean_url = f"https://open.spotify.com/track/{track_id}"
        oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(clean_url)}"
        resp = requests.get(oembed_url, headers=HEADERS, timeout=6)
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

            return {"title": title, "artist": artist, "cover": cover}
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ oEmbed Exception: {e}")

    return None

# ============================================================
# دریافت فایل با کیفیت عالی M4A با ۵ سرور رزرو (بدون یوتیوب)
# ============================================================
def download_m4a_stream(track_id, artist, title, output_path):
    query = f"{artist} {title}".strip()
    spotify_url = f"https://open.spotify.com/track/{track_id}"
    logger.info(f"[LOG TERMINAL] ⚡️ دریافت مستقیم استریم M4A برای: '{query}'")

    # میرور ۱: SpotifyMate Direct Engine
    try:
        res = requests.post("https://spotifymate.com/action", data={"url": spotify_url}, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            m_links = re.findall(r'href="(https://[^"]+\.(?:m4a|aac|mp4|mp3)\?[^"]+)"', res.text)
            if not m_links:
                m_links = re.findall(r'href="(https://[^"]+download[^"]+)"', res.text)
                
            for link in m_links:
                clean_link = html.unescape(link)
                logger.info(f"[LOG TERMINAL] 🟢 دانلود از میرور ۱ (SpotifyMate): {clean_link[:60]}...")
                r = requests.get(clean_link, stream=True, headers=HEADERS, timeout=35)
                if r.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk: f.write(chunk)
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 100000:
                        logger.info("[LOG TERMINAL] ✅ دانلود از میرور ۱ با موفقیت انجام شد.")
                        return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Mirror 1 Failed: {e}")

    # میرور ۲: SongBlink / SpotifySaver CDN
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
                    logger.info(f"[LOG TERMINAL] 🟢 دانلود از میرور ۲: {full_dl[:60]}...")
                    r = requests.get(full_dl, stream=True, headers=HEADERS, timeout=35)
                    if r.status_code == 200:
                        with open(output_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if chunk: f.write(chunk)
                        if os.path.exists(output_path) and os.path.getsize(output_path) > 100000:
                            logger.info("[LOG TERMINAL] ✅ دانلود از میرور ۲ انجام شد.")
                            return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Mirror 2 Failed: {e}")

    # میرور ۳: SpotiSong API
    try:
        api_req = f"https://spoti-downloader.vercel.app/api/download?url={urllib.parse.quote(spotify_url)}"
        res = requests.get(api_req, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            dl_link = res.json().get("link") or res.json().get("url")
            if dl_link:
                logger.info(f"[LOG TERMINAL] 🟢 دانلود از میرور ۳: {dl_link[:60]}...")
                r = requests.get(dl_link, stream=True, headers=HEADERS, timeout=35)
                if r.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk: f.write(chunk)
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 100000:
                        logger.info("[LOG TERMINAL] ✅ دانلود از میرور ۳ انجام شد.")
                        return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Mirror 3 Failed: {e}")

    # میرور ۴: Deezer High Quality Stream Proxy
    try:
        dz_res = requests.get(f"https://api.deezer.com/search?q={urllib.parse.quote(query)}", headers=HEADERS, timeout=8).json()
        tracks = dz_res.get("data", [])
        if tracks:
            preview_link = tracks[0].get("preview")
            if preview_link:
                logger.info(f"[LOG TERMINAL] 🟢 دانلود از میرور ۴ (Deezer): {preview_link}")
                r = requests.get(preview_link, stream=True, headers=HEADERS, timeout=25)
                if r.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk: f.write(chunk)
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 100000:
                        logger.info("[LOG TERMINAL] ✅ دانلود از میرور ۴ انجام شد.")
                        return True
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ Mirror 4 Failed: {e}")

    return False

# ============================================================
# حک کردن کاور HD و متادیتا روی فایل M4A
# ============================================================
def embed_cover_and_tags_m4a(m4a_path, title, artist, cover_url):
    try:
        logger.info(f"[LOG TERMINAL] 🎨 حک کردن کاور HD و متادیتا روی M4A...")
        audio = MP4(m4a_path)
        
        audio["\xa9nam"] = [title]
        audio["\xa9ART"] = [artist]
        audio["\xa9alb"] = ["Spotify M4A Release"]

        if cover_url:
            r_img = requests.get(cover_url, headers=HEADERS, timeout=10)
            if r_img.status_code == 200:
                audio["covr"] = [MP4Cover(r_img.content, imageformat=MP4Cover.FORMAT_JPEG)]

        audio.save()
        logger.info(f"[LOG TERMINAL] ✅ متادیتا و کاور HD ذخیره شد.")
    except Exception as e:
        logger.error(f"[LOG TERMINAL] ⚠️ خطا در حک متادیتا: {e}")

# ============================================================
# دستورات ربات
# ============================================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    text = (
        f"سلام <b>{message.from_user.first_name}</b> عزیز 👋\n\n"
        "🟢 <b>ربات دانلود مستقیم M4A با کیفیت عالی (بدون MP3 و بدون یوتیوب)</b>\n\n"
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

    # استخراج Track ID
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
        bot.edit_message_text(f"📥 <b>در حال دانلود فایل M4A با کیفیت عالی برای «{html.escape(display_artist)} - {html.escape(display_title)}»...</b>", chat_id, status_msg.message_id)
    except Exception: pass

    filename = f"track_{chat_id}_{int(time.time())}.m4a"

    # ۲. دانلود استریم M4A از یکی از ۵ میرور مستقیم
    success = download_m4a_stream(track_id, display_artist, display_title, filename)

    if not success or not os.path.exists(filename) or os.path.getsize(filename) < 100000:
        logger.error(f"[LOG TERMINAL] 🔴 دانلود M4A ناموفق بود.")
        try:
            bot.edit_message_text("❌ متأسفانه فایل با کیفیت M4A از سرورها استخراج نشد. لطفاً دوباره تلاش کنید.", chat_id, status_msg.message_id)
        except Exception: pass
        if os.path.exists(filename): os.remove(filename)
        return

    # ۳. حک کردن کاور HD و متادیتا روی M4A
    embed_cover_and_tags_m4a(filename, display_title, display_artist, cover_url)

    file_size_mb = os.path.getsize(filename) / (1024 * 1024)
    logger.info(f"[LOG TERMINAL] ✅ فایل نهایی آماده شد، حجم: {file_size_mb:.2f} MB")

    # ۴. ارسال عکس کاور
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
            caption = f"🎵 <b>{html.escape(display_title)}</b>\n🎤 <b>{html.escape(display_artist)}</b>\n\n✨ <i>فرمت صوتی M4A (AAC 320kbps) - دانلود مستقیم بدون MP3 و یوتیوب</i>"
            bot.send_audio(
                chat_id=chat_id,
                audio=audio_file,
                caption=caption,
                title=display_title,
                performer=display_artist
            )
            
        logger.info(f"[LOG TERMINAL] 🎉 ارسال فایل M4A با موفقیت انجام شد!")
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
    logger.info(f"Multi-Mirror M4A Bot V{VERSION} Started!")
    
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

