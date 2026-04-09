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
    """Kisi fotografini bul - Wikimedia Commons + Wikipedia"""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"}

    # 1. Wikimedia Commons - en iyi kaynak
    try:
        url = "https://commons.wikimedia.org/w/api.php"
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": f"{person_name} portrait",
            "gsrnamespace": "6",
            "gsrlimit": "5",
            "prop": "imageinfo",
            "iiprop": "url|mime",
            "format": "json"
        }
        response = requests.get(url, params=params, headers=headers, timeout=15)
        if response.status_code == 200 and response.text.strip():
            pages = response.json().get("query", {}).get("pages", {})
            for page in pages.values():
                info = page.get("imageinfo", [{}])[0]
                mime = info.get("mime", "")
                img_url = info.get("url", "")
                if mime.startswith("image/") and img_url and "svg" not in img_url.lower():
                    print(f"Wikimedia bulundu: {person_name}")
                    return img_url
    except Exception as e:
        print(f"Wikimedia hatasi: {e}")

    # 2. Wikipedia API
    try:
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "titles": person_name,
            "prop": "pageimages",
            "format": "json",
            "pithumbsize": 1000
        }
        response = requests.get(url, params=params, headers=headers, timeout=15)
        if response.status_code == 200 and response.text.strip():
            pages = response.json().get("query", {}).get("pages", {})
            for page in pages.values():
                thumb = page.get("thumbnail", {})
                if thumb:
                    print(f"Wikipedia bulundu: {person_name}")
                    return thumb.get("source")
    except Exception as e:
        print(f"Wikipedia hatasi: {e}")

    # 3. YouTube thumbnail - C-SPAN oncelikli
    try:
        # C-SPAN ara
        result = subprocess.run([
            "yt-dlp", "--no-download",
            "--print", "%(id)s\t%(thumbnail)s",
            "--playlist-end", "2",
            f"https://www.youtube.com/@CSPAN/search?query={person_name.replace(' ', '+')}"
        ], capture_output=True, text=True, timeout=20)

        for line in result.stdout.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 2:
                video_id = parts[0].strip()
                thumbnail = parts[1].strip()
                if video_id and len(video_id) == 11 and thumbnail:
                    print(f"C-SPAN thumbnail: {person_name}")
                    return thumbnail

        # Genel YouTube ara
        result2 = subprocess.run([
            "yt-dlp", "--no-download",
            "--print", "%(id)s\t%(thumbnail)s",
            "--playlist-end", "3",
            "--match-filter", "duration < 1800",
            f"https://www.youtube.com/results?search_query={person_name.replace(' ', '+')}+interview&sp=EgIYAQ%3D%3D"
        ], capture_output=True, text=True, timeout=20)

        for line in result2.stdout.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 2:
                video_id = parts[0].strip()
                thumbnail = parts[1].strip()
                if video_id and len(video_id) == 11 and thumbnail:
                    print(f"YouTube thumbnail: {person_name}")
                    return thumbnail
    except Exception as e:
        print(f"YouTube hatasi: {e}")

    return None

def download_file(url, output_path):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"}
        response = requests.get(url, stream=True, timeout=30, headers=headers)
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return output_path
    except Exception as e:
        print(f"Indirme hatasi: {e}")
    return None

def calculate_font_size(text, max_width=1200):
    char_count = len(text)
    font_size = 48
    while font_size >= 14:
        if char_count * font_size * 0.58 <= max_width:
            break
        font_size -= 1
    return font_size

def make_cover_one(photo, safe_title, font_size, strip_y, strip_height, output_path):
    vf = (
        f"scale=1280:720:force_original_aspect_ratio=decrease,"
        f"pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"drawbox=x=0:y={strip_y}:w=1280:h={strip_height}:color=0xFF0000@0.93:t=fill,"
        f"drawtext=text='{safe_title}':fontcolor=white:fontsize={font_size}:"
        f"x=(w-text_w)/2:y={strip_y+14}:font=DejaVuSans-Bold,"
        f"drawbox=x=0:y=0:w=1280:h=720:color=0xFF0000@0.95:t=8"
    )
    result = subprocess.run([
        "ffmpeg", "-i", str(photo), "-vf", vf,
        "-frames:v", "1", "-update", "1", str(output_path), "-y"
    ], capture_output=True)
    return result.returncode == 0

