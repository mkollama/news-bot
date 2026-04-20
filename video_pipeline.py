import anthropic
import requests
import subprocess
import os
import json
from datetime import datetime
from pathlib import Path

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
OUTPUT_DIR = Path("output_videos")
OUTPUT_DIR.mkdir(exist_ok=True)

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

def send_telegram_photo_file(photo_path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    try:
        with open(photo_path, "rb") as f:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption}, files={"photo": f}, timeout=30)
    except:
        pass

def detect_people_and_topics(article):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=800,
        messages=[{"role": "user", "content": f"""Analyze this news article. Return ONLY valid JSON.

Title: {article['title']}
Summary: {article['summary']}

video_search_queries rules:
- Exactly 5 queries, max 3-4 words each
- ALWAYS use the main person's LAST NAME in every query
- Focus on: speech, statement, hearing, press conference, reaction, interview
- Queries must be short and specific for YouTube search
- If main_person is "Eric Swalwell" -> use "Swalwell" in every query
- If main_person is "Donald Trump" -> use "Trump" in every query

Return exactly:
{{
  "people": ["Person Name 1", "Person Name 2"],
  "main_person": "Most important person causing drama or conflict",
  "drama_type": "brief description of the conflict/drama",
  "video_search_queries": [
    "LastName keyword1 keyword2",
    "LastName keyword3 keyword4",
    "LastName press conference",
    "LastName statement reaction",
    "LastName news hearing"
  ],
  "pexels_query": "fallback stock footage query"
}}"""}]
    )
    try:
        result = json.loads(response.content[0].text.strip())
        result["article_title"] = article["title"]
        return result
    except:
        return {
            "people": [],
            "main_person": "",
            "drama_type": "",
            "article_title": article["title"],
            "video_search_queries": ["US politics breaking news", "Congress hearing", "White House press conference", "Senate vote", "political drama"],
            "pexels_query": "Washington DC politics"
        }

def generate_hook_title(article):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=200,
        messages=[{"role": "user", "content": f"""Create a YouTube hook title for this political drama. Return ONLY the title.

Rules:
- Max 65 characters
- Must create IMMEDIATE curiosity or shock
- Use: CAUGHT, EXPOSED, ERUPTS, DESTROYS, NOBODY EXPECTED, JUST IN, BREAKING
- Focus on DRAMA and CONFLICT
- Make viewer think "I NEED to see this"
- Stay factual

Good examples:
"Trump ERUPTS After Congress Makes Midnight Move"
"CAUGHT: Senator's Shocking Secret Vote Exposed"
"NOBODY Expected This — Washington in Chaos"
"He Said WHAT?! Senate EXPLODES Over New Bill"

Article: {article['title']}
Summary: {article['summary']}

Hook title:"""}]
    )
    return response.content[0].text.strip().strip('"')

def get_wikipedia_photo(person_name):
    try:
        params = {
            "action": "query",
            "titles": person_name,
            "prop": "pageimages",
            "format": "json",
            "pithumbsize": 1000
        }
        response = requests.get("https://en.wikipedia.org/w/api.php", params=params, timeout=10)
        pages = response.json().get("query", {}).get("pages", {})
        for page in pages.values():
            thumb = page.get("thumbnail", {})
            if thumb:
                return thumb.get("source")
    except:
        pass
    return None

def search_youtube_for_video(query, max_results=3, recent=False):
    """YouTube'da video ara - recent=True ise son 24 saat"""
    try:
        sp = "EgIYAQ%3D%3D" if recent else "EgIQAQ%3D%3D"  # 24 saat veya bu ay
        result = subprocess.run([
            "yt-dlp",
            "--no-download",
            "--print", "%(id)s\t%(title)s\t%(thumbnail)s\t%(duration)s",
            "--playlist-end", str(max_results),
            "--match-filter", "duration < 3600",
            f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}&sp={sp}"
        ], capture_output=True, text=True, timeout=60)

        videos = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                video_id = parts[0].strip()
                title = parts[1].strip()
                thumbnail = parts[2].strip()
                if video_id and len(video_id) == 11:
                    videos.append({
                        "id": video_id,
                        "title": title,
                        "thumbnail": thumbnail,
                        "url": f"https://www.youtube.com/watch?v={video_id}"
                    })
        return videos
    except Exception as e:
        print(f"YouTube arama hatasi ({query}): {e}")
        return []

def search_cspan_youtube(query):
    try:
        result = subprocess.run([
            "yt-dlp",
            "--no-download",
            "--print", "%(id)s\t%(title)s\t%(thumbnail)s",
            "--playlist-end", "3",
            f"https://www.youtube.com/@CSPAN/search?query={query.replace(' ', '+')}"
        ], capture_output=True, text=True, timeout=45)

        videos = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 1:
                video_id = parts[0].strip()
                title = parts[1].strip() if len(parts) > 1 else ""
                thumbnail = parts[2].strip() if len(parts) > 2 else ""
                if video_id and len(video_id) == 11:
                    videos.append({
                        "id": video_id,
                        "title": title,
                        "thumbnail": thumbnail,
                        "url": f"https://www.youtube.com/watch?v={video_id}"
                    })
        return videos
    except Exception as e:
        print(f"C-SPAN arama hatasi: {e}")
        return []

