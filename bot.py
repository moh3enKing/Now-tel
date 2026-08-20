# ============================================================
# ربات واسط هوشمند (Bridge UserBot) جهت دریافت کیفیت Lossless/ALAC
# از ربات @AppleMusic_DL_bot بدون نیاز به api_id اختصاصی
# ============================================================

import os
import re
import json
import asyncio
import logging
import urllib.parse
import requests
from flask import Flask
from threading import Thread
from pyrogram import Client, filters, enums
from pyrogram.types import Message, CallbackQuery

# ============================================================
# تنظیمات اصلی (استفاده از API_ID عمومی رسمی تلگرام)
# ============================================================
API_ID = 2040  # API_ID رسمی تلگرام وب
API_HASH = "b18441a12607e109353316371075a3f1"  # API_HASH رسمی تلگرام وب

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY")
# رشته Session اکانت تلگرام واسط (در صورت وجود در متغیرهای محیطی)
SESSION_STRING = os.environ.get("SESSION_STRING", "")

TARGET_BOT = "AppleMusic_DL_bot" # آیدی ربات دانلودر اپل موزیک
PREFERRED_QUALITY = "ALAC — Lossless" # کیفیت درخواستی (یا "AAC 256 kbps")

# ذخیره‌سازی درخواست‌های فعال کاربران {user_id_in_target_bot: original_chat_id}
pending_requests = {}

# ============================================================
# لاگ سرور
# ============================================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("BridgeBot")

# ============================================================
# سرور Flask جهت روشن ماندن روی Render
# ============================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Telegram Lossless Bridge Bot is Running!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_web, daemon=True).start()

