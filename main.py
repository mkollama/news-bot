import threading
import subprocess
import time
import os
import requests
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        })
    except:
        pass

def run_scheduler():
    subprocess.run(["python", "scheduler.py"])

def run_telegram_bot():
    subprocess.run(["python", "telegram_bot.py"])

def main():
    print(f"[{datetime.now()}] 🚀 News Bot başlıyor...")
    
    send_telegram(
        "🤖 *News Bot aktif!*\n\n"
        "📅 Haberler günde 3 kez taranacak (06:00, 14:00, 22:00)\n"
        "📱 Yeni haberler geldiğinde buraya bildirim alacaksın\n\n"
        "Hazır! 🎬"
    )
    
    # İki servisi paralel çalıştır
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    
    scheduler_thread.start()
    bot_thread.start()
    
    print("✅ Scheduler ve Telegram bot çalışıyor!")
    
    # Ana thread canlı tut
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