def download_youtube_clip(youtube_url, start_seconds, duration_seconds, output_path):
    try:
        temp_path = OUTPUT_DIR / f"yt_temp_{os.path.basename(str(output_path))}.mp4"
        result = subprocess.run([
            "yt-dlp",
            "-f", "best[height<=720][ext=mp4]/best[height<=720]/best",
            "--no-playlist",
            "-o", str(temp_path),
            youtube_url
        ], capture_output=True, text=True, timeout=120)

        if result.returncode != 0 or not temp_path.exists():
            return None

        subprocess.run([
            "ffmpeg",
            "-ss", str(start_seconds),
            "-i", str(temp_path),
            "-t", str(duration_seconds),
            "-vf", "crop=in_w:in_h*0.88:0:0,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
            "-c:v", "libx264", "-c:a", "aac",
            str(output_path), "-y"
        ], check=True, capture_output=True)

        os.remove(temp_path)
        return output_path
    except Exception as e:
        print(f"YouTube klip hatasi: {e}")
        try:
            if Path(str(temp_path)).exists():
                os.remove(temp_path)
        except:
            pass
        return None

def download_file(url, output_path):
    response = requests.get(url, stream=True, timeout=30)
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return output_path

def download_thumbnail(url, output_path):
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(response.content)
            return output_path
    except:
        pass
    return None

def photo_to_video(photo_path, duration, output_path):
    subprocess.run([
        "ffmpeg", "-loop", "1", "-i", str(photo_path),
        "-c:v", "libx264", "-t", str(duration),
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
        "-r", "30", str(output_path), "-y"
    ], check=True, capture_output=True)

def get_clip_duration(path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ], capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return 8.0

def normalize_clip(input_path, output_path):
    subprocess.run([
        "ffmpeg", "-i", str(input_path),
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
        "-c:v", "libx264", "-r", "30", "-an",
        str(output_path), "-y"
    ], check=True, capture_output=True)

def fetch_pexels_photos(query, count=8):
    if not PEXELS_API_KEY:
        return []
    headers = {"Authorization": PEXELS_API_KEY}
    response = requests.get("https://api.pexels.com/v1/search", headers=headers,
        params={"query": query, "per_page": count})
    if response.status_code != 200:
        return []
    return [p["src"]["large"] for p in response.json().get("photos", [])]

def fetch_pexels_videos(query, count=3):
    if not PEXELS_API_KEY:
        return []
    headers = {"Authorization": PEXELS_API_KEY}
    response = requests.get("https://api.pexels.com/videos/search", headers=headers,
        params={"query": query, "per_page": count, "min_duration": 5})
    if response.status_code != 200:
        return []
    videos = response.json().get("videos", [])
    result = []
    for v in videos:
        files = v.get("video_files", [])
        hd = [f for f in files if f.get("quality") in ["hd", "sd"]]
        if hd:
            result.append(hd[0]["link"])
    return result

def build_final_video(video_clips, photo_clips, audio_path, audio_duration, output_path):
    all_clips = []

    if video_clips:
        norm_videos = []
        for i, clip in enumerate(video_clips):
            norm = OUTPUT_DIR / f"normv_{i}.mp4"
            try:
                normalize_clip(clip, norm)
                norm_videos.append(norm)
            except Exception as e:
                print(f"Video normalize hatasi: {e}")

        if norm_videos:
            video_section = OUTPUT_DIR / "video_section.mp4"
            list_file = OUTPUT_DIR / "video_list.txt"
            with open(list_file, "w") as f:
                for n in norm_videos:
                    f.write(f"file '{os.path.abspath(n)}'\n")
            subprocess.run([
                "ffmpeg", "-f", "concat", "-safe", "0", "-i", str(list_file),
                "-c:v", "libx264", "-t", "180", "-an",
                str(video_section), "-y"
            ], check=True, capture_output=True)
            for n in norm_videos:
                try: os.remove(n)
                except: pass
            all_clips.append(video_section)

    photo_duration = max(audio_duration - 180, 30)
    if photo_clips:
        norm_photos = []
        for i, clip in enumerate(photo_clips):
            norm = OUTPUT_DIR / f"normp_{i}.mp4"
            try:
                normalize_clip(clip, norm)
                norm_photos.append(norm)
            except:
                pass

        if norm_photos:
            total = 0.0
            loop = []
            while total < photo_duration:
                for p in norm_photos:
                    d = get_clip_duration(p)
                    loop.append(p)
                    total += d
                    if total >= photo_duration:
                        break

            list_file2 = OUTPUT_DIR / "photo_list.txt"
            with open(list_file2, "w") as f:
                for p in loop:
                    f.write(f"file '{os.path.abspath(p)}'\n")

            photo_section = OUTPUT_DIR / "photo_section.mp4"
            subprocess.run([
                "ffmpeg", "-f", "concat", "-safe", "0", "-i", str(list_file2),
                "-c:v", "libx264", "-t", str(photo_duration), "-an",
                str(photo_section), "-y"
            ], check=True, capture_output=True)
            all_clips.append(photo_section)

            for n in norm_photos:
                try: os.remove(n)
                except: pass

    if not all_clips:
        fallback = OUTPUT_DIR / "fallback.mp4"
        subprocess.run([
            "ffmpeg", "-f", "lavfi", "-i", "color=c=black:size=1920x1080:rate=30",
            "-t", str(audio_duration), "-c:v", "libx264",
            str(fallback), "-y"
        ], check=True, capture_output=True)
        all_clips.append(fallback)

    final_list = OUTPUT_DIR / "final_list.txt"
    with open(final_list, "w") as f:
        for c in all_clips:
            f.write(f"file '{os.path.abspath(c)}'\n")

    combined = OUTPUT_DIR / "combined.mp4"
    subprocess.run([
        "ffmpeg", "-f", "concat", "-safe", "0", "-i", str(final_list),
        "-c:v", "libx264", "-t", str(audio_duration),
        str(combined), "-y"
    ], check=True, capture_output=True)

    subprocess.run([
        "ffmpeg", "-i", str(combined), "-i", str(audio_path),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        str(output_path), "-y"
    ], check=True, capture_output=True)

    for c in all_clips:
        try: os.remove(c)
        except: pass

