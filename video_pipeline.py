import anthropic
import requests
import subprocess
import os
import json
import time
from datetime import datetime
from pathlib import Path

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

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

def generate_script(article):
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
- Write ONLY the spoken words, no stage directions, no brackets
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
    send_telegram("🎙️ Seslendirme yapılıyor...")
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
            raise Exception(f"ElevenLabs hatası: {response.status_code} - {response.text}")

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

    print(f"✅ Seslendirme tamamlandı")
    return output_path

def create_simple_video(audio_path, title, output_path):
    send_telegram("🎬 Video oluşturuluyor...")
    safe_title = title[:60].replace("'", "\\'").replace(":", "\\:").replace('"', '\\"')
    subprocess.run([
        "ffmpeg",
        "-f", "lavfi", "-i", "color=c=black:size=1920x1080:rate=30",
        "-i", str(audio_path),
        "-vf", f"drawtext=text='{safe_title}'
