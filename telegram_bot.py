import requests
import json
import os
import time
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
PENDING_FILE = "pending_news.json"
LAST_UPDATE_FILE = "last_update_id.txt"

def get_last_update_id():
    try:
        with open(LAST_UPDATE_FILE) as f:
            return int(f.read().strip())
    except:
        return 0

def save_last_update_id(update_id):
    with open(LAST_UPDATE_FILE, "w") as f:
        f.write(str(update_id))

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    })

def get_updates():
    last_id = get_last_update_id()
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    resp = requests.get(url, params={"offset": last_id + 1, "timeout": 30})
    return resp.json().get("result", [])

def load_pending_news():
    try:
        with open(PENDING_FILE) as f:
            return json.load(f)
    except:
        return []

def trigger_news_fetch():
    send_message("🔍 Haberler taranıyor, biraz bekle...")
    try:
        from news_fetcher import fetch_news, filter_with_claude, send_telegram_menu
        articles = fetch_news()
        selected = filter_with_claude(articles)
        send_telegram_menu(selected)
    except Exception as e:
        send_message(f"❌ Hata: {str(e)}")

def trigger_video_pipeline(article):
    send_message(f"✅ Anladım! Şu haber için video yapılıyor:\n\n*{article['title']}*\n\n⏳ Pipeline başlıyor...")
    import threading
    import video_pipeline
    thread = threading.Thread(target=video_pipeline.run, args=(article,), daemon=True)
    thread.start()

def process_message(text, articles):
    text = text.strip()

    if text.lower() in ["/haber", "haber", "/start"]:
        trigger_news_fetch()
        return

    if text.lower() == "/yardim":
        send_message(
            "🤖 *Komutlar:*\n\n"
            "/haber → Haberleri şimdi tara\n"
            "/yardim → Bu menüyü göster\n\n"
            "Haber listesi gelince numara yaz (1, 2, 3...)\n"
            "Hi
