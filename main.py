import threading
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
    import schedule
    import time
    from news_fetcher import fetch_news, filter_with_claude, send_telegram_menu
    from datetime import datetime

    def job():
        print(f"[{datetime.now()}] Haber tarama başlıyor...")
        articles = fetch_news()
        selected = filter_with_claude(articles)
        send_telegram_menu(selected)

    schedule.every().day.at("06:00").do(job)
    schedule.every().day.at("14:00").do(job)
    schedule.every().day.at("22:00").do(job)

    print("📅 Scheduler başladı!")
    while True:
        schedule.run_pending()
        time.sleep(60)

def run_telegram_bot():
    from telegram_bot import main
    main()

def main():
    print(f"[{datetime.now()}] 🚀 News Bot başlıyor...")
    send_telegram("🤖 *News Bot aktif!*\n\n/haber yazarak haberleri tarayabilirsin.")

    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)

    scheduler_thread.start()
    bot_thread.start()

    print("✅ Scheduler ve Telegram bot çalışıyor!")

    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
