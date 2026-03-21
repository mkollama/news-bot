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
    send_telegram("Script yaziliyor...")
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
- Duration: 10-12 minutes when read at normal pace
- Style: Professional news anchor, engaging, clear
- Structure:
  * Hook (30 sec): Dramatic opening
  * Introduction (1 min): What happened and why it matters
  * Background (2 min): Context and history
  * Main story (5-6 min): Detailed breakdown
  * Analysis (2 min): What this means going forward
  * Conclusion (30 sec): Summary and call to action

IMPORTANT:
- Write ONLY the spoken words, no stage directions, no brackets
- Use short, clear sentences
- Keep it factual and professional

Write the complete script now:"""
        }]
    )
    script = response.content[0].text
    print(f"Script yazildi: {len(script)} karakter")
    return script

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
            print(f"Ses parcasi {i+1}/{len(chunks)} olusturuldu")
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

    print("Seslendirme tamamlandi")
    return output_path

def create_simple_video(audio_path, title, output_path):
    send_telegram("Video olusturuluyor...")
    safe_title = title[:60].replace("'", "").replace(":", "-").replace('"', '')
    subprocess.run([
        "ffmpeg",
        "-f", "lavfi", "-i", "color=c=black:size=1920x1080:rate=30",
        "-i", str(audio_path),
        "-vf", f"drawtext=text='{safe_title}':fontcolor=white:fontsize=40:x=(w-text_w)/2:y=(h-text_h)/2",
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-c:a", "aac",
        "-shortest", str(output_path), "-y"
    ], check=True)
    print(f"Video olusturuldu: {output_path}")
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
        script = generate_script(article)
        script_path = OUTPUT_DIR / f"script_{timestamp}.txt"
        with open(script_path, "w") as f:
            f.write(script)

        audio_path = OUTPUT_DIR / f"audio_{timestamp}.mp3"
        generate_audio(script, audio_path)

        final_video = OUTPUT_DIR / f"final_{timestamp}.mp4"
        create_simple_video(audio_path, article['title'], final_video)

        metadata = generate_metadata(article)
        metadata_path = OUTPUT_DIR / f"metadata_{timestamp}.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        send_telegram(
            f"Video hazir!\n\n"
            f"Baslik: {metadata['title']}\n\n"
            f"YouTube OAuth henuz kurulmadi, manuel yukleme gerekiyor.\n"
            f"Dosya: final_{timestamp}.mp4"
        )

    except Exception as e:
        error_msg = f"Pipeline hatasi: {str(e)}"
        print(error_msg)
        send_telegram(error_msg)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        article = json.loads(sys.argv[1])
        run(article)
