import os
import logging
import re
import tempfile
import glob
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
from difflib import SequenceMatcher

# تنظیمات لاگ (مخفی کردن توکن)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.getLogger('httpx').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# توکن از محیط
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN را در محیط تنظیم کنید!")

def normalize(text: str) -> str:
    """نرمال‌سازی متن: حذف علائم، حروف اضافه، تبدیل به حروف کوچک"""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)  # حذف علائم
    text = re.sub(r'\s+', ' ', text).strip()
    # حذف کلمات اضافه رایج (مثل official, video, audio و...)
    stopwords = {'official', 'audio', 'video', 'lyrics', 'موسیقی', 'آهنگ'}
    words = [w for w in text.split() if w not in stopwords]
    return ' '.join(words)

def extract_track_id(link: str):
    match = re.search(r'/track/([a-zA-Z0-9]+)', link)
    return match.group(1) if match else None

def get_track_info(track_id: str):
    """دریافت عنوان، خواننده، مدت زمان از صفحه اسپاتیفای"""
    url = f"https://open.spotify.com/track/{track_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise Exception("خطا در دریافت صفحه اسپاتیفای")
    soup = BeautifulSoup(resp.text, 'html.parser')
    title = soup.find('meta', property='og:title')
    artist = soup.find('meta', property='og:description')
    duration = None
    if title and artist:
        title = title['content']
        artist = artist['content'].split(' · ')[0]
        title = re.sub(r'\s*Song$', '', title)
        # استخراج مدت زمان از متاتگ‌ها (اگر موجود باشد)
        duration_meta = soup.find('meta', property='music:duration')
        if duration_meta:
            duration = int(duration_meta['content']) // 1000  # میلی‌ثانیه به ثانیه
        return title, artist, duration
    raise Exception("اطلاعات پیدا نشد")

def similarity(a, b):
    """شباهت دو رشته (بعد از نرمال‌سازی)"""
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()

def filter_best_result(entries, title, artist, duration=None, max_results=10):
    """انتخاب بهترین نتیجه بر اساس تطابق عنوان، خواننده و مدت زمان"""
    best_score = 0
    best_entry = None
    
    for entry in entries[:max_results]:
        entry_title = entry.get('title', '')
        entry_artist = entry.get('artist', '') or entry.get('uploader', '')
        entry_duration = entry.get('duration')  # ثانیه
        
        # امتیاز عنوان و خواننده
        title_score = similarity(entry_title, title)
        artist_score = similarity(entry_artist, artist)
        score = title_score * 0.6 + artist_score * 0.4
        
        # اگه مدت زمان موجود باشه، اختلاف مدت هم امتیاز بده
        if duration and entry_duration:
            duration_diff = abs(duration - entry_duration) / max(duration, entry_duration)
            if duration_diff > 0.2:  # اختلاف بیشتر از ۲۰٪ یعنی آهنگ دیگه‌ایه
                score -= 0.3
            else:
                score += 0.1
        
        if score > best_score:
            best_score = score
            best_entry = entry
    
    # اگر بهترین امتیاز خیلی پایین بود، به جای نتیجه‌ی اول برگرد
    if best_score < 0.4:
        logger.warning(f"هیچ نتیجه دقیقی پیدا نشد، امتیاز بهترین: {best_score}")
        return entries[0] if entries else None
    return best_entry

def search_soundcloud(query: str, tmpdir: str, title: str, artist: str, duration=None):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'flac', 'preferredquality': '0'}],
        'extractor_args': {'soundcloud': {'client_id': 'Web'}},
        'match_filter': lambda info: None if (info.get('duration', 0) > 30 and info.get('duration', 0) < 900) else 'Duration out of range'
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search = ydl.extract_info(f"scsearch10:{query}", download=False)
            if 'entries' in search and search['entries']:
                best_entry = filter_best_result(search['entries'], title, artist, duration)
                if best_entry:
                    ydl.download([best_entry['webpage_url']])
                    return True
    except Exception as e:
        logger.warning(f"SoundCloud error: {e}")
    return False

def search_youtube(query: str, tmpdir: str, title: str, artist: str, duration=None):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'flac', 'preferredquality': '0'}],
        'extractor_args': {'youtube': {'player_client': ['android', 'web', 'ios', 'tv']}},
        'match_filter': lambda info: None if (info.get('duration', 0) > 60 and info.get('duration', 0) < 600) else 'Duration out of range'
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search = ydl.extract_info(f"ytsearch10:{query} audio", download=False)
            if 'entries' in search and search['entries']:
                best_entry = filter_best_result(search['entries'], title, artist, duration)
                if best_entry:
                    ydl.download([best_entry['webpage_url']])
                    return True
    except Exception as e:
        logger.warning(f"YouTube error: {e}")
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! لینک اسپاتیفای رو بفرست تا آهنگ دقیق رو برات دانلود کنم. 🎵")

async def handle_spotify_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    track_id = extract_track_id(link)
    if not track_id:
        await update.message.reply_text("لینک معتبر نیست.")
        return

    await update.message.reply_text("در حال دریافت اطلاعات آهنگ...")
    try:
        title, artist, duration = get_track_info(track_id)
        query = f"{title} {artist}"
        await update.message.reply_text(f"🎵 {title} - {artist}\nدر حال جستجو در ساندکلود...")

        with tempfile.TemporaryDirectory() as tmpdir:
            success = search_soundcloud(query, tmpdir, title, artist, duration)
            if not success:
                await update.message.reply_text("ساندکلود جواب نداد، تلاش از یوتیوب...")
                success = search_youtube(query, tmpdir, title, artist, duration)

            if not success:
                await update.message.reply_text("هیچ منبع دقیقی پیدا نشد.")
                return

            files = glob.glob(os.path.join(tmpdir, "*.flac")) or glob.glob(os.path.join(tmpdir, "*.mp3"))
            if not files:
                await update.message.reply_text("فایل پیدا نشد.")
                return

            audio_file = files[0]
            with open(audio_file, 'rb') as f:
                await update.message.reply_audio(audio=f, title=os.path.basename(audio_file))

    except Exception as e:
        logger.exception(f"Error: {e}")
        await update.message.reply_text(f"خطا: {e}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_spotify_link))
    logger.info("ربات شروع به کار کرد...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
