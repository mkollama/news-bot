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
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    })

def send_telegram_photo(photo_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "photo": photo_url,
        "caption": caption
    })

def detect_people_and_topics(article):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""Analyze this news article and extract key information. Return ONLY valid JSON.

Title: {article['title']}
Summary: {article['summary']}

Return exactly this format:
{{
  "people": ["Person Name 1", "Person Name 2"],
  "main_person": "Most important person in the story",
  "topics": ["topic1", "topic2"],
  "pexels_query": "best search query for stock footage (e.g. 'US Capitol Congress', 'White House Washington', 'courthouse justice')",
  "cover_query": "search query for cover image"
}}

People should be real named individuals mentioned. Topics should be general themes."""
        }]
    )
    try:
        text = response.content[0].text.strip()
        return json.loads(text)
    except:
        return {
            "people": [],
            "main_person": "",
            "topics": ["US politics"],
            "pexels_query": "Washington DC politics",
            "cover_query": "US Capitol"
        }

def get_wikipedia_photo(person_name):
    try:
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "titles": person_name,
            "prop": "pageimages",
            "format": "json",
            "pithumbsize": 500
        }
        response = requests.get(search_url, params=params, timeout=10)
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            thumb = page.get("thumbnail", {})
            if thumb:
                return thumb.get("source")
    except:
        pass
    return None

def fetch_pexels_videos(query, count=5):
    if not PEXELS_API_KEY:
        return []
    headers = {"Authorization": PEXELS_API_KEY}
    response = requests.get(
        "https://api.pexels.com/videos/search",
        headers=headers,
        params={"query": query, "per_page": count, "min_duration": 5}
    )
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
    response = requests.get(
        "https://api.pexels.com/v1/search",
        headers=headers,
        params={"query": query, "per_page": count}
    )
    if response.status_code != 200:
        return []
    photos = response.json().get("photos", [])
    return [p["src"]["large"] for p in photos]

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

def get_video_duration(video_path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)
    ], capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return 8.0

def get_audio_duration(audio_path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)
    ], capture_output=True, text=True)
    return float(result.stdout.strip())

def build_video_from_clips(clips, audio_path, audio_duration, output_path):
    normalized = []
    for i, clip in enumerate(clips):
        norm = OUTPUT_DIR / f"norm_{i}.mp4"
        subprocess.run([
            "ffmpeg", "-i", str(clip),
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
            "-c:v", "libx264", "-r", "30", "-an",
            str(norm), "-y"
        ], check=True, capture_output=True)
        normalized.append(norm)

    total = 0.0
    loop_clips = []
    while total < audio_duration:
        for c in normalized:
            d = get_video_duration(c)
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
        "-c:v", "libx264", "-t", str(audio_duration),
        str(combined), "-y"
    ], check=True, capture_output=True)

    subprocess.run([
        "ffmpeg", "-i", str(combined), "-i", str(audio_path),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        str(output_path), "-y"
    ], check=True, capture_output=True)

    for n in normalized:
        try:
            os.remove(n)
        except:
            pass

def create_video(article, audio_path, output_path, analysis):
    send_telegram("Video olusturuluyor...")

    audio_duration = get_audio_duration(audio_path)
    clips = []

    # 1. Haberdeki kisilerin Wikipedia fotograflari
    people = analysis.get("people", [])
    for i, person in enumerate(people[:4]):
        photo_url = get_wikipedia_photo(person)
        if photo_url:
            try:
                photo_path = OUTPUT_DIR / f"person_{i}.jpg"
                download_file(photo_url, photo_path)
                video_path = OUTPUT_DIR / f"person_video_{i}.mp4"
                photo_to_video(photo_path, 6, video_path)
                clips.append(video_path)
                os.remove(photo_path)
                print(f"Wikipedia fotografi alindi: {person}")
            except Exception as e:
                print(f"Wikipedia hatasi {person}: {e}")

    # 2. Pexels stock video
    pexels_query = analysis.get("pexels_query", "Washington DC politics")
    video_urls = fetch_pexels_videos(pexels_query, count=5)
    for i, url in enumerate(video_urls[:3]):
        try:
            path = OUTPUT_DIR / f"pexels_video_{i}.mp4"
            download_file(url, path)
            clips.append(path)
        except:
            pass

    # 3. Yeterli yoksa Pexels fotograf
    if len(clips) < 3:
        photo_urls = fetch_pexels_photos(pexels_query, count=8)
        for i, url in enumerate(photo_urls[:6]):
            try:
                photo_path = OUTPUT_DIR / f"pexels_photo_{i}.jpg"
                download_file(url, photo_path)
                video_path = OUTPUT_DIR / f"photo_video_{i}.mp4"
                photo_to_video(photo_path, 8, video_path)
                clips.append(video_path)
                os.remove(photo_path)
            except:
                pass

    if clips:
        build_video_from_clips(clips, audio_path, audio_duration, output_path)
    else:
        subprocess.run([
            "ffmpeg", "-f", "lavfi", "-i", "color=c=black:size=1920x1080:rate=30",
            "-i", str(audio_path),
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-c:a", "aac", "-shortest",
            str(output_path), "-y"
        ], check=True)

    for clip in clips:
        try:
            os.remove(clip)
        except:
            pass

def send_cover_suggestion(article, analysis):
    main_person = analysis.get("main_person", "")
    cover_url = None

    if main_person:
        cover_url = get_wikipedia_photo(main_person)

    if cover_url:
        send_telegram_photo(
            cover_url,
            f"Kapak fotografi onerisi: {main_person}\n\nYouTube'da manuel olarak yukle!"
        )
    else:
        cover_query = analysis.get("cover_query", "US Capitol")
        photos = fetch_pexels_photos(cover_query, count=1)
        if photos:
            send_telegram_photo(
                photos[0],
                f"Kapak fotografi onerisi (Pexels)\n\nYouTube'da manuel olarak yukle!"
            )
        else:
            send_telegram("Kapak fotografi bulunamadi, manuel ekle!")

def generate_script(article):
    send_telegram("Script yaziliyor...")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": f"""You are a professional YouTube news channel scriptwriter. Write an engaging 6-10 minute video script about this news story.

