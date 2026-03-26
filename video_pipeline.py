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

def send_telegram_photo(photo_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "photo": photo_url, "caption": caption})

def detect_people_and_topics(article):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=600,
        messages=[{"role": "user", "content": f"""Analyze this news article. Return ONLY valid JSON.

Title: {article['title']}
Summary: {article['summary']}

Return exactly:
{{
  "people": ["Person Name 1", "Person Name 2"],
  "main_person": "Most important person",
  "pexels_query": "stock footage search query (e.g. 'US Capitol Congress', 'White House Washington')",
  "cspan_query": "C-SPAN YouTube search query for related footage",
  "cover_query": "cover image search query"
}}"""}]
    )
    try:
        return json.loads(response.content[0].text.strip())
    except:
        return {"people": [], "main_person": "", "pexels_query": "Washington DC politics", "cspan_query": "Congress hearing", "cover_query": "US Capitol"}

def generate_hook_title(article):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=200,
        messages=[{"role": "user", "content": f"""Create a YouTube hook title for this news. Return ONLY the title, nothing else.

Rules:
- Max 70 characters
- Must create curiosity or urgency
- Use power words: EXPOSED, CAUGHT, BREAKING, SHOCKING, NOBODY EXPECTED
- Do NOT use clickbait lies, stay factual
- Examples: "Trump CAUGHT Off Guard as Congress Drops Bombshell", "NOBODY Expected This Senate Vote"

Article: {article['title']}

Hook title:"""}]
    )
    return response.content[0].text.strip().strip('"')

def get_wikipedia_photo(person_name):
    try:
        params = {"action": "query", "titles": person_name, "prop": "pageimages", "format": "json", "pithumbsize": 800}
        response = requests.get("https://en.wikipedia.org/w/api.php", params=params, timeout=10)
        pages = response.json().get("query", {}).get("pages", {})
        for page in pages.values():
            thumb = page.get("thumbnail", {})
            if thumb:
                return thumb.get("source")
    except:
        pass
    return None

def search_cspan_youtube(query):
    try:
        search_url = "https://www.youtube.com/results"
        params = {"search_query": f"site:c-span.org OR C-SPAN {query}", "sp": "EgIIAQ%3D%3D"}
        headers = {"User-Agent": "Mozilla/5.0"}
        
        # yt-dlp ile C-SPAN YouTube kanalinda ara
        result = subprocess.run([
            "yt-dlp",
            "--no-download",
            "--print", "%(id)s",
            "--playlist-end", "1",
            f"https://www.youtube.com/@CSPAN/search?query={query.replace(' ', '+')}"
        ], capture_output=True, text=True, timeout=30)
        
        video_id = result.stdout.strip().split("\n")[0]
        if video_id and len(video_id) == 11:
            return f"https://www.youtube.com/watch?v={video_id}"
    except:
        pass
    return None

