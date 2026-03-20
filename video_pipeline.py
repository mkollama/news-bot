import anthropic
import requests
import subprocess
import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

# API Keys
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# ElevenLabs ses ayarları
VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel sesi (doğal İngilizce)

OUTPUT_DIR = Path("output_videos")
OUTPUT_DIR.mkdir(exist_ok=True)

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    })

def generate_script(article):
    """Claude ile 10-15 dakikalık video scripti oluştur"""
    send_telegram("📝 Script yazılıyor...")
    
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": f"""You are a professional YouTube news channel scriptwriter. Write an engaging 10-12 minute video script about this news story.

NEWS:
Title: {article['title']}
Summary: {article['summary']}
Source: {article['source']}

SCRIPT REQUIREMENTS:
- Duration: 10-12 minutes when read at normal pace (~1400-1600 words)
- Style: Professional news anchor, engaging, clear
- Structure:
  * Hook (30 sec): Dramatic opening that grabs attention
  * Introduction (1 min): What happened and why it matters
  * Background (2 min): Context and history
  * Main story (5-6 min): Detailed breakdown of the news
  * Analysis (2 min): What this means going forward
  * Conclusion (30 sec): Summary and call to action

IMPORTANT:
- Write ONLY the spoken words (no stage directions, no [MUSIC], no brackets)
- Use short, clear sentences
- Keep it factual and professional
- Start with a powerful hook sentence

Write the complete script now:"""
        }]
    )
    
    script = response.content[0].text
    print(f"✅ Script yazıldı: {len(script)} karakter")
    return script

def generate_audio(script, output_path):
    """ElevenLabs ile seslendirme oluştur"""
    send_telegram("🎙️ Seslendirme yapılıyor...")
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    
    # ElevenLabs max 5000 karakter alır, scripti böleceğiz
    chunks = [script[i:i+4500] for i in range(0, len(script), 4500)]
    audio_files = []
    
    for i, chunk in enumerate(chunks):
        chunk_path = OUTPUT_DIR / f"audio_chunk_{i}.mp3"
        
        response = requests.post(url, headers=headers, json={
            "text": chunk,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.75,
                "similarity_boost": 0.75,
                "style": 0.5,
                "use_speaker_boost": True
            }
        })
        
        if response.status_code == 200:
            with open(chunk_path, "wb") as f:
                f.write(response.content)
            audio_files.append(str(chunk_path))
            print(f"✅ Ses parçası {i+1}/{len(chunks)} oluşturuldu")
        else:
            print(f"❌ ElevenLabs hatası: {response.status_code} - {response.text}")
            raise Exception(f"ElevenLabs API hatası: {response.status_code}")
    
    # Ses parçalarını birleştir
    if len(audio_files) == 1:
        import shutil
        shutil.copy(audio_files[0], output_path)
    else:
        # ffmpeg ile birleştir
        list_file = OUTPUT_DIR / "audio_list.txt"
        with open(list_file, "w") as f:
            for af in audio_files:
                f.write(f"file '{os.path.abspath(af)}'\n")
        
        subprocess.run([
            "ffmpeg", "-f", "concat", "-safe", "0",
            "-i", str(list_file), "-c", "copy", str(output_path), "-y"
        ], check=True)
        
        # Geçici dosyaları temizle
        for af in audio_files:
            os.remove(af)
        os.remove(list_file)
    
    print(f"✅ Seslendirme tamamlandı: {output_path}")
    return output_path

def fetch_stock_footage(query, duration_seconds, output_path):
    """Pexels'dan stock video indir"""
    PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")
    
    if not PEXELS_API_KEY:
        # Pexels key yoksa siyah ekran oluştur
        create_black_video(duration_seconds, output_path)
        return output_path
    
    headers = {"Authorization": PEXELS_API_KEY}
    response = requests.get(
        "https://api.pexels.com/videos/search",
        headers=headers,
        params={"query": query, "per_page": 5, "min_duration": 10}
    )
    
    if response.status_code == 200:
        videos = response.json().get("videos", [])
        if videos:
            video_url = videos[0]["video_files"][0]["link"]
            video_response = requests.get(video_url, stream=True)
            with open(output_path, "wb") as f:
                for chunk in video_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return output_path
    
    create_black_video(duration_seconds, output_path)
    return output_path

def create_black_video(duration, output_path):
    """Fallback: siyah arka plan video oluştur"""
    subprocess.run([
        "ffmpeg", "-f", "lavfi", "-i", f"color=black:size=1920x1080:rate=30",
        "-t", str(duration), "-c:v", "libx264", str(output_path), "-y"
    ], check=True)

def create_intro_video(article, duration=100):
    """İlk 1.5-2 dakika için intro video oluştur"""
    send_telegram("🎬 Intro video oluşturuluyor...")
    
    output_path = OUTPUT_DIR / "intro.mp4"
    
    # Habere uygun arama terimi
    query = "US Capitol Congress Washington politics"
    if "trump" in article['title'].lower():
        query = "White House Washington DC politics"
    elif "court" in article['title'].lower() or "trial" in article['title'].lower():
        query = "courthouse justice legal"
    
    stock_path = OUTPUT_DIR / "stock_intro.mp4"
    fetch_stock_footage(query, duration, stock_path)
    
    # Başlık overlay ekle
    title = article['title'][:80]
    safe_title = title.replace("'", "\\'").replace(":", "\\:")
    
    subprocess.run([
        "ffmpeg", "-i", str(stock_path),
        "-vf", f"drawtext=text='{safe_title}':fontcolor=white:fontsize=36:x=(w-text_w)/2:y=h-100:box=1:boxcolor=black@0.7:boxborderw=10",
        "-t", str(duration), "-c:a", "copy", str(output_path), "-y"
    ], check=True, capture_output=True)
    
    return output_path