NEWS:
Title: {article['title']}
Summary: {article['summary']}
Source: {article['source']}

SCRIPT REQUIREMENTS:
- Duration: 6-10 minutes when read at normal pace (~800-1200 words)
- Style: Professional news anchor, engaging, clear
- Structure:
  * Hook (30 sec): Dramatic opening
  * Introduction (1 min): What happened and why it matters
  * Background (2 min): Context and history
  * Main story (3-4 min): Detailed breakdown
  * Conclusion (30 sec): Summary and call to action

IMPORTANT:
- Write ONLY the spoken words, no stage directions, no brackets
- Use short, clear sentences
- Keep it factual and professional

Write the complete script now:"""
        }]
    )
    return response.content[0].text

def generate_audio(script, output_path):
    send_telegram("Seslendirme yapiliyor...")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    chunks = [script[i:i+4500] for i in range(0, len(script), 4500)]
    audio_files = []

    for i, chunk in enumerate(chunks):
        chunk_path = OUTPUT_DIR / f"audio_chunk_{i}.mp3"
        response = requests.post(url, headers=headers, json={
            "text": chunk,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {
                "stability": 0.75,
                "similarity_boost": 0.75
            }
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

def generate_metadata(article):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""Create YouTube metadata. Return ONLY valid JSON, nothing else, no markdown.

Article: {article['title']}

Return exactly this format:
{{"title": "YouTube title max 70 chars", "description": "2-3 paragraph description with subscribe CTA", "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]}}"""
        }]
    )
    try:
        text = response.content[0].text.strip()
        return json.loads(text)
    except:
        return {
            "title": article['title'][:70],
            "description": f"In this video: {article['title']}\n\nSubscribe for more US political news!",
            "tags": ["US politics", "news", "Trump", "Congress", "Washington"]
        }

def run(article):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    send_telegram(f"Video pipeline basladi!\n\n{article['title']}")

    try:
        analysis = detect_people_and_topics(article)
        people = analysis.get("people", [])
        if people:
            send_telegram(f"Haberdeki kisiler: {', '.join(people)}")

        script = generate_script(article)
        with open(OUTPUT_DIR / f"script_{timestamp}.txt", "w") as f:
            f.write(script)

        audio_path = OUTPUT_DIR / f"audio_{timestamp}.mp3"
        generate_audio(script, audio_path)

        final_video = OUTPUT_DIR / f"final_{timestamp}.mp4"
        create_video(article, audio_path, final_video, analysis)

        metadata = generate_metadata(article)
        with open(OUTPUT_DIR / f"metadata_{timestamp}.json", "w") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        send_telegram(f"Video hazir! Baslik: {metadata['title']}\n\nYouTube yuklemesi basliyor...")
        import youtube_uploader
        youtube_uploader.upload(str(final_video), metadata)

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
