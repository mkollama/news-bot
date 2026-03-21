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
            "Hiçbirini istemiyorsan *0* yaz"
        )
        return

    if text == "0":
        send_message("👍 Tamam, bu haberleri geçtik. /haber yazarak yeni tarama başlatabilirsin.")
        try:
            os.remove(PENDING_FILE)
        except:
            pass
        return

    if articles:
        try:
            choice = int(text)
            if 1 <= choice <= len(articles):
                selected = articles[choice - 1]
                trigger_video_pipeline(selected)
            else:
                send_message(f"❌ Lütfen 1-{len(articles)} arasında bir sayı yaz.")
        except ValueError:
            send_message("❓ Anlamadım.\n\n/haber → Haber tara\n/yardim → Yardım")
    else:
        send_message("📭 Bekleyen haber yok. /haber yazarak tarama başlatabilirsin.")

def main():
    print(f"[{datetime.now()}] Telegram bot dinleniyor...")
    send_message("🤖 Bot aktif! /haber yazarak haberleri tarayabilirsin.")

    while True:
        try:
            updates = get_updates()
            for update in updates:
                update_id = update["update_id"]
                save_last_update_id(update_id)
                if "message" not in update:
                    continue
                chat_id = str(update["message"]["chat"]["id"])
                if chat_id != str(TELEGRAM_CHAT_ID):
                    continue
                text = update["message"].get("text", "")
                if not text:
                    continue
                print(f"[{datetime.now()}] Mesaj: {text}")
                articles = load_pending_news()
                process_message(text, articles)
            time.sleep(2)
        except Exception as e:
            print(f"Hata: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
