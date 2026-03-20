import schedule
import time
import subprocess
from datetime import datetime

def run_news_fetcher():
    print(f"[{datetime.now()}] Haber tarama başlıyor...")
    subprocess.run(["python", "news_fetcher.py"])

def main():
    print("🤖 Scheduler başladı!")
    print("📅 Haberler her 8 saatte bir taranacak (06:00, 14:00, 22:00)")
    
    # Günde 3 kez çalıştır
    schedule.every().day.at("06:00").do(run_news_fetcher)
    schedule.every().day.at("14:00").do(run_news_fetcher)
    schedule.every().day.at("22:00").do(run_news_fetcher)
    
    # Başlarken bir kez hemen çalıştır
    run_news_fetcher()
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
