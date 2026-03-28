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

VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
OUTPUT_DIR = Path("output_videos")
OUTPUT_DIR.mkdir(exist_ok=True)

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"})

def send_telegram_photo_file(photo_path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    with open(photo_path, "rb") as f:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption}, files={"photo": f})

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
  "main_person": "Most important person in the story",
  "youtube_queries": ["search query 1", "search query 2", "search query 3"],
  "cspan_query": "C-SPAN specific search query",
  "pexels_query": "fallback stock footage query"
}}

youtube_queries: 3 different search terms to find related YouTube videos from last 12 hours.
Example for Trump Iran news: ["Trump Iran statement", "Iran US war latest", "Trump cabinet Iran"]"""}]
    )
    try:
        text = response.content[0].text.strip()
        return json.loads(text)
    except:
        return {
            "people": [],
            "main_person": "",
            "youtube_queries": ["US politics news", "Congress hearing", "White House briefing"],
            "cspan_query": "Congress hearing",
            "pexels_query": "Washington DC politics"
        }

def generate_hook_title(article):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=150,
        messages=[{"role": "user", "content": f"""Create a YouTube hook title. Return ONLY the title, nothing else.

Rules:
- Max 60 characters
- Create curiosity or urgency
- Use power words: EXPOSED, CAUGHT, BREAKING, SHOCKING, JUST IN
- Stay factual, no lies
- Examples: "Trump CAUGHT Off Guard as Congress Acts", "BREAKING: Senate Makes Midnight Move"

Article: {article['title']}