# ============================================================
# تعریف کلاینت‌های Pyrogram (کلاینت ربات + کلاینت اکانت واسط)
# ============================================================
bot_app = Client("bot_side", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

if SESSION_STRING:
    user_app = Client("user_side", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
else:
    # در صورت عدم وجود Session String، جلسه متنی ایجاد می‌شود
    user_app = Client("user_side", api_id=API_ID, api_hash=API_HASH)

# ============================================================
# تبدیل لینک اسپاتیفای به لینک اپل موزیک (با iTunes API)
# ============================================================
def spotify_to_apple_music(spotify_url):
    try:
        # استخراج متادیتا از oEmbed اسپاتیفای
        oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(spotify_url)}"
        res = requests.get(oembed_url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            title = data.get("title", "")
            artist = data.get("author_name", "")
            
            if " - " in title and not artist:
                parts = title.split(" - ", 1)
                artist, title = parts[0].strip(), parts[1].strip()

            search_query = f"{artist} {title}".strip()
            logger.info(f"🔎 جستجوی اپل موزیک برای: {search_query}")
            
            # جستجو در iTunes API رسمی و رایگان
            itunes_url = f"https://itunes.apple.com/search?term={urllib.parse.quote(search_query)}&entity=song&limit=1"
            it_res = requests.get(itunes_url, timeout=5)
            if it_res.status_code == 200:
                results = it_res.json().get("results", [])
                if results:
                    track_url = results[0].get("trackViewUrl")
                    logger.info(f"✅ لینک اپل موزیک یافت شد: {track_url}")
                    return track_url
    except Exception as e:
        logger.error(f"⚠️ خطا در تبدیل اسپاتیفای به اپل موزیک: {e}")
    
    return None

# ============================================================
# هندلر ربات تلگرام اصلی (دریافت پیام از کاربر)
# ============================================================
@bot_app.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    await message.reply_text(
        f"سلام **{message.from_user.first_name}** عزیز 👋\n\n"
        "🎵 **ربات دانلود مستقیم کیفیت استودیویی (Lossless / ALAC / AAC 256k)**\n\n"
        "لینک **اسپاتیفای** یا **اپل موزیک** را بفرستید تا فایل اصلی با بالاترین کیفیت کیفیت ارسال شود."
    )

@bot_app.on_message(filters.text & filters.private)
async def handle_user_link(client: Client, message: Message):
    text = message.text.strip()
    chat_id = message.chat.id

    apple_url = None

    if "music.apple.com" in text:
        apple_url = text
    elif "spotify.com" in text:
        status_msg = await message.reply_text("🔎 **در حال تبدیل لینک اسپاتیفای به اپل موزیک...**")
        apple_url = spotify_to_apple_music(text)
        if not apple_url:
            await status_msg.edit_text("❌ متأسفانه این اثر در اپل موزیک یافت نشد.")
            return
        await status_msg.delete()
    else:
        await message.reply_text("❌ لطفاً یک لینک معتبر از اسپاتیفای یا اپل موزیک ارسال کنید.")
        return

    status = await message.reply_text("🚀 **در حال ارسال به موتور استخراج کیفیت اصلی ALAC/Lossless...**")

    try:
        # ۱. ارسال لینک از طریق اکانت واسط به ربات AppleMusic_DL_bot
        sent_msg = await user_app.send_message(TARGET_BOT, apple_url)
        
        # ذخیره ثبت درخواست
        pending_requests[sent_msg.id] = {
            "user_chat_id": chat_id,
            "status_msg_id": status.id,
            "time": asyncio.get_event_loop().time()
        }
        
    except Exception as e:
        logger.error(f"🔴 خطا در ارتباط با اکانت واسط: {e}")
        await status.edit_text("❌ خطایی در سیستم واسط رخ داد. لطفا دوباره تلاش کنید.")

# ============================================================
# هندلر اکانت واسط (UserBot) برای دریافت پاسخ از @AppleMusic_DL_bot
# ============================================================
@user_app.on_message(filters.chat(TARGET_BOT))
async def handle_target_bot_response(client: Client, message: Message):
    logger.info(f"📩 دریافت پاسخ جدید از {TARGET_BOT}")

    # ۱. اگر ربات هدف دکمه‌های شیشه‌ای کیفیت فرستاد
    if message.reply_markup and message.reply_markup.inline_keyboard:
        logger.info("🔘 دکمه‌های انتخاب کیفیت دریافت شد. در حال کلیک خودکار...")
        clicked = False
        
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                # جستجو برای دکمه کیفیت ALAC یا AAC
                if PREFERRED_QUALITY.lower() in btn.text.lower() or "alac" in btn.text.lower() or "lossless" in btn.text.lower():
                    try:
                        await user_app.request_callback_answer(
                            chat_id=message.chat.id,
                            message_id=message.id,
                            callback_data=btn.callback_data
                        )
                        logger.info(f"✅ دکمه '{btn.text}' با موفقیت کلیک شد.")
                        clicked = True
                        break
                    except Exception as e:
                        logger.error(f"⚠️ خطا در کلیک دکمه: {e}")
            if clicked:
                break

        # اگر کیفیت پیش‌فرض پیدا نشد، روی دکمه اول کلیک کن
        if not clicked and message.reply_markup.inline_keyboard[0]:
            first_btn = message.reply_markup.inline_keyboard[0][0]
            try:
                await user_app.request_callback_answer(
                    chat_id=message.chat.id,
                    message_id=message.id,
                    callback_data=first_btn.callback_data
                )
                logger.info(f"✅ دکمه پیش‌فرض '{first_btn.text}' کلیک شد.")
            except Exception: pass

    # ۲. اگر ربات هدف فایل صوتی را فرستاد
    elif message.audio or message.document:
        logger.info("🎵 فایل صوتی اصلی دریافت شد! در حال ارسال به کاربر...")
        
        # یافتن آخرین کاربر درخواست‌کننده
        if pending_requests:
            req_key = list(pending_requests.keys())[-1]
            req_info = pending_requests.pop(req_key)
            
            user_chat_id = req_info["user_chat_id"]
            status_msg_id = req_info["status_msg_id"]

            try:
                # حذف پیام در حال پردازش
                await bot_app.delete_messages(user_chat_id, status_msg_id)
            except Exception: pass

            # ارسال خود فایل برای کاربر
            await user_app.copy_message(
                chat_id=user_chat_id,
                from_chat_id=message.chat.id,
                message_id=message.id,
                caption="💎 **کیفیت استودیویی اورجینال (ALAC / Lossless)**"
            )
            logger.info(f"🎉 فایل با موفقیت برای کاربر {user_chat_id} ارسال شد.")

# ============================================================
# استارت همزمان کلاینت‌ها
# ============================================================
async def main():
    await bot_app.start()
    await user_app.start()
    logger.info("🚀 ربات واسط و کلاینت UserBot با موفقیت روشن شدند!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