def get_thumbnail_text_score(image_path):
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return len(text.split())
    except:
        return 999

def create_cover_image(thumbnail_path, hook_title, output_path):
    """
    Kapak formati:
    - Fotograf tam dolu (1280x720)
    - Altta kalin kirmizi serit + beyaz bold yazi
    - Etrafinda kirmizi cerceve (8px)
    - Yazi kisa ve dramatik - subtitle tarzi
    """
    try:
        safe_title = (hook_title
            .replace("'", "")
            .replace(":", " -")
            .replace('"', '')
            .replace("\\", "")
            .replace("/", " ")
            .replace("%", "percent")
            .upper()  # Buyuk harf - daha dramatik
        )

        # Font boyutunu dinamik hesapla - tum genislige sigdir
        char_count = len(safe_title)
        font_size = 52
        while font_size > 20:
            if char_count * font_size * 0.55 <= 1180:
                break
            font_size -= 2

        strip_height = font_size + 30
        strip_y = 720 - strip_height

        vf = (
            "scale=1280:720:force_original_aspect_ratio=decrease,"
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,"
            # Kirmizi alt serit
            f"drawbox=x=0:y={strip_y}:w=1280:h={strip_height}:color=0xFF0000@0.93:t=fill,"
            # Beyaz bold yazi
            f"drawtext=text='{safe_title}':"
            "fontcolor=white:"
            f"fontsize={font_size}:"
            "x=(w-text_w)/2:"
            f"y={strip_y + 14}:"
            "font=DejaVuSans-Bold,"
            # Kirmizi cerceve etrafta
            "drawbox=x=0:y=0:w=1280:h=720:color=0xFF0000@0.95:t=8"
        )

        result = subprocess.run([
            "ffmpeg", "-i", str(thumbnail_path),
            "-vf", vf,
            "-frames:v", "1", "-update", "1",
            str(output_path), "-y"
        ], capture_output=True)

        if result.returncode == 0:
            return output_path
        else:
            print(f"Kapak ffmpeg hatasi: {result.stderr.decode()[-300:]}")
            return None

    except Exception as e:
        print(f"Kapak olusturma hatasi: {e}")
        return None

def search_youtube_rss(query, seen_ids, max_clips=2):
    """YouTube RSS feedlerinden video bul ve indir"""
    import feedparser

    NEWS_CHANNELS = [
        ("UCVTyTA4-gk6H_Th8dBnEmNQ", "ABC News"),
        ("UCupvZG-5ko_eiXAupbDfxWw", "CNN"),
        ("UCXIJgqnII2ZOINSWNOGFThA", "Fox News"),
        ("UCeY0bbntWzzVIaj2z3QigXg", "NBC News"),
        ("UC8p1vwvB8vI4LasAZZFAL5g", "CBS News"),
        ("UCIALMKvObZNtJ6AmdCLP7Lg", "MSNBC"),
        ("UCP4bf6IHJJQehibu6ai__cg", "BBC News"),
        ("UCNye-wNBqNL5ZzHSJj3l8Bg", "Al Jazeera"),
    ]

    clips = []
    found = []
    query_words = [w.lower() for w in query.split() if len(w) > 2]

    for channel_id, channel_name in NEWS_CHANNELS:
        if len(clips) >= max_clips:
            break
        try:
            rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:30]:
                if len(clips) >= max_clips:
                    break
                title = entry.get("title", "")
                video_url = entry.get("link", "")
                if not video_url or "watch" not in video_url:
                    continue
                vid = video_url.split("v=")[-1].split("&")[0]
                if len(vid) != 11 or vid in seen_ids:
                    continue
                title_lower = title.lower()
                matches = sum(1 for w in query_words if w in title_lower)
                if matches == 0:
                    continue
                thumb = f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"
                clip_path = OUTPUT_DIR / f"rss_{vid}.mp4"
                dl = download_youtube_clip(video_url, 5, 45, clip_path)
                if dl and clip_path.exists():
                    clips.append(clip_path)
                    found.append({"id": vid, "title": title, "thumbnail": thumb, "url": video_url})
                    seen_ids.add(vid)
                    send_telegram(f"RSS klibi alindi ({channel_name}): {title[:50]}")
        except Exception as e:
            print(f"RSS hatasi {channel_name}: {e}")

    return clips, found

