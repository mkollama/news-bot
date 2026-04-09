import sys
import os
import json
import requests
import subprocess
from pathlib import Path

os.chdir("/app")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
OUTPUT_DIR = Path("output_videos")
OUTPUT_DIR.mkdir(exist_ok=True)

def send_photo(photo_path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    with open(photo_path, "rb") as f:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption}, files={"photo": f}, timeout=30)

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=10)

def get_person_photo(person_name):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"}

    # 1. Wikipedia
    try:
        params = {"action": "query", "titles": person_name, "prop": "pageimages", "format": "json", "pithumbsize": 1000}
        r = requests.get("https://en.wikipedia.org/w/api.php", params=params, headers=headers, timeout=15)
        if r.status_code == 200 and r.text.strip():
            pages = r.json().get("query", {}).get("pages", {})
            for page in pages.values():
                if str(page.get("pageid", -1)) != "-1":
                    thumb = page.get("thumbnail", {})
                    if thumb:
                        print(f"Wikipedia: {person_name}")
                        return thumb.get("source")
    except Exception as e:
        print(f"Wikipedia hatasi: {e}")

    # 2. C-SPAN thumbnail
    try:
        result = subprocess.run([
            "yt-dlp", "--no-download",
            "--print", "%(id)s\t%(thumbnail)s",
            "--playlist-end", "2",
            f"https://www.youtube.com/@CSPAN/search?query={person_name.replace(' ', '+')}"
        ], capture_output=True, text=True, timeout=20)
        for line in result.stdout.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 2:
                vid = parts[0].strip()
                thumb = parts[1].strip()
                if vid and len(vid) == 11 and thumb:
                    print(f"C-SPAN: {person_name}")
                    return thumb
    except Exception as e:
        print(f"C-SPAN hatasi: {e}")

    # 3. YouTube thumbnail
    try:
        result = subprocess.run([
            "yt-dlp", "--no-download",
            "--print", "%(id)s\t%(thumbnail)s",
            "--playlist-end", "3",
            "--match-filter", "duration < 1800",
            f"https://www.youtube.com/results?search_query={person_name.replace(' ', '+')}+interview+2024&sp=EgIYAQ%3D%3D"
        ], capture_output=True, text=True, timeout=20)
        for line in result.stdout.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 2:
                vid = parts[0].strip()
                thumb = parts[1].strip()
                if vid and len(vid) == 11 and thumb:
                    print(f"YouTube: {person_name}")
                    return thumb
    except Exception as e:
        print(f"YouTube hatasi: {e}")

    return None

def download_file(url, output_path):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"}
        r = requests.get(url, stream=True, timeout=30, headers=headers)
        if r.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            return output_path
    except Exception as e:
        print(f"Indirme hatasi: {e}")
    return None

def split_title(hook_title):
    """Basliği 3 satira bol - sari / beyaz / kirmizi"""
    words = hook_title.upper().split()
    n = len(words)

    if n <= 2:
        return words[0], "", " ".join(words[1:]) if len(words) > 1 else ""
    elif n <= 4:
        mid = n // 2
        return " ".join(words[:mid]), " ".join(words[mid:]), ""
    elif n <= 6:
        return " ".join(words[:2]), " ".join(words[2:4]), " ".join(words[4:])
    else:
        # Uzun baslik - ilk 2, orta 3, kalan
        return " ".join(words[:2]), " ".join(words[2:5]), " ".join(words[5:])

def font_size_for(text, max_w=310):
    if not text:
        return 0
    fs = 62
    while fs > 18:
        if len(text) * fs * 0.55 <= max_w:
            break
        fs -= 2
    return fs