def create_main_video(audio_path, audio_duration):
    """Ana video kısmı için stock footage"""
    send_telegram("🎞️ Ana video hazırlanıyor...")
    
    output_path = OUTPUT_DIR / "main_stock.mp4"
    
    # Genel haber arka planı
    fetch_stock_footage("news broadcast studio professional", int(audio_duration), output_path)
    
    return output_path

def get_audio_duration(audio_path):
    """Ses dosyasının süresini al"""
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)
    ], capture_output=True, text=True)
    return float(result.stdout.strip())

def assemble_final_video(intro_video, main_video, audio_path, output_path):
    """Tüm parçaları birleştir"""
    send_telegram("🔧 Video birleştiriliyor...")
    
    # Intro süresi
    intro_duration = 100  # 1:40 dakika
    
    # Ses süresini al
    audio_duration = get_audio_duration(audio_path)
    main_duration = audio_duration - intro_duration
    
    # Main videoyu doğru süreye kes/döngüye al
    main_looped = OUTPUT_DIR / "main_looped.mp4"
    subprocess.run([
        "ffmpeg", "-stream_loop", "-1", "-i", str(main_video),
        "-t", str(max(main_duration, 60)), "-c:v", "libx264", "-c:a", "copy",
        str(main_looped), "-y"
    ], check=True, capture_output=True)
    
    # İki videoyu birleştir
    combined_video = OUTPUT_DIR / "combined.mp4"
    list_file = OUTPUT_DIR / "video_list.txt"
    
    with open(list_file, "w") as f:
        f.write(f"file '{os.path.abspath(intro_video)}'\n")
        f.write(f"file '{os.path.abspath(main_looped)}'\n")
    
    subprocess.run([
        "ffmpeg", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c:v", "libx264", "-c:a", "copy", str(combined_video), "-y"
    ], check=True, capture_output=True)
    
    # Ses ekle (video + audio birleştir)
    subprocess.run([
        "ffmpeg", "-i", str(combined_video), "-i", str(audio_path),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac",
        "-shortest", str(output_path), "-y"
    ], check=True, capture_output=True)
    
    print(f"✅ Final video oluşturuldu: {output_path}")
    return output_path

def generate_metadata(article, script):
    """YouTube başlık, açıklama ve tag oluştur"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""Create YouTube metadata for this video. Return ONLY JSON.

Article: {article['title']}

Return this exact JSON format:
{{
  "title": "Engaging YouTube title (max 70 chars, with keywords)",
  "description": "YouTube description (2-3 paragraphs, include keywords, add subscribe CTA)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"]
}}"""
        }]
    )
    
    try:
        text = response.content[0].text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except:
        return {
            "title": article['title'][:70],
            "description": f"In this video, we cover: {article['title']}\n\nDon't forget to subscribe for more US political news!",
            "tags": ["US politics", "news", "Trump", "Congress", "Washington"]
        }

def main():
    if len(sys.argv) < 2:
        print("Kullanım: python video_pipeline.py '<article_json>'")
        sys.exit(1)
    
    article = json.loads(sys.argv[1])
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    send_telegram(f"🚀 Video pipeline başladı!\n\n*{article['title']}*")
    
    try:
        # 1. Script oluştur
        script = generate_script(article)
        script_path = OUTPUT_DIR / f"script_{timestamp}.txt"
        with open(script_path, "w") as f:
            f.write(script)
        
        # 2. Seslendirme
        audio_path = OUTPUT_DIR / f"audio_{timestamp}.mp3"
        generate_audio(script, audio_path)
        
        # 3. Intro video (1.5-2 dk)
        intro_video = create_intro_video(article, duration=100)
        
        # 4. Ana video
        audio_duration = get_audio_duration(audio_path)
        main_video = create_main_video(audio_path, audio_duration)
        
        # 5. Final video birleştir
        final_video = OUTPUT_DIR / f"final_{timestamp}.mp4"
        assemble_final_video(intro_video, main_video, audio_path, final_video)
        
        # 6. YouTube metadata
        metadata = generate_metadata(article, script)
        metadata_path = OUTPUT_DIR / f"metadata_{timestamp}.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        send_telegram(
            f"✅ *Video hazır!*\n\n"
            f"📺 Başlık: {metadata['title']}\n\n"
            f"📁 Dosya: {final_video}\n\n"
            f"Şimdi YouTube'a yüklenecek..."
        )
        
        # 7. YouTube'a yükle
        import youtube_uploader
        youtube_uploader.upload(str(final_video), metadata)
        
    except Exception as e:
        error_msg = f"❌ Pipeline hatası: {str(e)}"
        print(error_msg)
        send_telegram(error_msg)
        raise

if __name__ == "__main__":
    main()
