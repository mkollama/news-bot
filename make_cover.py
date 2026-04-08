import sys
import os
import json
from pathlib import Path
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
OUTPUT_DIR = Path("output_videos")
OUTPUT_DIR.mkdir(exist_ok=True)

def send_photo(photo_path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    with open(photo_path, "rb") as f:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption}, files={"photo": f}, timeout=30)

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=10)

if __name__ == "__main__":
    from cover_maker import create_cover

    if len(sys.argv) < 2:
        send_message("Kullanim hatasi!")
        sys.exit(1)

    data = json.loads(sys.argv[1])
    hook_title = data.get("hook_title", "")
    analysis = data.get("analysis", {})

    if not hook_title:
        send_message("Baslik bulunamadi!")
        sys.exit(1)

    cover_path = OUTPUT_DIR / "cover_retry.jpg"
    result = create_cover(hook_title, analysis, cover_path)

    if result and cover_path.exists():
        send_photo(cover_path, f"Kapak fotografi\n{hook_title}\n\nYouTube'da manuel yukle!")
        os.remove(cover_path)
    else:
        send_message("Kapak olusturulamadi!")