def download_cspan_clip(youtube_url, duration_seconds, output_path):
    try:
        # Once video indir
        temp_path = OUTPUT_DIR / "cspan_temp.mp4"
        result = subprocess.run([
            "yt-dlp",
            "-f", "best[height<=720]",
            "--no-playlist",
            "-o", str(temp_path),
            youtube_url
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0 or not temp_path.exists():
            return None
        
        # Ilk N saniyeyi kes
        subprocess.run([
            "ffmpeg", "-i", str(temp_path),
            "-t", str(duration_seconds),
            "-c:v", "libx264", "-c:a", "aac",
            str(output_path), "-y"
        ], check=True, capture_output=True)
        
        os.remove(temp_path)
        return output_path
    except Exception as e:
        print(f"C-SPAN indirme hatasi: {e}")
        return None

def fetch_pexels_videos(query, count=5):
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

def fetch_pexels_photos(query, count=8):
    if not PEXELS_API_KEY:
        return []
    headers = {"Authorization": PEXELS_API_KEY}
    response = requests.get("https://api.pexels.com/v1/search", headers=headers,
        params={"query": query, "per_page": count})
    if response.status_code != 200:
        return []
    return [p["src"]["large"] for p in response.json().get("photos", [])]

def download_file(url, output_path):
    response = requests.get(url, stream=True, timeout=30)
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return output_path

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

def build_final_video(clips, audio_path, audio_duration, output_path):
    normalized = []
    for i, clip in enumerate(clips):
        norm = OUTPUT_DIR / f"norm_{i}.mp4"
        normalize_clip(clip, norm)
        normalized.append(norm)

    total = 0.0
    loop_clips = []
    while total < audio_duration:
        for c in normalized:
            d = get_clip_duration(c)
            loop_clips.append(c)
            total += d
            if total >= audio_duration:
                break

    list_file = OUTPUT_DIR / "clips_list.txt"
    with open(list_file, "w") as f:
        for c in loop_clips:
            f.write(f"file '{os.path.abspath(c)}'\n")

    combined = OUTPUT_DIR / "combined_video.mp4"
    subprocess.run([
        "ffmpeg", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c:v", "libx264", "-t", str(audio_duration), str(combined), "-y"
    ], check=True, capture_output=True)

    subprocess.run([
        "ffmpeg", "-i", str(combined), "-i", str(audio_path),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        str(output_path), "-y"
    ], check=True, capture_output=True)

    for n in normalized:
        try: os.remove(n)
        except: pass

def create_video(article, audio_path, output_path, analysis):
    send_telegram("Video olusturuluyor...")
    audio_duration = get_clip_duration(audio_path)
    clips = []

    # 1. C-SPAN'dan ilk 2-3 dakika (varsa)
    cspan_query = analysis.get("cspan_query", "Congress hearing")
    cspan_url = search_cspan_youtube(cspan_query)
    if cspan_url:
        cspan_clip = OUTPUT_DIR / "cspan_clip.mp4"
        result = download_cspan_clip(cspan_url, 150, cspan_clip)  # 2.5 dakika
        if result and cspan_clip.exists():
            clips.append(cspan_clip)
            send_telegram(f"C-SPAN klibi alindi!")
            print("C-SPAN klibi basariyla indirildi")

    # 2. Haberdeki kisilerin Wikipedia fotograflari
    people = analysis.get("people", [])
    for i, person in enumerate(people[:3]):
        photo_url = get_wikipedia_photo(person)
        if photo_url:
            try:
                photo_path = OUTPUT_DIR / f"person_{i}.jpg"
                download_file(photo_url, photo_path)
                video_path = OUTPUT_DIR / f"person_video_{i}.mp4"
                photo_to_video(photo_path, 8, video_path)
                clips.append(video_path)
                os.remove(photo_path)
                print(f"Wikipedia fotografi: {person}")
            except Exception as e:
                print(f"Wikipedia hatasi {person}: {e}")

    # 3. Pexels stock video (farkli sorgularla)
    pexels_query = analysis.get("pexels_query", "Washington DC politics")
    queries = [pexels_query, "US Congress Capitol", "White House Washington", "American politics news"]
    
    used_urls = set()
    for q in queries:
        if len(clips) >= 8:
            break
        video_urls = fetch_pexels_videos(q, count=3)
        for url in video_urls:
            if url not in used_urls:
                try:
                    path = OUTPUT_DIR / f"pexels_video_{len(clips)}.mp4"
                    download_file(url, path)
                    clips.append(path)
                    used_urls.add(url)
                except:
                    pass

    # 4. Pexels fotograf (yeterli video yoksa)
    if len(clips) < 4:
        for q in queries[:2]:
            photo_urls = fetch_pexels_photos(q, count=5)
            for i, url in enumerate(photo_urls):
                if len(clips) >= 8:
                    break
                try:
                    photo_path = OUTPUT_DIR / f"extra_photo_{len(clips)}.jpg"
                    download_file(url, photo_path)
                    video_path = OUTPUT_DIR / f"extra_video_{len(clips)}.mp4"
                    photo_to_video(photo_path, 8, video_path)
                    clips.append(video_path)
                    os.remove(photo_path)
                except:
                    pass

    if clips:
        build_final_video(clips, audio_path, audio_duration, output_path)
    else:
        subprocess.run([
            "ffmpeg", "-f", "lavfi", "-i", "color=c=black:size=1920x1080:rate=30",
            "-i", str(audio_path), "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-c:a", "aac", "-shortest", str(output_path), "-y"
        ], check=True)

    for clip in clips:
        try: os.remove(clip)
        except: pass

def send_cover_suggestion(article, analysis):
    main_person = analysis.get("main_person", "")
    cover_url = None

    if main_person:
        cover_url = get_wikipedia_photo(main_person)

    if not cover_url:
        photos = fetch_pexels_photos(analysis.get("cover_query", "US Capitol"), count=1)
        if photos:
            cover_url = photos[0]

    if cover_url:
        try:
            # Gorseli indir
            img_path = OUTPUT_DIR / "cover_raw.jpg"
            download_file(cover_url, img_path)

            # 1280x720 formatina getir
            cover_path = OUTPUT_DIR / "cover_1280x720.jpg"
            subprocess.run([
                "ffmpeg", "-i", str(img_path),
                "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black",
                str(cover_path), "-y"
            ], check=True, capture_output=True)

            os.remove(img_path)

            # Telegram'a dosya olarak gonder
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            with open(cover_path, "rb") as f:
                requests.post(url, data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "caption": f"Kapak fotografi (1280x720 YouTube formati)\nKisi: {main_person}\n\nYouTube'da manuel yukle!"
                }, files={"photo": f})

            os.remove(cover_path)
        except Exception as e:
            send_telegram(f"Kapak fotografi hatasi: {str(e)}")
    else:
        send_telegram("Kapak fotografi bulunamadi, manuel ekle!")

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

Write an engaging 6-10 minute video script (~800-1200 words).

Structure:
* Hook (30 sec): Start with the most shocking/surprising element. Create immediate tension.
* Introduction (1 min): What happened and why it matters TODAY
* Background (2 min): Context viewers need to understand
* Main story (3-4 min): Full breakdown with details
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
        subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(output_path), "-y"], check=True)
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
        # Analiz
        analysis = detect_people_and_topics(article)
        people = analysis.get("people", [])
        if people:
            send_telegram(f"Haberdeki kisiler: {', '.join(people)}")

        # Hook baslik
        hook_title = generate_hook_title(article)
        send_telegram(f"Hook baslik: *{hook_title}*")

        # Script
        script = generate_script(article, hook_title)
        with open(OUTPUT_DIR / f"script_{timestamp}.txt", "w") as f:
            f.write(script)

        # Ses
        audio_path = OUTPUT_DIR / f"audio_{timestamp}.mp3"
        generate_audio(script, audio_path)

        # Video
        final_video = OUTPUT_DIR / f"final_{timestamp}.mp4"
        create_video(article, audio_path, final_video, analysis)

        # Metadata
        metadata = generate_metadata(article, hook_title)
        with open(OUTPUT_DIR / f"metadata_{timestamp}.json", "w") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        # YouTube'a yukle
        send_telegram(f"YouTube yuklemesi basliyor...")
        import youtube_uploader
        youtube_uploader.upload(str(final_video), metadata)

        # Kapak onerisi
        send_cover_suggestion(article, analysis)

    except Exception as e:
        error_msg = f"Pipeline hatasi: {str(e)}"
        print(error_msg)
        send_telegram(error_msg)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        article = json.loads(sys.argv[1])
        run(article)