Hook title:"""}]
    )
    return response.content[0].text.strip().strip('"')

def get_text_coverage(image_path):
    """OCR ile fotograftaki yazi yogunlugunu olc"""
    try:
        import pytesseract
        from PIL import Image
        from pytesseract import Output

        img = Image.open(image_path)
        width, height = img.size

        data = pytesseract.image_to_data(img, output_type=Output.DICT)
        text_rows = []
        for i, text in enumerate(data['text']):
            if text.strip() and int(data['conf'][i]) > 30:
                y = data['top'][i]
                h = data['height'][i]
                text_rows.append(y + h)

        if text_rows:
            max_text_y = max(text_rows)
            return max_text_y / height
        return 0.0
    except Exception as e:
        print(f"OCR hatasi: {e}")
        return 0.5

def create_cover_image(thumbnail_path, hook_title, output_path):
    """
    - OCR ile yazilarin nerede oldugunu tespit et
    - Yazilari kirp
    - Hook basligini dinamik font ile tam sigdir
    """
    try:
        # OCR ile yazi kapsamini bul
        coverage = get_text_coverage(thumbnail_path)
        print(f"Yazi kaplaması: %{coverage*100:.0f}")

        # Crop oranini belirle
        if coverage > 0.75:
            crop_ratio = 0.70
        elif coverage > 0.55:
            crop_ratio = 0.80
        elif coverage > 0.35:
            crop_ratio = 0.88
        else:
            crop_ratio = 0.95

        # Font boyutunu dinamik hesapla - 1220px genislige sigdir
        safe_title = hook_title.replace("'", "").replace(":", " -").replace('"', '').replace("\\", "")
        max_width = 1220
        char_count = len(safe_title)
        font_size = 72
        while font_size > 22:
            estimated_width = char_count * font_size * 0.58
            if estimated_width <= max_width:
                break
            font_size -= 2

        print(f"Font boyutu: {font_size}")

        vf = (
            f"crop=in_w:in_h*{crop_ratio}:0:0,"
            "scale=1280:720:force_original_aspect_ratio=decrease,"
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"drawtext=text='{safe_title}':fontcolor=white:fontsize={font_size}:"
            "x=(w-text_w)/2:y=(h-text_h-20):"
            "box=1:boxcolor=black@0.85:boxborderw=14:font=DejaVuSans-Bold"
        )

        subprocess.run([
            "ffmpeg", "-i", str(thumbnail_path),
            "-vf", vf,
            "-frames:v", "1", "-update", "1",
            str(output_path), "-y"
        ], check=True, capture_output=True)

        return output_path

    except Exception as e:
        print(f"Kapak olusturma hatasi: {e}")
        # Fallback: sadece resize
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

def get_thumbnail_text_score(image_path):
    """Daha az yazi = daha iyi thumbnail. Dusuk skor = iyi."""
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        word_count = len(text.split())
        return word_count
    except:
        return 999

def search_youtube_recent(query, max_results=3):
    try:
        result = subprocess.run([
            "yt-dlp",
            "--no-download",
            "--print", "%(id)s\t%(title)s\t%(thumbnail)s",
            "--playlist-end", str(max_results),
            "--match-filter", "duration < 1800",
            f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}&sp=EgIIAQ%3D%3D"
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
        print(f"YouTube arama hatasi: {e}")
        return []

def search_cspan_youtube(query):
    try:
        result = subprocess.run([
            "yt-dlp",
            "--no-download",
            "--print", "%(id)s",
            "--playlist-end", "1",
            f"https://www.youtube.com/@CSPAN/search?query={query.replace(' ', '+')}"
        ], capture_output=True, text=True, timeout=45)

        video_id = result.stdout.strip().split("\n")[0].strip()
        if video_id and len(video_id) == 11:
            return f"https://www.youtube.com/watch?v={video_id}"
    except Exception as e:
        print(f"C-SPAN arama hatasi: {e}")
    return None

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
        print(f"YouTube klip indirme hatasi: {e}")
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

    # Video kismi - ilk 3 dakika
    video_section = OUTPUT_DIR / "video_section.mp4"
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
    
    if not all_clips:
        subprocess.run([
            "ffmpeg", "-f", "lavfi", "-i", "color=c=navy:size=1920x1080:rate=30",
            "-t", "5", "-c:v", "libx264", str(video_section), "-y"
        ], check=True, capture_output=True)
        all_clips.append(video_section)

    # Fotograf kismi - geri kalan sure
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

    # Birlestir
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

def create_video(article, audio_path, output_path, analysis, youtube_videos):
    send_telegram("Video olusturuluyor...")
    audio_duration = get_clip_duration(audio_path)
    video_clips = []
    photo_clips = []

    # 1. C-SPAN klip
    cspan_query = analysis.get("cspan_query", "Congress hearing")
    send_telegram("C-SPAN aranıyor...")
    cspan_url = search_cspan_youtube(cspan_query)
    if cspan_url:
        cspan_clip = OUTPUT_DIR / "cspan_clip.mp4"
        result = download_youtube_clip(cspan_url, 0, 180, cspan_clip)
        if result and cspan_clip.exists():
            video_clips.append(cspan_clip)
            send_telegram("C-SPAN klibi alindi!")

    # 2. YouTube son 12 saat klipleri
    for i, video in enumerate(youtube_videos[:3]):
        try:
            clip_path = OUTPUT_DIR / f"yt_clip_{i}.mp4"
            result = download_youtube_clip(video["url"], 10, 30, clip_path)
            if result and clip_path.exists():
                video_clips.append(clip_path)
        except Exception as e:
            print(f"YouTube klip hatasi: {e}")

    # 3. Pexels fotograflar (fotograf bolumu icin)
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

    # Fallback Pexels video
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

def send_cover_to_telegram(youtube_videos, hook_title):
    """En az yazili thumbnail'i sec, OCR ile kirp, hook baslik ekle"""
    best_thumb = None
    best_score = 999
    thumb_paths = []

    # Tum thumbnail'leri indir ve skor hesapla
    for i, video in enumerate(youtube_videos[:5]):
        if video.get("thumbnail"):
            try:
                thumb_path = OUTPUT_DIR / f"thumb_{i}.jpg"
                result = download_thumbnail(video["thumbnail"], thumb_path)
                if result:
                    score = get_thumbnail_text_score(thumb_path)
                    thumb_paths.append((thumb_path, score))
                    print(f"Thumbnail {i} skoru: {score}")
                    if score < best_score:
                        best_score = score
                        best_thumb = thumb_path
            except Exception as e:
                print(f"Thumbnail indirme hatasi: {e}")

    if best_thumb:
        try:
            cover_path = OUTPUT_DIR / "cover_final.jpg"
            create_cover_image(best_thumb, hook_title, cover_path)
            send_telegram_photo_file(
                cover_path,
                f"Kapak fotografi (1280x720)\nBaslik: {hook_title}\n\nYouTube'da manuel yukle!"
            )
            os.remove(cover_path)
        except Exception as e:
            send_telegram(f"Kapak olusturma hatasi: {e}")
    else:
        send_telegram("Kapak fotografi bulunamadi, manuel ekle!")

    # Gecici dosyalari temizle
    for tp, _ in thumb_paths:
        try: os.remove(tp)
        except: pass

