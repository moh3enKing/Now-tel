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

# برای مقایسه دقیق متن
try:
    from rapidfuzz import fuzz, utils
    USE_RAPIDFUZZ = True
except ImportError:
    from difflib import SequenceMatcher
    USE_RAPIDFUZZ = False
    def fuzz_ratio(a, b):
        return SequenceMatcher(None, a, b).ratio()
    def fuzz_partial_ratio(a, b):
        return SequenceMatcher(None, a, b).ratio()
    def fuzz_token_set_ratio(a, b):
        return SequenceMatcher(None, a, b).ratio()

# تنظیمات لاگ (مخفی کردن توکن)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.getLogger('httpx').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# توکن از محیط
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN را در محیط تنظیم کنید!")

def normalize_text(text: str) -> str:
    """نرمال‌سازی متن فارسی و انگلیسی"""
    if not text:
        return ""
    text = text.lower()
    # تبدیل حروف عربی به فارسی
    text = text.replace('ي', 'ی').replace('ك', 'ک')
    # حذف نیم‌فاصله و علائم
    text = text.replace('\u200c', ' ').replace('‌', ' ')
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    # حذف کلمات اضافه رایج
    stopwords = {'official', 'audio', 'video', 'lyrics', 'موسیقی', 'آهنگ', 'دانلود', 'ریمیکس', 'remix', 'cover'}
    words = [w for w in text.split() if w not in stopwords]
    return ' '.join(words)

def similarity_ratio(a: str, b: str) -> float:
    """شباهت دو متن (۰ تا ۱)"""
    if not a or not b:
        return 0.0
    a_norm = normalize_text(a)
    b_norm = normalize_text(b)
    if USE_RAPIDFUZZ:
        return fuzz.ratio(a_norm, b_norm) / 100.0
    else:
        return fuzz_ratio(a_norm, b_norm)

def token_set_ratio(a: str, b: str) -> float:
    """شباهت با در نظر گرفتن ترتیب کلمات (برای تشخیص جابجایی)"""
    if not a or not b:
        return 0.0
    a_norm = normalize_text(a)
    b_norm = normalize_text(b)
    if USE_RAPIDFUZZ:
        return fuzz.token_set_ratio(a_norm, b_norm) / 100.0
    else:
        return fuzz_token_set_ratio(a_norm, b_norm)

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
        # حذف پسوند "Song" از عنوان (در برخی صفحات)
        title = re.sub(r'\s*Song$', '', title, flags=re.IGNORECASE)
        # استخراج مدت زمان از متاتگ‌ها
        duration_meta = soup.find('meta', property='music:duration')
        if duration_meta:
            try:
                duration = int(duration_meta['content']) // 1000  # ثانیه
            except:
                duration = None
        return title, artist, duration
    raise Exception("اطلاعات پیدا نشد")

def is_duration_match(duration_expected, duration_actual, tolerance=0.15):
    """بررسی تطابق مدت زمان (با تلورانس ۱۵٪)"""
    if not duration_expected or not duration_actual:
        return True  # اگه یکی نبود، قبول کن (نمی‌خوایم رد کنیم)
    diff = abs(duration_expected - duration_actual) / max(duration_expected, duration_actual)
    return diff <= tolerance