def search_news_channels(query, seen_ids, max_clips=2):
    """Cok katmanli video arama - yt-dlp + RSS"""
    clips = []
    found = []

    # 1. yt-dlp ile C-SPAN
    try:
        result = subprocess.run([
            "yt-dlp", "--no-download",
            "--print", "%(id)s\t%(title)s\t%(thumbnail)s",
            "--playlist-end", "5",
            f"https://www.youtube.com/@CSPAN/search?query={query.replace(' ', '+')}"
        ], capture_output=True, text=True, timeout=30)
        query_words = [w.lower() for w in query.split() if len(w) > 2]
        for line in result.stdout.strip().split("\n"):
            if len(clips) >= max_clips:
                break
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            vid, title, thumb = parts[0].strip(), parts[1].strip(), parts[2].strip()
            if not vid or len(vid) != 11 or vid in seen_ids:
                continue
            title_lower = title.lower()
            matches = sum(1 for w in query_words if w in title_lower)
            if matches == 0:
                continue
            clip_path = OUTPUT_DIR / f"cspan_{vid}.mp4"
            dl = download_youtube_clip(f"https://www.youtube.com/watch?v={vid}", 0, 60, clip_path)
            if dl and clip_path.exists():
                clips.append(clip_path)
                found.append({"id": vid, "title": title, "thumbnail": thumb, "url": f"https://www.youtube.com/watch?v={vid}"})
                seen_ids.add(vid)
                send_telegram(f"C-SPAN klibi: {title[:50]}")
    except Exception as e:
        print(f"C-SPAN hatasi: {e}")

    # 2. yt-dlp ile genel YouTube arama
    if len(clips) < max_clips:
        try:
            result = subprocess.run([
                "yt-dlp", "--no-download",
                "--print", "%(id)s\t%(title)s\t%(thumbnail)s",
                "--playlist-end", "5",
                "--match-filter", "duration < 1800",
                f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}&sp=EgIYAQ%3D%3D"
            ], capture_output=True, text=True, timeout=30)
            query_words = [w.lower() for w in query.split() if len(w) > 2]
            for line in result.stdout.strip().split("\n"):
                if len(clips) >= max_clips:
                    break
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                vid, title, thumb = parts[0].strip(), parts[1].strip(), parts[2].strip()
                if not vid or len(vid) != 11 or vid in seen_ids:
                    continue
                title_lower = title.lower()
                matches = sum(1 for w in query_words if w in title_lower)
                if matches == 0:
                    continue
                clip_path = OUTPUT_DIR / f"yt_{vid}.mp4"
                dl = download_youtube_clip(f"https://www.youtube.com/watch?v={vid}", 5, 30, clip_path)
                if dl and clip_path.exists():
                    clips.append(clip_path)
                    found.append({"id": vid, "title": title, "thumbnail": thumb, "url": f"https://www.youtube.com/watch?v={vid}"})
                    seen_ids.add(vid)
                    send_telegram(f"YouTube klibi: {title[:50]}")
        except Exception as e:
            print(f"YouTube arama hatasi: {e}")

    # 3. RSS ile haber kanallari - en guvenilir fallback
    if len(clips) < max_clips:
        rss_clips, rss_found = search_youtube_rss(query, seen_ids, max_clips - len(clips))
        clips.extend(rss_clips)
        found.extend(rss_found)

    return clips, found

