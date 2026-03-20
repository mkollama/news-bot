import os
import json
import requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = "youtube_token.json"
CLIENT_SECRETS_FILE = "client_secrets.json"

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    })

def get_youtube_service():
    """YouTube API servisini başlat"""
    creds = None
    
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=8080)
        
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    
    return build("youtube", "v3", credentials=creds)

def upload(video_path, metadata):
    """Videoyu YouTube'a yükle"""
    send_telegram("📤 YouTube'a yükleniyor...")
    
    try:
        youtube = get_youtube_service()
        
        body = {
            "snippet": {
                "title": metadata["title"],
                "description": metadata["description"],
                "tags": metadata.get("tags", []),
                "categoryId": "25"  # News & Politics
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }
        
        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024*1024*5  # 5MB chunks
        )
        
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"Yükleniyor... %{progress}")
        
        video_id = response["id"]
        video_url = f"https://youtube.com/watch?v={video_id}"
        
        send_telegram(
            f"🎉 *Video yüklendi!*\n\n"
            f"📺 {metadata['title']}\n\n"
            f"🔗 {video_url}\n\n"
            f"⚠️ Kapak fotoğrafını değiştirmeyi unutma!"
        )
        
        print(f"✅ Video yüklendi: {video_url}")
        return video_id
        
    except Exception as e:
        error_msg = f"❌ YouTube yükleme hatası: {str(e)}"
        send_telegram(error_msg)
        raise