def make_cover_two(main_photo, second_photo, safe_title, font_size, strip_y, strip_height, output_path):
    vf = (
        f"[0:v]scale=760:680:force_original_aspect_ratio=decrease,"
        f"pad=760:680:(ow-iw)/2:(oh-ih)/2:color=black[main];"
        f"[1:v]scale=480:380:force_original_aspect_ratio=decrease,"
        f"pad=480:380:(ow-iw)/2:(oh-ih)/2:color=black[second];"
        f"color=black:s=1280x720[bg];"
        f"[bg][main]overlay=0:20[bg2];"
        f"[bg2][second]overlay=790:150[combined];"
        f"[combined]"
        f"drawbox=x=0:y={strip_y}:w=1280:h={strip_height}:color=0xFF0000@0.93:t=fill,"
        f"drawtext=text='{safe_title}':fontcolor=white:fontsize={font_size}:"
        f"x=(w-text_w)/2:y={strip_y+14}:font=DejaVuSans-Bold,"
        f"drawbox=x=0:y=0:w=1280:h=720:color=0xFF0000@0.95:t=8"
    )
    result = subprocess.run([
        "ffmpeg", "-i", str(main_photo), "-i", str(second_photo),
        "-filter_complex", vf, "-frames:v", "1", "-update", "1", str(output_path), "-y"
    ], capture_output=True)
    return result.returncode == 0

def make_cover_three(main_photo, left_photo, right_photo, safe_title, font_size, strip_y, strip_height, output_path):
    vf = (
        f"[0:v]scale=380:350:force_original_aspect_ratio=decrease,"
        f"pad=380:350:(ow-iw)/2:(oh-ih)/2:color=black[left];"
        f"[1:v]scale=520:600:force_original_aspect_ratio=decrease,"
        f"pad=520:600:(ow-iw)/2:(oh-ih)/2:color=black[center];"
        f"[2:v]scale=380:350:force_original_aspect_ratio=decrease,"
        f"pad=380:350:(ow-iw)/2:(oh-ih)/2:color=black[right];"
        f"color=black:s=1280x720[bg];"
        f"[bg][left]overlay=0:100[bg2];"
        f"[bg2][center]overlay=380:0[bg3];"
        f"[bg3][right]overlay=900:100[combined];"
        f"[combined]"
        f"drawbox=x=0:y={strip_y}:w=1280:h={strip_height}:color=0xFF0000@0.93:t=fill,"
        f"drawtext=text='{safe_title}':fontcolor=white:fontsize={font_size}:"
        f"x=(w-text_w)/2:y={strip_y+14}:font=DejaVuSans-Bold,"
        f"drawbox=x=0:y=0:w=1280:h=720:color=0xFF0000@0.95:t=8"
    )
    result = subprocess.run([
        "ffmpeg", "-i", str(left_photo), "-i", str(main_photo), "-i", str(right_photo),
        "-filter_complex", vf, "-frames:v", "1", "-update", "1", str(output_path), "-y"
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

        safe_title = (hook_title
            .replace("'", "").replace(":", " -").replace('"', '')
            .replace("\\", "").replace("/", " ").replace("%", "percent")
            .upper()
        )

        font_size = calculate_font_size(safe_title)
        strip_height = font_size + 32
        strip_y = 720 - strip_height

        all_people = []
        if main_person:
            all_people.append(main_person)
        for p in people:
            if p not in all_people:
                all_people.append(p)

        send_message(f"Fotograflar aranıyor: {', '.join(all_people)}")

        person_photos = []
        for i, person in enumerate(all_people[:3]):
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

        cover_path = OUTPUT_DIR / "cover_retry.jpg"
        success = False

        if len(person_photos) >= 3:
            success = make_cover_three(
                person_photos[0], person_photos[1], person_photos[2],
                safe_title, font_size, strip_y, strip_height, cover_path
            )
        elif len(person_photos) == 2:
            success = make_cover_two(
                person_photos[0], person_photos[1],
                safe_title, font_size, strip_y, strip_height, cover_path
            )
        elif len(person_photos) == 1:
            success = make_cover_one(
                person_photos[0],
                safe_title, font_size, strip_y, strip_height, cover_path
            )
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