def is_relevant(video_title, keywords):
    """Video basliginin arama terimleriyle alakali olup olmadigini kontrol et"""
    title_lower = video_title.lower()
    kws = [w.lower() for w in keywords if len(w) > 3]
    if not kws:
        return True
    matches = sum(1 for w in kws if w in title_lower)
    return matches >= max(1, len(kws) // 3)

def find_best_video_clips(analysis, seen_ids=None):
    """Ana karakterle alakali video klip bul - cok agresif arama"""
    if seen_ids is None:
        seen_ids = set()

    video_clips = []
    found_videos = []

    main_person = analysis.get("main_person", "")
    people = analysis.get("people", [])
    queries = analysis.get("video_search_queries", [])
    article_title = analysis.get("article_title", "")
    drama_type = analysis.get("drama_type", "")

    # Ana karakter soyadi
    last_name = main_person.split()[-1] if main_person else ""

    # Akilli sorgu olustur
    STOPWORDS = {"the", "and", "for", "over", "from", "with", "that", "this",
                 "have", "been", "will", "about", "after", "before", "against"}

    def make_smart_queries(main_person, last_name, drama_type, article_title, queries):
        result = []
        # 1. Ana kisi varsa - en iyi sorgular
        if main_person:
            result.append(main_person)
            if last_name:
                result.append(last_name)
            if drama_type:
                drama_words = [w for w in drama_type.split() if len(w) > 4 and w.lower() not in STOPWORDS]
                if drama_words:
                    result.append(f"{last_name} {drama_words[0]}")

        # 2. Ana kisi yoksa basliktan anlamli kelimeler sec
        if not main_person and article_title:
            title_words = [w for w in article_title.split()
                          if len(w) > 4 and w.lower() not in STOPWORDS]
            if title_words:
                result.append(" ".join(title_words[:3]))
                result.append(title_words[0])

        # 3. Claude'un urettigi sorgulardan anlamli olanlar
        for q in queries:
            q = q.strip()
            words = [w for w in q.split() if w.lower() not in STOPWORDS]
            if words and len(words) <= 4 and len(words) >= 2:
                result.append(" ".join(words[:3]))

        # Tekrarlari kaldir, max 5 sorgu
        seen = set()
        unique = []
        for q in result:
            if q.lower() not in seen and q.strip():
                seen.add(q.lower())
                unique.append(q)
        return unique[:5]

    news_queries = make_smart_queries(main_person, last_name, drama_type, article_title, queries)
    send_telegram(f"Arama: {main_person or article_title[:30]} → {news_queries[:3]}")

    # ============================================================
    # 1. BUYUK HABER KANALLARI - birincil kaynak (en guncel)
    # ============================================================

    for nq in news_queries[:3]:
        if len(video_clips) >= 2:
            break
        news_clips, news_found = search_news_channels(nq, seen_ids, max_clips=2)
        video_clips.extend(news_clips)
        found_videos.extend(news_found)
        for v in news_found:
            seen_ids.add(v["id"])

    # ============================================================
    # 2. C-SPAN - ikincil kaynak
    # ============================================================
    if len(video_clips) < 2:
        cspan_queries = []
        if main_person:
            cspan_queries.append(main_person)
        if last_name:
            cspan_queries.append(last_name)
        for p in people[:2]:
            if p != main_person:
                cspan_queries.append(p)

        send_telegram(f"C-SPAN aranıyor: {main_person}")

        for cspan_q in cspan_queries[:3]:
            if len(video_clips) >= 2:
                break
            try:
                result = subprocess.run([
                    "yt-dlp", "--no-download",
                    "--print", "%(id)s\t%(title)s\t%(thumbnail)s",
                    "--playlist-end", "5",
                    f"https://www.youtube.com/@CSPAN/search?query={cspan_q.replace(' ', '+')}"
                ], capture_output=True, text=True, timeout=45)

                for line in result.stdout.strip().split("\n"):
                    parts = line.split("\t")
                    if len(parts) < 3:
                        continue
                    vid = parts[0].strip()
                    title = parts[1].strip()
                    thumb = parts[2].strip()
                    if not vid or len(vid) != 11 or vid in seen_ids:
                        continue

                    # Tam isim eslemesi - her iki kelime de baslikta gecmeli
                    if main_person:
                        person_words = main_person.lower().split()
                        title_lower = title.lower()
                        matches = sum(1 for w in person_words if w in title_lower)
                        if len(person_words) >= 2 and matches < 2:
                            print(f"C-SPAN atlandi: {title[:50]}")
                            continue

                    clip_path = OUTPUT_DIR / f"cspan_{vid}.mp4"
                    dl = download_youtube_clip(f"https://www.youtube.com/watch?v={vid}", 0, 90, clip_path)
                    if dl and clip_path.exists():
                        video_clips.append(clip_path)
                        found_videos.append({"id": vid, "title": title, "thumbnail": thumb, "url": f"https://www.youtube.com/watch?v={vid}"})
                        seen_ids.add(vid)
                        send_telegram(f"C-SPAN klibi alindi: {title[:60]}")
                        if len(video_clips) >= 2:
                            break
            except Exception as e:
                print(f"C-SPAN hatasi ({cspan_q}): {e}")

    # ============================================================
    # 3. YouTube - ucuncu kaynak
    # ============================================================
    if len(video_clips) < 4:
        send_telegram("YouTube aranıyor...")
        yt_queries = []
        if main_person and drama_type:
            yt_queries.append(f"{last_name} {drama_type[:20]}")
        if last_name:
            yt_queries.append(last_name)
        yt_queries += queries[:3]
        if main_person:
            yt_queries.append(main_person)

        for query in yt_queries[:6]:
            if len(video_clips) >= 4:
                break
            videos = search_youtube_for_video(query, max_results=2, recent=True)
            if not videos:
                videos = search_youtube_for_video(query, max_results=2, recent=False)
            for video in videos:
                if video["id"] not in seen_ids and len(video_clips) < 4:
                    if main_person and not is_relevant(video["title"], main_person.split()):
                        continue
                    clip_path = OUTPUT_DIR / f"yt_{video['id']}.mp4"
                    dl = download_youtube_clip(video["url"], 10, 30, clip_path)
                    if dl and clip_path.exists():
                        video_clips.append(clip_path)
                        found_videos.append(video)
                        seen_ids.add(video["id"])
                        print(f"YouTube klibi: {video['title'][:50]}")

    # RSS ile haber kanallari
    if len(video_clips) < 2:
        main_q = f"{last_name} {drama_type[:20]}" if last_name else article_title[:30]
        for nq in [main_q, last_name, main_person]:
            if not nq or len(video_clips) >= 2:
                break
            rss_clips, rss_found = search_youtube_rss(nq, seen_ids, 2 - len(video_clips))
            video_clips.extend(rss_clips)
            found_videos.extend(rss_found)

    send_telegram(f"Toplam {len(video_clips)} video klibi bulundu!")
    return video_clips, found_videos, seen_ids

def create_video(article, audio_path, output_path, analysis, youtube_videos):
    send_telegram("Video olusturuluyor...")
    audio_duration = get_clip_duration(audio_path)
    photo_clips = []

    # Video klipleri bul
    video_clips, found_videos, seen_ids = find_best_video_clips(analysis)

    # Haberdeki kisilerin Wikipedia fotograflari
    people = analysis.get("people", [])
    for i, person in enumerate(people[:3]):
        photo_url = get_wikipedia_photo(person)
        if photo_url:
            try:
                photo_path = OUTPUT_DIR / f"person_{i}.jpg"
                download_file(photo_url, photo_path)
                video_path = OUTPUT_DIR / f"person_video_{i}.mp4"
                photo_to_video(photo_path, 8, video_path)
                photo_clips.append(video_path)
                os.remove(photo_path)
                print(f"Wikipedia fotografi alindi: {person}")
            except Exception as e:
                print(f"Wikipedia hatasi {person}: {e}")

    # Pexels fotograflar - habere ozel sorgular, Capitol/WH her video ayni olmasin
    import random
    pexels_query = analysis.get("pexels_query", "Washington DC politics")
    main_person = analysis.get("main_person", "")
    drama_type = analysis.get("drama_type", "")
    
    # Habere ozel sorgular olustur
    specific_queries = []
    if pexels_query and pexels_query != "Washington DC politics":
        specific_queries.append(pexels_query)
    if drama_type:
        # Drama tipine gore gorsel
        drama_lower = drama_type.lower()
        if any(w in drama_lower for w in ["court", "trial", "judge", "legal"]):
            specific_queries.append("courthouse justice law")
        elif any(w in drama_lower for w in ["war", "military", "attack", "bomb"]):
            specific_queries.append("military war fighter jet")
        elif any(w in drama_lower for w in ["protest", "rally", "march"]):
            specific_queries.append("protest crowd demonstration")
        elif any(w in drama_lower for w in ["scandal", "assault", "sexual"]):
            specific_queries.append("government corruption scandal")
        elif any(w in drama_lower for w in ["election", "vote", "ballot"]):
            specific_queries.append("election voting democracy")
        elif any(w in drama_lower for w in ["congress", "senate", "vote", "bill"]):
            specific_queries.append("US Senate Congress hearing")
    
    # Genel sorgular - her seferinde farkli sayfa getir
    page = random.randint(1, 5)
    general_queries = [
        f"US Capitol Washington DC {page}",
        "American flag government building",
        "Washington DC political press",
    ]
    
    queries = specific_queries + general_queries
    used_urls = set()

    for q in queries:
        photo_urls = fetch_pexels_photos(q, count=4)
        for url in photo_urls:
            if url not in used_urls and len(photo_clips) < 12:
                try:
                    photo_path = OUTPUT_DIR / f"pexels_photo_{len(photo_clips)}.jpg"
                    download_file(url, photo_path)
                    video_path = OUTPUT_DIR / f"pexels_video_{len(photo_clips)}.mp4"
                    photo_to_video(photo_path, 8, video_path)
                    photo_clips.append(video_path)
                    used_urls.add(url)
                    os.remove(photo_path)
                except:
                    pass

    if len(photo_clips) < 3:
        for q in queries[:2]:
            video_urls = fetch_pexels_videos(q, count=3)
            for url in video_urls:
                if url not in used_urls and len(photo_clips) < 8:
                    try:
                        path = OUTPUT_DIR / f"pexels_vid_{len(photo_clips)}.mp4"
                        download_file(url, path)
                        photo_clips.append(path)
                        used_urls.add(url)
                    except:
                        pass

    build_final_video(video_clips, photo_clips, audio_path, audio_duration, output_path)

    for clip in video_clips + photo_clips:
        try: os.remove(clip)
        except: pass

    return found_videos

def send_cover_to_telegram(found_videos, hook_title, analysis):
    """Kapak fotografi - make_cover.py ile olustur"""
    try:
        import json as jsonlib
        env_data = jsonlib.dumps({"hook_title": hook_title, "analysis": analysis})
        import subprocess as sp
        result = sp.run(
            ["python3", "/app/make_cover.py", env_data],
            capture_output=True, timeout=120
        )
        if result.returncode != 0:
            send_telegram(f"Kapak hatasi: {result.stderr.decode()[-200:]}")
    except Exception as e:
        send_telegram(f"Kapak olusturulamadi: {str(e)}")

def generate_script(article, hook_title, analysis):
    send_telegram("Script yaziliyor...")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    drama_type = analysis.get("drama_type", "political conflict")
    people = analysis.get("people", [])
    people_str = ", ".join(people) if people else "key political figures"

    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": f"""You are a political DRAMA channel scriptwriter — NOT a news anchor.

Your job is to make viewers FEEL something, not just inform them.

ARTICLE:
Title: {article['title']}
Hook Title: {hook_title}
Summary: {article['summary']}
Key People: {people_str}
Drama Type: {drama_type}

Write an 8-12 minute script (~1100-1600 words).

STRICT FORMULA:
1. HOOK (30 sec) — Start MID-ACTION. NEVER say "Today in Washington" or "Welcome back".
   Start with: "He didn't expect this." / "This just changed everything." / "Nobody saw this coming."
   Make viewer feel they walked into a crisis already happening.

2. SETUP (1 min) — Who are these people? Why should we care? Keep it punchy.

3. THE DRAMA (5-6 min) — Build tension.
   - What exactly happened?
   - Who got blindsided?
   - Reactions: erupted, slammed, destroyed, blindsided, furious
   - What does this mean for regular people?

4. REACTIONS (2 min) — How are people responding? Who won? Who lost?

5. WHAT'S NEXT (1 min) — Tease what could happen. Leave viewer wanting more.

6. OUTRO (30 sec) — "Subscribe now so you never miss what's really happening in Washington."

TONE RULES:
- Sound OUTRAGED or SHOCKED, not reading a report
- Short sentences. Punchy. Dramatic.
- Use "And here's the thing..." / "But wait." / "Nobody is talking about this."
- NEVER say "In conclusion" or "As we can see"

Write ONLY the spoken script, no stage directions:"""}]
    )
    return response.content[0].text

def generate_audio_elevenlabs(script, output_path):
    """ElevenLabs TTS - su an deaktif, ileride kullanmak icin sakla"""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    chunks = [script[i:i+4500] for i in range(0, len(script), 4500)]
    audio_files = []

    for i, chunk in enumerate(chunks):
        chunk_path = OUTPUT_DIR / f"audio_chunk_{i}.mp3"
        response = requests.post(url, headers=headers, json={
            "text": chunk, "model_id": "eleven_turbo_v2_5",
            "voice_settings": {"stability": 0.70, "similarity_boost": 0.80}
        })
        if response.status_code == 200:
            with open(chunk_path, "wb") as f:
                f.write(response.content)
            audio_files.append(str(chunk_path))
        else:
            raise Exception(f"ElevenLabs hatasi: {response.status_code} - {response.text}")

    if len(audio_files) == 1:
        import shutil
        shutil.copy(audio_files[0], output_path)
    else:
        list_file = OUTPUT_DIR / "audio_list.txt"
        with open(list_file, "w") as f:
            for af in audio_files:
                f.write(f"file '{os.path.abspath(af)}'\n")
        subprocess.run([
            "ffmpeg", "-f", "concat", "-safe", "0",
            "-i", str(list_file), "-c", "copy", str(output_path), "-y"
        ], check=True)
        for af in audio_files:
            os.remove(af)
        os.remove(list_file)

    return output_path

def generate_audio_edge(script, output_path):
    """Edge TTS - Microsoft, ucretsiz ve sinırsiz"""
    import asyncio
    import edge_tts

    # en-US-GuyNeural: haber spikeri tarzi, guclu ve dramatik
    # ElevenLabs mUfWEBhcigm8YlCDbmGP sesine en yakin
    EDGE_VOICE = "en-US-GuyNeural"

    chunks = [script[i:i+4500] for i in range(0, len(script), 4500)]
    audio_files = []

    async def synthesize(text, path):
        communicate = edge_tts.Communicate(text, EDGE_VOICE, rate="+5%", volume="+10%")
        await communicate.save(path)

    for i, chunk in enumerate(chunks):
        chunk_path = str(OUTPUT_DIR / f"audio_chunk_{i}.mp3")
        asyncio.run(synthesize(chunk, chunk_path))
        audio_files.append(chunk_path)

    if len(audio_files) == 1:
        import shutil
        shutil.copy(audio_files[0], str(output_path))
    else:
        list_file = OUTPUT_DIR / "audio_list.txt"
        with open(list_file, "w") as f:
            for af in audio_files:
                f.write(f"file '{os.path.abspath(af)}'\n")
        subprocess.run([
            "ffmpeg", "-f", "concat", "-safe", "0",
            "-i", str(list_file), "-c", "copy", str(output_path), "-y"
        ], check=True)
        for af in audio_files:
            os.remove(af)
        os.remove(str(list_file))

    return output_path

def generate_audio_gtts(script, output_path):
    """gTTS - ucretsiz, yedek olarak sakla"""
    from gtts import gTTS
    import shutil
    chunks = [script[i:i+4500] for i in range(0, len(script), 4500)]
    audio_files = []
    for i, chunk in enumerate(chunks):
        chunk_path = str(OUTPUT_DIR / f"audio_chunk_{i}.mp3")
        tts = gTTS(text=chunk, lang="en", tld="com", slow=False)
        tts.save(chunk_path)
        audio_files.append(chunk_path)
    if len(audio_files) == 1:
        shutil.copy(audio_files[0], str(output_path))
    else:
        list_file = OUTPUT_DIR / "audio_list.txt"
        with open(list_file, "w") as f:
            for af in audio_files:
                f.write(f"file '{os.path.abspath(af)}'\n")
        subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0",
            "-i", str(list_file), "-c", "copy", str(output_path), "-y"], check=True)
        for af in audio_files:
            os.remove(af)
        os.remove(str(list_file))
    return output_path

def generate_audio(script, output_path):
    send_telegram("Seslendirme yapiliyor...")
    # OpenAI TTS - Nova sesi
    # Yedek icin: return generate_audio_gtts(script, output_path)
    # ElevenLabs icin: return generate_audio_elevenlabs(script, output_path)
    import shutil

    chunks = [script[i:i+4500] for i in range(0, len(script), 4500)]
    audio_files = []

    for i, chunk in enumerate(chunks):
        chunk_path = str(OUTPUT_DIR / f"audio_chunk_{i}.mp3")
        response = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "tts-1",
                "input": chunk,
                "voice": "nova",
                "speed": 1.05
            },
            timeout=60
        )
        if response.status_code == 200:
            with open(chunk_path, "wb") as f:
                f.write(response.content)
            audio_files.append(chunk_path)
        else:
            send_telegram(f"OpenAI TTS hatasi: {response.status_code} - gTTS'e geciliyor")
            return generate_audio_gtts(script, output_path)

    if len(audio_files) == 1:
        shutil.copy(audio_files[0], str(output_path))
    else:
        list_file = OUTPUT_DIR / "audio_list.txt"
        with open(list_file, "w") as f:
            for af in audio_files:
                f.write(f"file '{os.path.abspath(af)}'\n")
        subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0",
            "-i", str(list_file), "-c", "copy", str(output_path), "-y"], check=True)
        for af in audio_files:
            os.remove(af)
        os.remove(str(list_file))

    return output_path

def generate_metadata(article, hook_title, analysis):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    people = analysis.get("people", [])
    drama = analysis.get("drama_type", "")

    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=600,
        messages=[{"role": "user", "content": f"""Create YouTube metadata for this political drama video. Return ONLY valid JSON.

Hook Title: {hook_title}
Article: {article['title']}
Key People: {', '.join(people)}
Drama: {drama}

Description rules:
- First 2 sentences must be DRAMATIC and hook the reader
- Include key people names for SEO
- Add subscribe CTA
- 2-3 paragraphs total

Return exactly:
{{"title": "{hook_title[:70]}", "description": "dramatic description here", "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"]}}

