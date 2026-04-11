import feedparser
import anthropic
import requests
import json
import os
import time
import email.utils
from datetime import datetime, timezone, timedelta

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

PENDING_FILE = "pending_news.json"

RSS_FEEDS = [
    "https://feeds.feedburner.com/politico/politics",
    "https://rss.cnn.com/rss/cnn_allpolitics.rss",
    "https://feeds.npr.org/1014/rss.xml",
    "https://thehill.com/rss/syndicator/19109",
    "https://www.politico.com/rss/politicopicks.xml",
    "https://feeds.washingtonpost.com/rss/politics",
    "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
]

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

def is_recent(published_str, max_days=3):
    """Haberin son max_days gun icinde yayinlanip yayinlanmadigini kontrol et"""
    if not published_str:
        return True  # tarih yoksa gecir
    try:
        dt = email.utils.parsedate_to_datetime(published_str)
        diff = datetime.now(timezone.utc) - dt
        return diff.days <= max_days
    except:
        try:
            # Alternatif format dene
            from dateutil import parser as dateparser
            dt = dateparser.parse(published_str)
            if dt and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            diff = datetime.now(timezone.utc) - dt
            return diff.days <= max_days
        except:
            return True

def fetch_rss_news():
    articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                published = entry.get("published", "")
                # Eski haberleri filtrele
                if not is_recent(published, max_days=3):
                    continue
                articles.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", "")[:300],
                    "link": entry.get("link", ""),
                    "published": published,
                    "source": feed.feed.get("title", url),
                    "type": "rss"
                })
        except Exception as e:
            print(f"RSS hatasi {url}: {e}")
    print(f"RSS: {len(articles)} guncel haber bulundu")
    return articles

def fetch_google_trends():
    """Google Trends USA - guncel trendler"""
    try:
        url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:15]:
            title = entry.get("title", "")
            summary = entry.get("summary", "")[:300]
            # Sadece siyasi icerik
            if any(kw in (title + summary).lower() for kw in [
                "trump", "congress", "senate", "white house", "president",
                "election", "republican", "democrat", "political", "washington",
                "court", "supreme", "law", "bill", "vote", "war", "iran",
                "military", "crisis", "protest", "impeach", "scandal"
            ]):
                articles.append({
                    "title": title,
                    "summary": summary,
                    "link": entry.get("link", ""),
                    "published": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
                    "source": "Google Trends US",
                    "type": "trend"
                })
        print(f"Google Trends: {len(articles)} siyasi trend bulundu")
        return articles
    except Exception as e:
        print(f"Google Trends hatasi: {e}")
        return []

def fetch_reddit_politics():
    """Reddit r/politics - son 24 saatte viral olan haberler"""
    try:
        headers = {"User-Agent": "NewsBot/1.0"}
        response = requests.get(
            "https://www.reddit.com/r/politics/hot.json?limit=20",
            headers=headers, timeout=10
        )
        if response.status_code != 200:
            return []
        
        posts = response.json()["data"]["children"]
        articles = []
        for post in posts:
            data = post["data"]
            # Son 24 saat icinde olan postlar
            created = data.get("created_utc", 0)
            post_time = datetime.fromtimestamp(created, tz=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - post_time).total_seconds() / 3600
            
            if age_hours > 48:  # 48 saatten eski postlari atla
                continue
                
            if data.get("score", 0) > 500:
                articles.append({
                    "title": data.get("title", ""),
                    "summary": data.get("selftext", "")[:300] or data.get("title", ""),
                    "link": f"https://reddit.com{data.get('permalink', '')}",
                    "published": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
                    "source": f"Reddit r/politics ({data.get('score', 0):,} upvotes)",
                    "type": "reddit",
                    "score": data.get("score", 0)
                })
        print(f"Reddit: {len(articles)} guncel post bulundu")
        return articles
    except Exception as e:
        print(f"Reddit hatasi: {e}")
        return []