def build_cover(left_photo, right_photo, hook_title, output_path):
    """2 kisi: ChatGPT stili - sol/sag yuz, ortada sari/beyaz/kirmizi yazi"""
    line1, line2, line3 = split_title(hook_title)

    fs1 = font_size_for(line1, 310)
    fs2 = font_size_for(line2, 310)
    fs3 = font_size_for(line3, 310)

    text_x = 478
    text_w = 340

    # Y pozisyonlari - dikey ortala
    total_h = fs1 + (fs2 + 15 if line2 else 0) + (fs3 + 40 if line3 else 0)
    start_y = max(120, (660 - total_h) // 2)
    y1 = start_y
    y2 = y1 + fs1 + 18
    y3 = y2 + (fs2 + 35 if line2 else 0)

    filters = [
        # Sol fotograf
        "[0:v]scale=520:720:force_original_aspect_ratio=decrease,"
        "pad=520:720:0:(oh-ih)/2:color=0x0d1117[left];",
        # Sag fotograf
        "[1:v]scale=520:720:force_original_aspect_ratio=decrease,"
        "pad=520:720:(ow-iw):(oh-ih)/2:color=0x0d1117[right];",
        # Koyu arka plan
        "color=0x0d1117:s=1280x720[bg];",
        "[bg][left]overlay=0:0[bg2];",
        "[bg2][right]overlay=760:0[combined];",
        # Ortada karanlik overlay
        f"[combined]drawbox=x={text_x}:y=0:w={text_w}:h=720:color=0x0d1117@0.80:t=fill,",
        # Sag ust BREAKING NEWS etiketi
        "drawbox=x=910:y=22:w=350:h=58:color=0xCC0000:t=fill,",
        "drawtext=text='BREAKING NEWS':fontcolor=white:fontsize=30:x=922:y=36:font=DejaVuSans-Bold,",
    ]

    # Satir 1 - SARI
    if line1:
        safe1 = line1.replace("'", "").replace("\\", "")
        filters.append(f"drawtext=text='{safe1}':fontcolor=0xFFDD00:fontsize={fs1}:x={text_x+12}:y={y1}:font=DejaVuSans-Bold,")

    # Satir 2 - BEYAZ
    if line2:
        safe2 = line2.replace("'", "").replace("\\", "")
        filters.append(f"drawtext=text='{safe2}':fontcolor=white:fontsize={fs2}:x={text_x+12}:y={y2}:font=DejaVuSans-Bold,")

    # Satir 3 - KIRMIZI KUTU icinde
    if line3:
        safe3 = line3.replace("'", "").replace("\\", "")
        filters.append(f"drawbox=x={text_x}:y={y3-8}:w={text_w}:h={fs3+28}:color=0xCC0000:t=fill,")
        filters.append(f"drawtext=text='{safe3}':fontcolor=white:fontsize={fs3}:x={text_x+12}:y={y3+6}:font=DejaVuSans-Bold")

    # Son virgulu kaldir
    filter_str = "".join(filters).rstrip(",")

    cmd = [
        "ffmpeg",
        "-i", str(left_photo),
        "-i", str(right_photo),
        "-filter_complex", filter_str,
        "-frames:v", "1", "-update", "1",
        str(output_path), "-y"
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print(f"ffmpeg hatasi: {result.stderr.decode()[-300:]}")
    return result.returncode == 0

def build_cover_one(photo, hook_title, output_path):
    """1 kisi: tam ekran, alt kirmizi serit"""
    safe_title = (hook_title.replace("'", "").replace(":", " -")
        .replace('"', '').replace("\\", "").replace("/", " ").upper())

    char_count = len(safe_title)
    font_size = 48
    while font_size >= 14:
        if char_count * font_size * 0.58 <= 1200:
            break
        font_size -= 1

    strip_h = font_size + 32
    strip_y = 720 - strip_h

    vf = (
        f"scale=1280:720:force_original_aspect_ratio=decrease,"
        f"pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0x0d1117,"
        f"drawbox=x=0:y={strip_y}:w=1280:h={strip_h}:color=0xCC0000@0.93:t=fill,"
        f"drawtext=text='{safe_title}':fontcolor=white:fontsize={font_size}:"
        f"x=(w-text_w)/2:y={strip_y+14}:font=DejaVuSans-Bold,"
        f"drawbox=x=0:y=0:w=1280:h=720:color=0xCC0000@0.95:t=8"
    )
    result = subprocess.run([
        "ffmpeg", "-i", str(photo), "-vf", vf,
        "-frames:v", "1", "-update", "1", str(output_path), "-y"
    ], capture_output=True)
    return result.returncode == 0

if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            send_message("Kullanim hatasi!")
            sys.exit(1)

        data = json.loads(sys.argv[1])
        hook_title = data.get("hook_title", "")
        analysis = data.get("analysis", {})
        main_person = analysis.get("main_person", "")
        people = analysis.get("people", [])

        all_people = []
        if main_person:
            all_people.append(main_person)
        for p in people:
            if p not in all_people:
                all_people.append(p)

        send_message(f"Fotograflar aranıyor: {', '.join(all_people[:3])}")

        person_photos = []
        for i, person in enumerate(all_people[:2]):
            photo_url = get_person_photo(person)
            if photo_url:
                path = OUTPUT_DIR / f"cp_{i}.jpg"
                result = download_file(photo_url, path)
                if result:
                    person_photos.append(path)
                    send_message(f"✅ {person}")
                else:
                    send_message(f"❌ {person} indirilemedi")
            else:
                send_message(f"❌ {person} bulunamadi")

        cover_path = OUTPUT_DIR / "cover_final.jpg"
        success = False

        if len(person_photos) >= 2:
            success = build_cover(
                person_photos[0], person_photos[1],
                hook_title, cover_path
            )
        elif len(person_photos) == 1:
            success = build_cover_one(person_photos[0], hook_title, cover_path)
        else:
            send_message("Hic fotografi bulunamadi!")

        for p in person_photos:
            try: os.remove(p)
            except: pass

        if success and cover_path.exists():
            send_photo(str(cover_path), f"Kapak fotografi\n{hook_title}\n\nYouTube'da manuel yukle!")
            try: os.remove(cover_path)
            except: pass
        elif len(person_photos) > 0:
            send_message("ffmpeg kapak olusturamadi!")

    except Exception as e:
        import traceback
        try:
            send_message(f"HATA: {str(e)}\n{traceback.format_exc()[-200:]}")
        except:
            print(f"Hata: {e}")