def generate_script(article, hook_title):
    send_telegram("Script yaziliyor...")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": f"""You are a professional YouTube news channel scriptwriter.

NEWS:
Original Title: {article['title']}
Hook Title: {hook_title}
Summary: {article['summary']}
Source: {article['source']}

Write an engaging 8-12 minute video script (~1100-1600 words).

Structure:
* Hook (30 sec): Start with most shocking element, create immediate tension
* Introduction (1 min): What happened and why it matters TODAY
* Background (3 min): Deep context, history, key players
* Main story (5-6 min): Full breakdown with details, quotes, reactions
* Analysis (1 min): What this means going forward
* Conclusion (30 sec): What happens next + subscribe CTA

Rules:
- Write ONLY spoken words, no directions, no brackets
- Short punchy sentences
- Build suspense before revealing key facts
- Sound like a confident news anchor

Write the complete script now:"""}]
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
            "voice_settings": {"stability": 0.75, "similarity_boost": 0.75}
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

def generate_metadata(article, hook_title):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": f"""Create YouTube metadata. Return ONLY valid JSON, no markdown.

Hook Title: {hook_title}
Article: {article['title']}

Return exactly:
{{"title": "{hook_title[:70]}", "description": "2-3 paragraph engaging description with keywords and subscribe CTA", "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"]}}"""}]
    )
    try:
        text = response.content[0].text.strip()
        return json.loads(text)
    except:
        return {
            "title": hook_title[:70],
            "description": f"In this video: {article['title']}\n\nSubscribe for more US political news!",
            "tags": ["US politics", "news", "Trump", "Congress", "Washington", "breaking news"]
        }

def run(article):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    send_telegram(f"Video pipeline basladi!\n\n{article['title']}")

    try:
        # 1. Analiz
        analysis = detect_people_and_topics(article)
        people = analysis.get("people", [])
        if people:
            send_telegram(f"Haberdeki kisiler: {', '.join(people)}")

        # 2. Hook baslik
        hook_title = generate_hook_title(article)
        send_telegram(f"Hook baslik: *{hook_title}*")

        # 3. YouTube son 12 saat arama
        send_telegram("YouTube'da ilgili videolar aranıyor...")
        youtube_queries = analysis.get("youtube_queries", ["US politics news"])
        youtube_videos = []
        seen_ids = set()
        for query in youtube_queries:
            videos = search_youtube_recent(query, max_results=3)
            for v in videos:
                if v["id"] not in seen_ids:
                    youtube_videos.append(v)
                    seen_ids.add(v["id"])

        if youtube_videos:
            send_telegram(f"{len(youtube_videos)} YouTube videosu bulundu!")
        else:
            send_telegram("YouTube'da video bulunamadi, Pexels kullanilacak.")

        # 4. Script
        script = generate_script(article, hook_title)
        with open(OUTPUT_DIR / f"script_{timestamp}.txt", "w") as f:
            f.write(script)

        # 5. Ses
        audio_path = OUTPUT_DIR / f"audio_{timestamp}.mp3"
        generate_audio(script, audio_path)

        # 6. Video (ilk 3 dk video, sonrasi fotograf)
        final_video = OUTPUT_DIR / f"final_{timestamp}.mp4"
        create_video(article, audio_path, final_video, analysis, youtube_videos)

        # 7. Metadata
        metadata = generate_metadata(article, hook_title)
        with open(OUTPUT_DIR / f"metadata_{timestamp}.json", "w") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        # 8. YouTube yukle
        send_telegram("YouTube yuklemesi basliyor...")
        import youtube_uploader
        youtube_uploader.upload(str(final_video), metadata)

        # 9. Kapak onerisi - OCR ile en temiz thumbnail sec
        send_cover_to_telegram(youtube_videos, hook_title)

    except Exception as e:
        error_msg = f"Pipeline hatasi: {str(e)}"
        print(error_msg)
        send_telegram(error_msg)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        article = json.loads(sys.argv[1])
        run(article)