def fetch_breaking_news():
    """Breaking news RSS - en son haberler"""
    breaking_feeds = [
        "https://feeds.bbci.co.uk/news/politics/rss.xml",
        "https://abcnews.go.com/abcnews/politicsheadlines",
        "https://feeds.foxnews.com/foxnews/politics",
    ]
    articles = []
    for url in breaking_feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                published = entry.get("published", "")
                if not is_recent(published, max_days=2):
                    continue
                articles.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", "")[:300],
                    "link": entry.get("link", ""),
                    "published": published,
                    "source": feed.feed.get("title", url),
                    "type": "breaking"
                })
        except Exception as e:
            print(f"Breaking news hatasi {url}: {e}")
    print(f"Breaking news: {len(articles)} haber bulundu")
    return articles

def fetch_news():
    rss = fetch_rss_news()
    trends = fetch_google_trends()
    reddit = fetch_reddit_politics()
    breaking = fetch_breaking_news()
    
    all_articles = rss + trends + reddit + breaking
    
    # Duplicate baslik temizle
    seen_titles = set()
    unique_articles = []
    for a in all_articles:
        title_key = a["title"][:50].lower()
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_articles.append(a)
    
    print(f"Toplam: {len(unique_articles)} guncel benzersiz haber")
    return unique_articles

def filter_with_claude(articles):
    if not articles:
        send_message("Hic guncel haber bulunamadi!")
        return []

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    today = datetime.now().strftime("%B %d, %Y")

    articles_text = "\n\n".join([
        f"ID: {i}\nKAYNAK: {a['source']} ({a.get('type','rss').upper()})\nBAŞLIK: {a['title']}\nÖZET: {a['summary']}"
        for i, a in enumerate(articles)
    ])

    for attempt in range(5):
        try:
            response = client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": f"""Sen bir YouTube politik drama kanalı editörüsün.
Bugun: {today}

KURAL 1 - GUNCELLIK: Sadece guncel haberleri sec. Eski haberler, secimler veya artik bitmis davalar kesinlikle dahil edilmemeli.
KURAL 2 - DRAMA: Sadece DRAMA, KRİZ, ÇATIŞMA, ŞOK, SKANDAL iceren haberleri sec.

YouTube haber sevmez, DRAMA sever!

İyi haber kriterleri:
✅ Birisi birini suçluyor / saldırıyor
✅ Beklenmedik olay / karar / gelisme
✅ Tartisma / kavga / kriz var
✅ Izleyici "ne oluyor?!" diyecek
✅ Gercek insan reaksiyonu var (sinirli, saskın, kizgın)
✅ Trump, Kongre, Mahkeme, Skandal, Savas iceriyor

❌ Eski haberler (secim kampanyasi, bitmis davalar vs)
❌ Duz haber (X toplanti yapti)
❌ Drama yok, kriz yok
❌ Aylarca once olan olaylar

Asagidan EN DRAMATIK ve EN GUNCEL 3-5 haberi sec:

{articles_text}

JSON formatinda don:
{{"selected": [0, 2, 4]}}

Sadece JSON don, baska bir sey yazma."""
                }]
            )
            result = json.loads(response.content[0].text.strip())
            selected_ids = result.get("selected", [])
            return [articles[i] for i in selected_ids if i < len(articles)]
        except Exception as e:
            if "overloaded" in str(e).lower() and attempt < 4:
                wait = (attempt + 1) * 30
                print(f"API overloaded, {wait}s bekleniyor...")
                time.sleep(wait)
            else:
                print(f"Claude hatasi: {e}")
                return articles[:5]
    return articles[:5]

def send_telegram_menu(selected_articles):
    if not selected_articles:
        send_message("Uygun guncel haber bulunamadi, tekrar dene.")
        return

    with open(PENDING_FILE, "w") as f:
        json.dump(selected_articles, f, ensure_ascii=False, indent=2)

    message = "🔥 *GUNCEL DRAMA HABERLERİ* 🔥\n\n"

    for i, article in enumerate(selected_articles):
        source_type = article.get("type", "rss")
        emoji = "🔥" if source_type == "reddit" else "📈" if source_type == "trend" else "⚡" if source_type == "breaking" else "📰"
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

def main():
    print(f"[{datetime.now()}] Haber tarama basliyor...")
    articles = fetch_news()
    selected = filter_with_claude(articles)
    send_telegram_menu(selected)
    print("Tamamlandi!")

if __name__ == "__main__":
    main()
