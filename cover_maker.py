import subprocess
import requests
import os
from pathlib import Path

OUTPUT_DIR = Path("output_videos")

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

def download_file(url, output_path):
    try:
        response = requests.get(url, stream=True, timeout=30)
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return output_path
    except:
        pass
    return None

def get_video_screenshot(query, output_path, timestamp=5):
    """YouTube veya C-SPAN'dan video bul ve ekran goruntusu al"""
    try:
        # Once C-SPAN'da ara
        result = subprocess.run([
            "yt-dlp",
            "--no-download",
            "--print", "%(id)s",
            "--playlist-end", "1",
            f"https://www.youtube.com/@CSPAN/search?query={query.replace(' ', '+')}"
        ], capture_output=True, text=True, timeout=30)

        video_id = result.stdout.strip().split("\n")[0].strip()

        # C-SPAN'da bulunamazsa YouTube'da ara
        if not video_id or len(video_id) != 11:
            result = subprocess.run([
                "yt-dlp",
                "--no-download",
                "--print", "%(id)s",
                "--playlist-end", "1",
                "--match-filter", "duration < 3600",
                f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}&sp=EgIYAQ%3D%3D"
            ], capture_output=True, text=True, timeout=30)
            video_id = result.stdout.strip().split("\n")[0].strip()

        if not video_id or len(video_id) != 11:
            return None

        video_url = f"https://www.youtube.com/watch?v={video_id}"

        # Videodan ekran goruntusu al
        temp_video = OUTPUT_DIR / f"bg_temp_{video_id}.mp4"
        dl_result = subprocess.run([
            "yt-dlp",
            "-f", "best[height<=720][ext=mp4]/best[height<=720]/best",
            "--no-playlist",
            "-o", str(temp_video),
            video_url
        ], capture_output=True, text=True, timeout=90)

        if dl_result.returncode != 0 or not temp_video.exists():
            return None

        # Belirli saniyeden ekran goruntusu al
        screenshot_result = subprocess.run([
            "ffmpeg",
            "-ss", str(timestamp),
            "-i", str(temp_video),
            "-frames:v", "1",
            "-update", "1",
            str(output_path), "-y"
        ], capture_output=True)

        os.remove(temp_video)

        if screenshot_result.returncode == 0 and Path(output_path).exists():
            print(f"Ekran goruntusu alindi: {video_id}")
            return output_path

    except Exception as e:
        print(f"Ekran goruntusu hatasi: {e}")
        try:
            if Path(str(OUTPUT_DIR / f"bg_temp_{video_id}.mp4")).exists():
                os.remove(OUTPUT_DIR / f"bg_temp_{video_id}.mp4")
        except:
            pass
    return None

def get_background_query(analysis):
    """Habere gore video arama terimi"""
    drama = analysis.get("drama_type", "").lower()
    main_person = analysis.get("main_person", "")
    people = analysis.get("people", [])

    # Ana kisiyle konuyla alakali arama yap
    topic_keywords = drama + " " + analysis.get("article_title", "")

    if any(w in topic_keywords.lower() for w in ["war", "military", "attack", "bomb", "iran", "missile", "strike"]):
        topic = "military strike attack"
    elif any(w in topic_keywords.lower() for w in ["court", "trial", "judge", "justice", "legal"]):
        topic = "Supreme Court hearing"
    elif any(w in topic_keywords.lower() for w in ["congress", "senate", "vote", "bill"]):
        topic = "Congress Senate vote"
    elif any(w in topic_keywords.lower() for w in ["white house", "president"]):
        topic = "White House press conference"
    elif any(w in topic_keywords.lower() for w in ["protest", "rally", "march"]):
        topic = "protest rally Washington"
    else:
        topic = "Washington DC press conference"

    # Ana kisi varsa onun konusmasini ara
    if main_person:
        return f"{main_person} {topic}"
    elif people:
        return f"{people[0]} {topic}"
    return topic

def calculate_font_size(text, max_width=1200):
    char_count = len(text)
    font_size = 48
    while font_size >= 14:
        if char_count * font_size * 0.58 <= max_width:
            break
        font_size -= 1
    return font_size

