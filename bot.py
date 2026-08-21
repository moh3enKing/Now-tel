import re
import os
import time
import requests
import traceback
import urllib.parse
import threading
from flask import Flask

# --------------------------------------------------
# توکن ربات تلگرام شما
# --------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8135900333:AAH2MTWecY7q3le28GZPppbJhnVwq276xfY")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"

# --------------------------------------------------
# وب‌سرور Flask جهت پشتیبانی از Web Service رایگان Render
# --------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Spotify Bot Test 3 (Multi-Engine + Debugger) is online!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --------------------------------------------------
# توابع ارسال پیام و دیباگ به تلگرام
# --------------------------------------------------
def send_message(chat_id, text, parse_mode="Markdown"):
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return requests.post(BASE_URL + "sendMessage", json=payload).json()

def send_debug(chat_id, debug_title, debug_info):
    """ارسال جزئیات فنی و خطایابی به کاربر"""
    msg = f"🐛 **[DEBUG LOG]**\n📌 **مرحله:** {debug_title}\n

