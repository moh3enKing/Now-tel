# ============================================================
# ربات دانلود مستقیم ۳۲۰kbps واقعی از سرورهای موزیک (Deezer Engine)
# ============================================================

import os
import re
import json
import sys
import time
import ssl
import logging
import threading
import html
import requests
import urllib.parse
import urllib.request
from flask import Flask
import telebot
from telebot.apihelper import ApiTelegramException

# تزریق متادیتا و کاور HD روی MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, ID3NoHeaderError
from Crypto.Cipher import Blowfish

# ============================================================
# تنظیمات اصلی
# ============================================================
TOKEN = "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY"
# توکن ARL دیزر برای دسترسی مستقیم به استریم‌های کیفیت بالا (320kbps MP3 / FLAC)
DEEZER_ARL = "e0b9fae2ed64f52fa4b0cb89c937f3eb30fb8d49830db9dc4d38dca5eb90a3a41b52e2be8efbb081825838d76d4948a3c861e6fa0bd4fca14dfd5fa7b0bd1929"
DATA_FILE = "audio_bot_db.json"
VERSION = "15.0-DeezerHQEngine"

# ============================================================
# تنظیم سیستم لاگ
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("DeezerHQBot")

# ============================================================
# سرور Flask جهت نگهداشت آنلاین در Render
# ============================================================
app = Flask('')
@app.route('/')
def home():
    return f"Spotify-Deezer HQ Audio Bot V:{VERSION} is Online!"

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
    "Accept-Language": "en-US,en;q=0.9",
}

# ============================================================
# کلیدهای رمزگشایی فایل‌های Deezer
# ============================================================
def get_blowfish_key(track_id):
    SECRET = "g42fzcuhw2022bcd"
    md5_id = requests.utils.hashlib.md5(str(track_id).encode('utf-8')).hexdigest()
    key = ""
    for i in range(16):
        key += chr(ord(md5_id[i]) ^ ord(md5_id[i + 16]) ^ ord(SECRET[i]))
    return key.encode('utf-8')

def decrypt_chunk(chunk, key):
    cipher = Blowfish.new(key, Blowfish.MODE_CBC, bytes([0, 1, 2, 3, 4, 5, 6, 7]))
    return cipher.decrypt(chunk)

# ============================================================
# استخراج کامل متادیتای اسپاتیفای
# ============================================================
def get_spotify_track_meta(url):
    logger.info(f"[LOG TERMINAL] 🔍 دریافت متادیتای اسپاتیفای: {url}")
    m = re.search(r"track/([A-Za-z0-9]{22})", url)
    track_id = m.group(1) if m else None
    clean_url = f"https://open.spotify.com/track/{track_id}" if track_id else url

    title, artist, cover = "", "", ""
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
            
            if og_title:
                raw_t = html.unescape(og_title.group(1).strip())
                if " - " in raw_t:
                    parts = raw_t.split(" - ", 1)
                    artist, title = parts[0].strip(), parts[1].strip()
                else:
                    title = raw_t

            if og_img: cover = og_img.group(1)
            
            if og_desc:
                desc = html.unescape(og_desc.group(1).strip())
                parts = [p.strip() for p in re.split(r'[·•:-]', desc) if p.strip()]
                for p in parts:
                    if p.lower() not in ["song", "single", "album", "listen on spotify"] and p.lower() != title.lower() and not p.isdigit():
                        if not artist:
                            artist = p
                            break

            if title:
                logger.info(f"[LOG TERMINAL] ✅ استخراج متادیتا موفق: خواننده='{artist}', آهنگ='{title}'")
                return {"title": title, "artist": artist, "cover": cover}
    except Exception as e:
        logger.warning(f"[LOG TERMINAL] ⚠️ خطا در استخراج متادیتای اسپاتیفای: {e}")

    return None

# ============================================================
# دریافت استریم ۳۲۰kbps از سرور Deezer
# ============================================================
def download_deezer_hq(artist, title, output_path):
    try:
        session = requests.Session()
        session.cookies.set("arl", DEEZER_ARL)
        
        # ۱. دریافت Sid و User Token از Deezer
        user_resp = session.post("https://www.deezer.com/ajax/gw-light.php?method=deezer.getUserData&api_version=1.0&api_token=", headers=HEADERS, timeout=10)
        user_data = user_resp.json()
        api_token = user_data.get("results", {}).get("checkForm")

        # ۲. جستجوی آهنگ در Deezer
        query = f"{artist} {title}".strip()
        search_res = session.get(f"https://api.deezer.com/search?q={urllib.parse.quote(query)}", headers=HEADERS, timeout=10).json()
        tracks = search_res.get("data", [])

        if not tracks:
            logger.warning("[LOG TERMINAL] ⚠️ آهنگ در Deezer یافت نشد.")
            return False

        track_info = tracks[0]
        deezer_id = track_info["id"]

        # ۳. دریافت اطلاعات استریم مستقیم با کیفیت MP3 320kbps
        track_req = session.post(
            f"https://www.deezer.com/ajax/gw-light.php?method=song.getData&api_version=1.0&api_token={api_token}",
            json={"sng_id": deezer_id},
            headers=HEADERS,
            timeout=10
        ).json()

        sng_data = track_req.get("results", {})
        md5_origin = sng_data.get("MD5_ORIGIN")
        media_version = sng_data.get("MEDIA_VERSION")
        format_code = "3" # کد 3 یعنی MP3 320kbps

        # ساخت URL دانلود مستقیم سرور
        url_part = f"{md5_origin}¤{format_code}¤{deezer_id}¤{media_version}".encode('utf-8')
        md5_part = requests.utils.hashlib.md5(url_part).hexdigest()
        
        # کلید Blowfish جهت رمزگشایی
        bf_key = get_blowfish_key(deezer_id)
        
        stream_url = f"https://e-cdns-proxy-{md5_origin[0]}.dzcdn.net/mobile/1/{md5_part}"
        
        logger.info(f"[LOG TERMINAL] ⚡️ در حال دریافت بایت‌های اصلی ۳۲۰kbps از سرور Deezer...")
        
        # ۴. دانلود و رمزگشایی چانک‌های فایل صوتی
        r = session.get(stream_url, stream=True, timeout=30)
        if r.status_code == 200:
            with open(output_path, "wb") as f:
                i = 0
                for chunk in r.iter_content(chunk_size=2048):
                    if not chunk:
                        continue
                    if i % 3 == 0 and len(chunk) == 2048:
                        chunk = decrypt_chunk(chunk, bf_key)
                    f.write(chunk)
                    i += 1

            if os.path.exists(output_path) and os.path.getsize(output_path) > 100000:
                logger.info("[LOG TERMINAL] ✅ دانلود مستقیم ۳۲۰kbps از سرور با موفقیت انجام شد.")
                return True

    except Exception as e:
        logger.error(f"[LOG TERMINAL] 🔴 خطا در دانلود از Deezer: {e}")

    return False

