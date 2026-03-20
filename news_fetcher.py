import feedparser
import anthropic
import requests
import json
import os
import time
from datetime import datetime

# === AYARLAR ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Haber kaynakları (ABD siyaseti odaklı)
RSS_FEEDS = [
    "https://feeds.feedburner.com/politico/politics",
    "https://rss.cnn.com/rss/cnn_allpolitics.rss",
    "https://feeds.npr.org/1014/rss.xml",
    "https://www.politico.com/rss/politicopicks.xml",
    "https://thehill.com/rss/syndicator/19109",
]

PENDING_FILE = "pending_news.json"

def fetch_news():
    """RSS'ten haberleri çek"""
    articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                articles.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", "")[:300],
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "source": feed.feed.get("title", url)
                })
        except Exception as e:
            print(f"RSS hatası {url}: {e}")
    return articles

def filter_with_claude(articles):
    """Claude ile en ilginç haberleri filtrele"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    articles_text = "\n\n".join([
        f"ID: {i}\nBAŞLIK: {a['title']}\nÖZET: {a['summary']}\nKAYNAK: {a['source']}"
        for i, a in enumerate(articles)
    ])
    
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"""Sen bir YouTube haber kanalı editörüsün. ABD siyaseti, Trump, Kongre, mahkeme davaları konularında video yapıyoruz.

Aşağıdaki haberlerden YouTube videosu için EN İLGİNÇ ve EN ÇOK İZLENECEK 3-5 tanesini seç.

Kriterler:
- Trump, Beyaz Saray, Kongre, önemli davalar öncelikli
- İzleyiciyi çekecek, tartışmalı veya ilginç konular
- Yeterli içerik üretilebilecek konular (10-15 dk video)

Haberleri JSON formatında döndür:
{{"selected": [0, 2, 4]}}  (sadece ID numaraları)

HABERLER:
{articles_text}

Sadece JSON döndür, başka bir şey yazma."""
        }]
    )
    
    try:
        result = json.loads(response.content[0].text.strip())
        selected_ids = result.get("selected", [])
        return [articles[i] for i in selected_ids if i < len(articles)]
    except:
        return articles[:5]

def send_telegram_menu(selected_articles):
    """Telegram'a haber listesi gönder"""
    if not selected_articles:
        return
    
    # Haberleri kaydet
    with open(PENDING_FILE, "w") as f:
        json.dump(selected_articles, f, ensure_ascii=False, indent=2)
    
    message = "📰 *YENİ HABERLER* 📰\n\n"
    message += "Video yapmak istediğin haberi seç:\n\n"
    
    for i, article in enumerate(selected_articles):
        message += f"*{i+1}.* {article['title']}\n"
        message += f"📍 {article['source']}\n\n"
    
    message += "━━━━━━━━━━━━━━━\n"
    message += "Yanıtlamak için numarayı yaz (örn: *1*)\n"
    message += "Hiçbirini istemiyorsan *0* yaz"
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    })
    
    print(f"✅ {len(selected_articles)} haber Telegram'a gönderildi")

def main():
    print(f"[{datetime.now()}] Haber tarama başlıyor...")
    
    articles = fetch_news()
    print(f"✅ {len(articles)} haber bulundu")
    
    selected = filter_with_claude(articles)
    print(f"✅ Claude {len(selected)} haber seçti")
    
    send_telegram_menu(selected)
    print("✅ Tamamlandı!")

if __name__ == "__main__":
    main()