Tags: include people names, topic keywords, "breaking news", "US politics" etc."""}]
    )
    try:
        text = response.content[0].text.strip()
        return json.loads(text)
    except:
        return {
            "title": hook_title[:70],
            "description": f"BREAKING: {article['title']}\n\nStay ahead of Washington's biggest stories. Subscribe for daily political coverage.",
            "tags": ["US politics", "breaking news", "Trump", "Congress", "Washington", "political drama"]
        }

def run(article):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    send_telegram(f"Video pipeline basladi!\n\n{article['title']}")

    try:
        # 1. Analiz
        send_telegram("Haber analiz ediliyor...")
        analysis = detect_people_and_topics(article)
        people = analysis.get("people", [])
        drama = analysis.get("drama_type", "")
        if people:
            send_telegram(f"Kisiler: {', '.join(people)}\nDrama: {drama}")

        # 2. Hook baslik
        hook_title = generate_hook_title(article)
        send_telegram(f"Hook baslik: *{hook_title}*")

        # 3. Script
        script = generate_script(article, hook_title, analysis)
        with open(OUTPUT_DIR / f"script_{timestamp}.txt", "w") as f:
            f.write(script)

        # 4. Ses
        audio_path = OUTPUT_DIR / f"audio_{timestamp}.mp3"
        generate_audio(script, audio_path)

        # 5. Video - genisletilmis arama
        final_video = OUTPUT_DIR / f"final_{timestamp}.mp4"
        found_videos = create_video(article, audio_path, final_video, analysis, [])

        # 6. Metadata
        metadata = generate_metadata(article, hook_title, analysis)
        with open(OUTPUT_DIR / f"metadata_{timestamp}.json", "w") as f:
            json.dump({"youtube": metadata, "analysis": analysis, "hook_title": hook_title, "timestamp": timestamp}, f, ensure_ascii=False, indent=2)

        # 7. YouTube yukle
        send_telegram("YouTube yuklemesi basliyor...")
        import youtube_uploader
        youtube_uploader.upload(str(final_video), metadata)

        # 8. Kapak komutu gonder - kullanici ChatGPT'ye yaptiracak
        people = analysis.get("people", [])
        people_str = " | ".join(people[:3]) if people else ""
        kapak_cmd = f"/kapak {hook_title} | {people_str}"
        send_telegram(
            f"Kapaği ChatGPT'ye yaptir:\n\n`{kapak_cmd}`\n\nYukaridaki komutu kopyala ve ChatGPT'ye yapistir!"
        )

    except Exception as e:
        import traceback
        error_msg = f"Pipeline hatasi: {str(e)}\n{traceback.format_exc()[-300:]}"
        print(error_msg)
        send_telegram(f"Pipeline hatasi: {str(e)}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        article = json.loads(sys.argv[1])
        run(article)
