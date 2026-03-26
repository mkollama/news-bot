import feedparser
import anthropic
import requests
import json
import os
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Haber kaynaklari
RSS_FEEDS = [
    "https://feeds.feedburner.com/politico/politics",
    "https://rss.cnn.com/rss/cnn_allpolitics.rss",
    "https://feeds.npr.org/1014/rss.xml",
    "https://thehill.com/rss/syndicator/19109",
    "https://www.politico.com/rss/politicopicks.xml",
]

PENDING_FILE = "pending_news.json"

def fetch_rss_news():
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
                    "source": feed.feed.get("title", url),
                    "type": "rss"
                })
        except Exception as e:
            print(f"RSS hatasi {url}: {e}")
    return articles

def fetch_google_trends():
    try:
        url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:10]:
            title = entry.get("title", "")
            summary = entry.get("summary", "")[:300]
            if any(kw in (title + summary).lower() for kw in [
                "trump", "congress", "senate", "white house", "president",
                "election", "republican", "democrat", "political", "washington",
                "court", "supreme", "biden", "harris", "law", "bill", "vote"
            ]):
                articles.append({
                    "title": title,
                    "summary": summary,
                    "link": entry.get("link", ""),
                    "published": "",
                    "source": "Google Trends US",
                    "type": "trend"
                })
        return articles
    except Exception as e:
        print(f"Google Trends hatasi: {e}")
        return []

def fetch_reddit_politics():
    try:
        headers = {"User-Agent": "NewsBot/1.0"}
        response = requests.get(
            "https://www.reddit.com/r/politics/hot.json?limit=15",
            headers=headers,
            timeout=10
        )
        if response.status_code != 200:
            return []
        
        posts = response.json()["data"]["children"]
        articles = []
        for post in posts:
            data = post["data"]
            if data.get("score", 0) > 1000:
                articles.append({
                    "title": data.get("title", ""),
                    "summary": data.get("selftext", "")[:300] or data.get("title", ""),
                    "link": f"https://reddit.com{data.get('permalink', '')}",
                    "published": "",
                    "source": f"Reddit r/politics ({data.get('score', 0):,} upvotes)",
                    "type": "reddit",
                    "score": data.get("score", 0)
                })
        return articles
    except Exception as e:
        print(f"Reddit hatasi: {e}")
        return []

def fetch_news():
    rss = fetch_rss_news()
    trends = fetch_google_trends()
    reddit = fetch_reddit_politics()
    
    all_articles = rss + trends + reddit
    print(f"Toplam: {len(rss)} RSS + {len(trends)} Trend + {len(reddit)} Reddit = {len(all_articles)} haber")
    return all_articles

def filter_with_claude(articles):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    articles_text = "\n\n".join([
        f"ID: {i}\nKAYNAK: {a['source']} ({a.get('type','rss').upper()})\nBAŞLIK: {a['title']}\nÖZET: {a['summary']}"
        for i, a in enumerate(articles)
    ])
    
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"""Sen bir YouTube haber kanali editorusun. ABD siyaseti, Trump, Kongre, mahkeme davalari konularinda video yapiyoruz.

Asagidaki haberlerden YouTube videosu icin EN ILGINC ve EN COK IZLENECEK 3-5 tanesini sec.

ONCELIKLER:
- Reddit'te cok upvote alan haberler (viral potansiyeli yuksek)
- Google Trends'de olan haberler (su an gundem)
- Trump, Beyaz Saray, Kongre, onemli davalar
- Izleyiciyi cekecek, tartismali veya sasirtici konular
- 6-10 dk video icin yeterli icerik olan konular

Secilen haberlerin JSON formatinda don:
{{"selected": [0, 2, 4]}}

HABERLER:
{articles_text}

Sadece JSON don, baska bir sey yazma."""
        }]
    )
    
    try:
        result = json.loads(response.content[0].text.strip())
        selected_ids = result.get("selected", [])
        return [articles[i] for i in selected_ids if i < len(articles)]
    except:
        return articles[:5]

def send_telegram_menu(selected_articles):
    if not selected_articles:
        send_message("Haber bulunamadi, tekrar dene.")
        return
    
    with open(PENDING_FILE, "w") as f:
        json.dump(selected_articles, f, ensure_ascii=False, indent=2)
    
    message = "📰 *GUNCEL HABERLER* 📰\n\n"
    
    for i, article in enumerate(selected_articles):
        source_type = article.get("type", "rss")
        emoji = "🔥" if source_type == "reddit" else "📈" if source_type == "trend" else "📰"
        score = f" ({article.get('score', 0):,} upvote)" if source_type == "reddit" else ""
        
        message += f"{emoji} *{i+1}.* {article['title']}\n"
        message += f"📍 {article['source']}{score}\n\n"
    
    message += "━━━━━━━━━━━━━━━\n"
    message += "Numara yaz (1-5) veya 0 ile gec\n"
    message += "/yardim → Komutlar"
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    })
    
    print(f"{len(selected_articles)} haber Telegram'a gonderildi")

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    })

def main():
    print(f"[{datetime.now()}] Haber tarama basliyor...")
    articles = fetch_news()
    selected = filter_with_claude(articles)
    send_telegram_menu(selected)
    print("Tamamlandi!")

if __name__ == "__main__":
    main()