# ============================================================
# حک کردن کاور رسمی HD و متادیتا روی MP3
# ============================================================
def embed_cover_and_tags(mp3_path, title, artist, cover_url):
    try:
        try:
            audio = ID3(mp3_path)
        except ID3NoHeaderError:
            audio = ID3()

        audio.add(TIT2(encoding=3, text=title))
        audio.add(TPE1(encoding=3, text=artist))
        audio.add(TALB(encoding=3, text="Spotify HQ Release"))

        if cover_url:
            r_img = requests.get(cover_url, headers=HEADERS, timeout=15)
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
    except Exception as e:
        logger.error(f"[LOG TERMINAL] ⚠️ خطا در حک کاور: {e}")

# ============================================================
# دستورات ربات
# ============================================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    text = (
        f"سلام <b>{message.from_user.first_name}</b> عزیز 👋\n\n"
        "🟢 <b>ربات دانلود مستقیم فایل صوتی با کیفیت ۳۲۰kbps اصلی</b>\n\n"
        "بدون استفاده از یوتیوب یا ساندکلاد، فایل‌های ۳۲۰k واقعی مستقیماً از CDN سرور دانلود می‌شوند.\n\n"
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

    # ۱. استخراج متادیتا
    meta = get_spotify_track_meta(url)
    
    if not meta or not meta.get("title"):
        try:
            bot.edit_message_text("❌ متأسفانه لینک اسپاتیفای معتبر نیست یا اثر یافت نشد.", chat_id, status_msg.message_id)
        except Exception: pass
        return

    display_title = meta["title"]
    display_artist = meta["artist"] or "Spotify Artist"
    cover_url = meta.get("cover")

    try:
        bot.edit_message_text(f"📥 <b>در حال دانلود مستقیم «{html.escape(display_artist)} - {html.escape(display_title)}» با کیفیت ۳۲۰kbps اصلی...</b>", chat_id, status_msg.message_id)
    except Exception: pass

    filename = f"track_{chat_id}_{int(time.time())}.mp3"

    # ۲. دانلود ۳۲۰k مستقیم از سرور
    success = download_deezer_hq(display_artist, display_title, filename)

    if not success or not os.path.exists(filename) or os.path.getsize(filename) < 100000:
        logger.error(f"[LOG TERMINAL] 🔴 دانلود فایل ۳۲۰k ناموفق بود.")
        try:
            bot.edit_message_text("❌ متأسفانه اثر مورد نظر در سرور با کیفیت ۳۲۰k یافت نشد.", chat_id, status_msg.message_id)
        except Exception: pass
        if os.path.exists(filename): os.remove(filename)
        return

    # ۳. حک کردن کاور اصلی اسپاتیفای و متادیتا روی فایل
    embed_cover_and_tags(filename, display_title, display_artist, cover_url)

    file_size_mb = os.path.getsize(filename) / (1024 * 1024)
    logger.info(f"[LOG TERMINAL] ✅ فایل نهایی با کیفیت ۳۲۰k آماده شد، حجم: {file_size_mb:.2f} MB")

    # ۴. ارسال کاور جداگانه
    if cover_url:
        try:
            bot.send_photo(chat_id, cover_url, caption=f"🖼 <b>کاور رسمی: {html.escape(display_title)} - {html.escape(display_artist)}</b>")
        except Exception as e:
            logger.warning(f"[LOG TERMINAL] ⚠️ خطا در ارسال عکس کاور: {e}")

    try:
        try:
            bot.edit_message_text("📤 <b>در حال آپلود فایل صوتی اصلی به تلگرام...</b>", chat_id, status_msg.message_id)
        except Exception: pass

        with open(filename, 'rb') as audio_file:
            caption = f"🎵 <b>{html.escape(display_title)}</b>\n🎤 <b>{html.escape(display_artist)}</b>\n\n💎 <i>کیفیت صوتی اصلی MP3 320kbps - دانلود مستقیم از سرور CDN</i>"
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
    logger.info(f"Deezer HQ Bot V{VERSION} Started!")
    
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