def score_entry(entry, title, artist, duration):
    """امتیازدهی به یک نتیجه بر اساس تطابق عنوان، خواننده و مدت زمان"""
    entry_title = entry.get('title', '')
    entry_artist = entry.get('artist', '') or entry.get('uploader', '')
    entry_duration = entry.get('duration')  # ثانیه
    
    # امتیاز عنوان (ترکیب ratio و token_set_ratio)
    title_score = similarity_ratio(entry_title, title)
    title_token_score = token_set_ratio(entry_title, title)
    title_final = max(title_score, title_token_score)
    
    # امتیاز خواننده
    artist_score = similarity_ratio(entry_artist, artist)
    artist_token_score = token_set_ratio(entry_artist, artist)
    artist_final = max(artist_score, artist_token_score)
    
    # امتیاز نهایی (عنوان مهم‌تر از خواننده)
    final_score = (title_final * 0.65) + (artist_final * 0.35)
    
    # اگر مدت زمان موجود باشه و تطابق نداشته باشه، امتیاز رو خیلی کم کن
    if not is_duration_match(duration, entry_duration):
        final_score -= 0.4
    
    # اگر عنوان دقیقاً یکی باشه (شباهت > 0.9) امتیاز اضافه بده
    if title_final > 0.9:
        final_score += 0.1
    
    return final_score

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
        query = f"{title} {artist} audio"
        await update.message.reply_text(f"🎵 {title} - {artist}\nدر حال جستجو...")

        # تنظیمات yt-dlp
        ydl_opts_base = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'flac', 'preferredquality': '0'}],
            'match_filter': lambda info: None if (info.get('duration', 0) > 30 and info.get('duration', 0) < 900) else 'Duration out of range'
        }

        best_entry = None
        best_score = 0
        best_source = None

        with tempfile.TemporaryDirectory() as tmpdir:
            # ۱. جستجو در ساندکلود
            try:
                ydl_opts_soundcloud = {**ydl_opts_base, 'extractor_args': {'soundcloud': {'client_id': 'Web'}}}
                with yt_dlp.YoutubeDL(ydl_opts_soundcloud) as ydl:
                    search = ydl.extract_info(f"scsearch10:{query}", download=False)
                    if 'entries' in search and search['entries']:
                        for entry in search['entries']:
                            score = score_entry(entry, title, artist, duration)
                            if score > best_score:
                                best_score = score
                                best_entry = entry
                                best_source = 'soundcloud'
            except Exception as e:
                logger.warning(f"SoundCloud search error: {e}")

            # ۲. جستجو در یوتیوب
            try:
                ydl_opts_youtube = {**ydl_opts_base, 'extractor_args': {'youtube': {'player_client': ['android', 'web', 'ios', 'tv']}}}
                with yt_dlp.YoutubeDL(ydl_opts_youtube) as ydl:
                    search = ydl.extract_info(f"ytsearch10:{query}", download=False)
                    if 'entries' in search and search['entries']:
                        for entry in search['entries']:
                            score = score_entry(entry, title, artist, duration)
                            if score > best_score:
                                best_score = score
                                best_entry = entry
                                best_source = 'youtube'
            except Exception as e:
                logger.warning(f"YouTube search error: {e}")

            # اگر بهترین نتیجه امتیاز قابل قبولی داشت، دانلود کن
            if best_entry and best_score > 0.6:
                source_name = "ساندکلود" if best_source == "soundcloud" else "یوتیوب"
                await update.message.reply_text(f"بهترین نتیجه از {source_name} پیدا شد. در حال دانلود...")
                try:
                    # دانلود از منبع مناسب
                    ydl_opts_final = {**ydl_opts_base}
                    if best_source == "soundcloud":
                        ydl_opts_final['extractor_args'] = {'soundcloud': {'client_id': 'Web'}}
                    elif best_source == "youtube":
                        ydl_opts_final['extractor_args'] = {'youtube': {'player_client': ['android', 'web', 'ios', 'tv']}}
                    
                    with yt_dlp.YoutubeDL(ydl_opts_final) as ydl:
                        ydl.download([best_entry['webpage_url']])
                    
                    files = glob.glob(os.path.join(tmpdir, "*.flac")) or glob.glob(os.path.join(tmpdir, "*.mp3"))
                    if files:
                        audio_file = files[0]
                        with open(audio_file, 'rb') as f:
                            await update.message.reply_audio(audio=f, title=os.path.basename(audio_file))
                    else:
                        await update.message.reply_text("فایل خروجی پیدا نشد.")
                except Exception as e:
                    logger.error(f"Download error: {e}")
                    await update.message.reply_text("خطا در دانلود فایل.")
            else:
                await update.message.reply_text("آهنگ دقیقی پیدا نشد. لینک رو چک کن یا بعداً دوباره تلاش کن.")

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
