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

VOICE_ID = "mUfWEBhcigm8YlCDbmGP"
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

Return exactly:
{{
  "people": ["Person Name 1", "Person Name 2"],
  "main_person": "Most important person causing drama or conflict",
  "drama_type": "brief description of the conflict/drama",
  "video_search_queries": [
    "query 1 - person name + speech/statement/reaction",
    "query 2 - topic + press conference/hearing",
    "query 3 - broader topic news",
    "query 4 - C-SPAN specific search",
    "query 5 - alternative angle"
  ],
  "pexels_query": "fallback stock footage query"
}}

video_search_queries should be 5 different searches to find relevant video footage.
Example for Trump DHS news: 
["Trump DHS statement", "Trump press conference DHS", "DHS shutdown Congress", "Senate DHS vote hearing", "Trump White House speech"]"""}]
    )
    try:
        return json.loads(response.content[0].text.strip())
    except:
        return {
            "people": [],
            "main_person": "",
            "drama_type": "",
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
    try:
        coverage = 0.5
        try:
            import pytesseract
            from PIL import Image
            from pytesseract import Output
            img = Image.open(thumbnail_path)
            width, height = img.size
            data = pytesseract.image_to_data(img, output_type=Output.DICT)
            text_rows = []
            for i, text in enumerate(data['text']):
                if text.strip() and int(data['conf'][i]) > 30:
                    y = data['top'][i]
                    h = data['height'][i]
                    text_rows.append(y + h)
            if text_rows:
                coverage = max(text_rows) / height
        except:
            pass

        if coverage > 0.75:
            crop_ratio = 0.70
        elif coverage > 0.55:
            crop_ratio = 0.80
        elif coverage > 0.35:
            crop_ratio = 0.88
        else:
            crop_ratio = 0.95

        safe_title = hook_title.replace("'", "").replace(":", " -").replace('"', '').replace("\\", "")
        char_count = len(safe_title)
        font_size = 72
        while font_size > 22:
            if char_count * font_size * 0.58 <= 1220:
                break
            font_size -= 2

        subprocess.run([
            "ffmpeg", "-i", str(thumbnail_path),
            "-vf", (
                f"crop=in_w:in_h*{crop_ratio}:0:0,"
                "scale=1280:720:force_original_aspect_ratio=decrease,"
                "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,"
                f"drawtext=text='{safe_title}':fontcolor=white:fontsize={font_size}:"
                "x=(w-text_w)/2:y=(h-text_h-20):"
                "box=1:boxcolor=black@0.85:boxborderw=14:font=DejaVuSans-Bold"
            ),
            "-frames:v", "1", "-update", "1",
            str(output_path), "-y"
        ], check=True, capture_output=True)
        return output_path
    except Exception as e:
        print(f"Kapak hatasi: {e}")
        return None

def find_best_video_clips(analysis, seen_ids=None):
    """Birden fazla kaynaktan video klip bul"""
    if seen_ids is None:
        seen_ids = set()

    video_clips = []
    found_videos = []

    main_person = analysis.get("main_person", "")
    people = analysis.get("people", [])
    queries = analysis.get("video_search_queries", [])

    # 1. C-SPAN - ana kisi ile ara
    cspan_query = main_person if main_person else (people[0] if people else "Congress hearing")
    send_telegram(f"C-SPAN aranıyor: {cspan_query}")
    cspan_videos = search_cspan_youtube(cspan_query)

    for video in cspan_videos[:2]:
        if video["id"] not in seen_ids:
            clip_path = OUTPUT_DIR / f"cspan_{video['id']}.mp4"
            result = download_youtube_clip(video["url"], 0, 90, clip_path)
            if result and clip_path.exists():
                video_clips.append(clip_path)
                found_videos.append(video)
                seen_ids.add(video["id"])
                send_telegram(f"C-SPAN klibi alindi: {video['title'][:50]}")
                if len(video_clips) >= 2:
                    break

    # 2. YouTube genisletilmis arama - 5 farkli sorgu
    send_telegram(f"YouTube aranıyor ({len(queries)} sorgu)...")
    for query in queries[:5]:
        if len(video_clips) >= 4:
            break
        # Once son 24 saat dene
        videos = search_youtube_for_video(query, max_results=2, recent=True)
        if not videos:
            # Bulamazsa bu ay ara
            videos = search_youtube_for_video(query, max_results=2, recent=False)

        for video in videos:
            if video["id"] not in seen_ids and len(video_clips) < 4:
                clip_path = OUTPUT_DIR / f"yt_{video['id']}.mp4"
                result = download_youtube_clip(video["url"], 10, 30, clip_path)
                if result and clip_path.exists():
                    video_clips.append(clip_path)
                    found_videos.append(video)
                    seen_ids.add(video["id"])
                    print(f"YouTube klibi: {video['title'][:50]}")

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

    # Pexels fotograflar
    pexels_query = analysis.get("pexels_query", "Washington DC politics")
    queries = [pexels_query, "US Congress Capitol building", "White House Washington DC", "American politics government"]
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
    """Kapak fotografi - MUTLAKA haberdeki kisinin yuzunu goster"""
    best_thumb = None
    thumb_paths = []

    main_person = analysis.get("main_person", "")
    people = analysis.get("people", [])

    # 1. Ana kisi Wikipedia fotografi - EN YUKSEK ONCELIK
    all_people = [main_person] + [p for p in people if p != main_person]
    for person in all_people[:3]:
        if not person:
            continue
        wiki_url = get_wikipedia_photo(person)
        if wiki_url:
            try:
                thumb_path = OUTPUT_DIR / f"cover_wiki_{person.replace(' ', '_')}.jpg"
                result = download_thumbnail(wiki_url, thumb_path)
                if result:
                    thumb_paths.append(thumb_path)
                    best_thumb = thumb_path
                    send_telegram(f"Kapak icin Wikipedia fotografi: {person}")
                    break
            except:
                pass

    # 2. Wikipedia yoksa - bulunan video thumbnailleri (az yazili olanlar)
    if not best_thumb:
        best_score = 999
        for video in found_videos[:5]:
            if video.get("thumbnail"):
                try:
                    thumb_path = OUTPUT_DIR / f"cover_yt_{video['id']}.jpg"
                    result = download_thumbnail(video["thumbnail"], thumb_path)
                    if result:
                        score = get_thumbnail_text_score(thumb_path)
                        thumb_paths.append(thumb_path)
                        if score < best_score:
                            best_score = score
                            best_thumb = thumb_path
                except:
                    pass

    if best_thumb:
        try:
            cover_path = OUTPUT_DIR / "cover_final.jpg"
            result = create_cover_image(best_thumb, hook_title, cover_path)
            if result:
                send_telegram_photo_file(
                    cover_path,
                    f"Kapak fotografi (1280x720)\nBaslik: {hook_title}\n\nYouTube'da manuel yukle!"
                )
                try: os.remove(cover_path)
                except: pass
        except Exception as e:
            print(f"Kapak olusturma hatasi: {e}")
            send_telegram("Kapak fotografi olusturulamadi, manuel ekle!")
    else:
        send_telegram("Kapak fotografi bulunamadi, manuel ekle!")

    for tp in thumb_paths:
        try: os.remove(tp)
        except: pass

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

def generate_audio(script, output_path):
    send_telegram("Seslendirme yapiliyor...")
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
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        # 7. YouTube yukle
        send_telegram("YouTube yuklemesi basliyor...")
        import youtube_uploader
        youtube_uploader.upload(str(final_video), metadata)

        # 8. Kapak - MUTLAKA kisi yuzu
        send_cover_to_telegram(found_videos, hook_title, analysis)

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
