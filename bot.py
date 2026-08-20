# ============================================================
# ربات واسط هوشمند + سیستم لاگین تلگرامی اختصاصی بدون نیاز به ترمینال/iSH
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

# فیکس Event Loop در پایتون ۳.۱۰ به بالا
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PasswordHashInvalid

# ============================================================
# تنظیمات اصلی (استفاده از API عمومی رسمی تلگرام وب)
# ============================================================
API_ID = 2040  
API_HASH = "b18441a12607e109353316371075a3f1"  

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

TARGET_BOT = "AppleMusic_DL_bot"
PREFERRED_QUALITY = "ALAC — Lossless"

# آیدی تلگرامی سازنده ربات (برای امنیت دستور /login)
ADMIN_ID = None  # اولین کسی که /start یا /login بزند ادمین می‌شود

# وضعیت‌های لاگین موقت
user_login_states = {}
pending_requests = {}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("BridgeBot")

# ============================================================
# سرور Flask جهت نگهداشت آنلاین در Render
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
# کلاینت اصلی ربات
# ============================================================
bot_app = Client("bot_side", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# کلاینت اکانت واسط
user_app = None
if SESSION_STRING:
    user_app = Client("user_side", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)

# ============================================================
# تبدیل لینک اسپاتیفای به لینک اپل موزیک
# ============================================================
def spotify_to_apple_music(spotify_url):
    try:
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
            
            itunes_url = f"https://itunes.apple.com/search?term={urllib.parse.quote(search_query)}&entity=song&limit=1"
            it_res = requests.get(itunes_url, timeout=5)
            if it_res.status_code == 200:
                results = it_res.json().get("results", [])
                if results:
                    return results[0].get("trackViewUrl")
    except Exception as e:
        logger.error(f"⚠️ Error Spotify to Apple: {e}")
    return None

# ============================================================
# دستورات ربات (شامل سیستم لاگین درون‌برنامه‌ای)
# ============================================================
@bot_app.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    global ADMIN_ID
    if not ADMIN_ID:
        ADMIN_ID = message.from_user.id

    text = (
        f"سلام **{message.from_user.first_name}** عزیز 👋\n\n"
        "🎵 **ربات دانلود مستقیم کیفیت استودیویی (Lossless / ALAC)**\n\n"
        "لینک **اسپاتیفای** یا **اپل موزیک** را ارسال کنید.\n\n"
    )
    if not user_app:
        text += "⚠️ **هشدار:** اکانت واسط هنوز فعال نشده است. برای فعال‌سازی دستور /login را بزنید."
    await message.reply_text(text)

# سیستم ساخت SESSION_STRING مستقیماً درون تلگرام
@bot_app.on_message(filters.command("login") & filters.private)
async def login_command(client: Client, message: Message):
    user_id = message.from_user.id
    user_login_states[user_id] = {"step": "phone", "client": None}
    await message.reply_text("📱 لطفاً **شماره تلفن** اکانت تلگرام واسط را با کد کشور بفرستید:\n\nمثال: `+989123456789`")

@bot_app.on_message(filters.text & filters.private)
async def handle_all_messages(client: Client, message: Message):
    user_id = message.from_user.id
    text = message.text.strip()

    # ۱. فرآیند لاگین تلگرامی
    if user_id in user_login_states:
        state = user_login_states[user_id]
        
        # گام دریافت شماره تلفن
        if state["step"] == "phone":
            msg = await message.reply_text("⏳ در حال ارسال کد تأیید به تلگرام شما...")
            try:
                temp_client = Client(f"temp_{user_id}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
                await temp_client.connect()
                code_info = await temp_client.send_code(text)
                
                state["client"] = temp_client
                state["phone"] = text
                state["phone_code_hash"] = code_info.phone_code_hash
                state["step"] = "code"
                
                await msg.edit_text("✅ کد ۵ رقمی تلگرام برای شما ارسال شد.\nلطفاً کد را بفرستید (بین اعداد فاصله بگذارید، مثلاً: `1 2 3 4 5`)")
            except Exception as e:
                await msg.edit_text(f"❌ خطا در ارسال شماره: {e}\nلطفاً دوباره /login بزنید.")
                user_login_states.pop(user_id, None)
            return

        # گام دریافت کد ۵ رقمی
        elif state["step"] == "code":
            clean_code = text.replace(" ", "").replace("-", "")
            temp_client = state["client"]
            msg = await message.reply_text("⏳ در حال بررسی کد...")
            try:
                await temp_client.sign_in(
                    phone_number=state["phone"],
                    phone_code_hash=state["phone_code_hash"],
                    phone_code=clean_code
                )
                
                # لاگین موفق - تولید Session String
                string_session = await temp_client.export_session_string()
                await msg.edit_text(
                    "🎉 **لاگین با موفقیت انجام شد!**\n\n"
                    "کد زیر همان `SESSION_STRING` شماست. آن را کپی کنید و در متغیرهای محیطی Render قرار دهید:\n\n"
                    f"`{string_session}`"
                )
                await temp_client.disconnect()
                user_login_states.pop(user_id, None)
            except SessionPasswordNeeded:
                state["step"] = "password"
                await msg.edit_text("🔐 این اکانت تایید دو مرحله‌ای (Two-Step Verification) دارد.\nلطفاً رمز عبور خود را وارد کنید:")
            except Exception as e:
                await msg.edit_text(f"❌ کد اشتباه است یا خطایی رخ داد: {e}\nلطفاً دوباره /login بزنید.")
                user_login_states.pop(user_id, None)
            return

        # گام تایید دو مرحله‌ای
        elif state["step"] == "password":
            temp_client = state["client"]
            msg = await message.reply_text("⏳ در حال تایید رمز عبور...")
            try:
                await temp_client.check_password(text)
                string_session = await temp_client.export_session_string()
                await msg.edit_text(
                    "🎉 **لاگین با موفقیت انجام شد!**\n\n"
                    "کد زیر همان `SESSION_STRING` شماست. آن را کپی کنید و در بخش Environment متغیر `SESSION_STRING` بگذارید:\n\n"
                    f"`{string_session}`"
                )
                await temp_client.disconnect()
                user_login_states.pop(user_id, None)
            except Exception as e:
                await msg.edit_text(f"❌ رمز عبور اشتباه است: {e}\nلطفاً دوباره /login بزنید.")
                user_login_states.pop(user_id, None)
            return

    # ۲. پردازش لینک‌های موزیک
    if not user_app:
        await message.reply_text("❌ اکانت واسط فعال نیست. ابتدا دستور /login را بزنید و Session دریافت شده را در Render بگذارید.")
        return

    apple_url = None
    if "music.apple.com" in text:
        apple_url = text
    elif "spotify.com" in text:
        status_msg = await message.reply_text("🔎 **در حال تبدیل لینک اسپاتیفای به اپل موزیک...**")
        apple_url = spotify_to_apple_music(text)
        if not apple_url:
            await status_msg.edit_text("❌ این اثر در اپل موزیک یافت نشد.")
            return
        await status_msg.delete()
        
    if apple_url:
        status = await message.reply_text("🚀 **در حال استخراج کیفیت اورجینال ALAC/Lossless...**")
        try:
            sent_msg = await user_app.send_message(TARGET_BOT, apple_url)
            pending_requests[sent_msg.id] = {
                "user_chat_id": message.chat.id,
                "status_msg_id": status.id
            }
        except Exception as e:
            await status.edit_text(f"❌ خطای ارتباط با ربات هدف: {e}")

# ============================================================
# استارت برنامه‌ها
# ============================================================
async def main():
    await bot_app.start()
    if user_app:
        await user_app.start()
        logger.info("✅ اکانت واسط UserBot فعال است.")
    logger.info("🚀 ربات با موفقیت روشن شد!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