def create_cover_single_person(person_photo, bg_photo, safe_title, font_size, strip_y, strip_height, output_path):
    """Tek karakter: arka planda video ekran goruntusu, onde karakter"""
    vf = (
        f"[0:v]scale=1280:720:force_original_aspect_ratio=decrease,"
        f"pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"colorchannelmixer=rr=0.5:gg=0.5:bb=0.5[bg];"
        f"[1:v]scale=500:690:force_original_aspect_ratio=decrease,"
        f"pad=500:690:(ow-iw)/2:(oh-ih)/2:color=black@0[person];"
        f"[bg][person]overlay=740:10[combined];"
        f"[combined]"
        f"drawbox=x=0:y={strip_y}:w=1280:h={strip_height}:color=0xFF0000@0.93:t=fill,"
        f"drawtext=text='{safe_title}':fontcolor=white:fontsize={font_size}:"
        f"x=(w-text_w)/2:y={strip_y+14}:font=DejaVuSans-Bold,"
        f"drawbox=x=0:y=0:w=1280:h=720:color=0xFF0000@0.95:t=8"
    )
    result = subprocess.run([
        "ffmpeg", "-i", str(bg_photo), "-i", str(person_photo),
        "-filter_complex", vf,
        "-frames:v", "1", "-update", "1", str(output_path), "-y"
    ], capture_output=True)
    return result.returncode == 0

def create_cover_two_persons(main_photo, second_photo, safe_title, font_size, strip_y, strip_height, output_path):
    """Iki karakter: solda buyuk ana karakter, sagda kucuk"""
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
        "-filter_complex", vf,
        "-frames:v", "1", "-update", "1", str(output_path), "-y"
    ], capture_output=True)
    return result.returncode == 0

def create_cover_three_persons(main_photo, left_photo, right_photo, safe_title, font_size, strip_y, strip_height, output_path):
    """Uc karakter: ortada buyuk ana karakter, yanlarda kucuk"""
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
        "ffmpeg",
        "-i", str(left_photo), "-i", str(main_photo), "-i", str(right_photo),
        "-filter_complex", vf,
        "-frames:v", "1", "-update", "1", str(output_path), "-y"
    ], capture_output=True)
    return result.returncode == 0

def create_cover(hook_title, analysis, output_path):
    main_person = analysis.get("main_person", "")
    people = analysis.get("people", [])

    safe_title = (hook_title
        .replace("'", "")
        .replace(":", " -")
        .replace('"', '')
        .replace("\\", "")
        .replace("/", " ")
        .replace("%", "percent")
        .upper()
    )

    font_size = calculate_font_size(safe_title)
    strip_height = font_size + 32
    strip_y = 720 - strip_height

    # Tum kisiler icin Wikipedia fotografi indir
    all_people = []
    if main_person:
        all_people.append(main_person)
    for p in people:
        if p not in all_people:
            all_people.append(p)

    person_photos = []
    for i, person in enumerate(all_people[:3]):
        url = get_wikipedia_photo(person)
        if url:
            path = OUTPUT_DIR / f"cover_person_{i}.jpg"
            result = download_file(url, path)
            if result:
                person_photos.append(path)
                print(f"Kapak fotografi: {person}")

    success = False

    if len(person_photos) >= 3:
        success = create_cover_three_persons(
            person_photos[0], person_photos[1], person_photos[2],
            safe_title, font_size, strip_y, strip_height, output_path
        )

    elif len(person_photos) == 2:
        success = create_cover_two_persons(
            person_photos[0], person_photos[1],
            safe_title, font_size, strip_y, strip_height, output_path
        )

    elif len(person_photos) == 1:
        # Arka plan: C-SPAN veya YouTube'dan ekran goruntusu
        bg_query = get_background_query(analysis)
        print(f"Arka plan aranıyor: {bg_query}")
        bg_path = OUTPUT_DIR / "cover_bg.jpg"
        bg_result = get_video_screenshot(bg_query, bg_path)

        if bg_result:
            success = create_cover_single_person(
                person_photos[0], bg_path,
                safe_title, font_size, strip_y, strip_height, output_path
            )

        if not success:
            # Fallback: sadece kisi fotografi tam ekran
            vf = (
                f"scale=1280:720:force_original_aspect_ratio=decrease,"
                f"pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,"
                f"drawbox=x=0:y={strip_y}:w=1280:h={strip_height}:color=0xFF0000@0.93:t=fill,"
                f"drawtext=text='{safe_title}':fontcolor=white:fontsize={font_size}:"
                f"x=(w-text_w)/2:y={strip_y+14}:font=DejaVuSans-Bold,"
                f"drawbox=x=0:y=0:w=1280:h=720:color=0xFF0000@0.95:t=8"
            )
            result = subprocess.run([
                "ffmpeg", "-i", str(person_photos[0]),
                "-vf", vf, "-frames:v", "1", "-update", "1",
                str(output_path), "-y"
            ], capture_output=True)
            success = result.returncode == 0

    # Temizlik
    for p in person_photos:
        try: os.remove(p)
        except: pass
    bg_path = OUTPUT_DIR / "cover_bg.jpg"
    if bg_path.exists():
        try: os.remove(bg_path)
        except: pass

    return output_path if success else None
