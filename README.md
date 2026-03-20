# 🤖 US News YouTube Bot

Otomatik haber takip ve YouTube video üretim sistemi.

## Nasıl Çalışır?

1. Her 8 saatte bir ABD siyaseti haberlerini tarar
2. Claude ile en ilginç 3-5 haberi seçer
3. Telegram'a haber listesi gönderir
4. Sen bir numara seçersin
5. Sistem otomatik olarak:
   - 10-12 dakikalık script yazar
   - ElevenLabs ile seslendirir
   - Stock footage ile video oluşturur
   - YouTube'a yükler
6. Kapak fotoğrafını kendin değiştirirsin

## Kurulum

### 1. Environment Variables (Railway'de ayarla)

```
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id
ANTHROPIC_API_KEY=your_anthropic_key
ELEVENLABS_API_KEY=your_elevenlabs_key
PEXELS_API_KEY=your_pexels_key (opsiyonel)
```

### 2. YouTube OAuth

`client_secrets.json` dosyasını Railway'e yükle.
İlk çalıştırmada YouTube'u authorize et.

### 3. Deploy

Railway'de bu repo'yu deploy et, otomatik başlar.

## Dosya Yapısı

```
├── main.py              # Ana başlangıç noktası
├── scheduler.py         # Zamanlayıcı (8 saatte bir)
├── news_fetcher.py      # Haber tarama + Claude filtreleme
├── telegram_bot.py      # Telegram mesaj dinleyici
├── video_pipeline.py    # Script + Ses + Video üretimi
├── youtube_uploader.py  # YouTube'a yükleme
├── requirements.txt     # Python bağımlılıkları
└── Procfile             # Railway konfigürasyonu
```
