# Modüller Arası Veri Sözleşmesi

Bu belge, üç modülün (🧠 DJ Brain, 🎙️ Voice & Broadcast, 🎵 Music & Platform) birbirine gönderdiği verileri tanımlar. Modeller `backend/app/contracts/` altında Pydantic v2 ile yazılmıştır; bu belgedeki JSON örnekleri `backend/tests/test_contracts.py` içindeki örneklerle aynıdır.

Genel kurallar:

- Tüm modeller bilinmeyen alanı reddeder (`extra="forbid"`).
- Enum değerleri JSON'da küçük harfli düz metindir (`"happy"`, `"song_intro"`).
- Tarih/saat alanları saat dilimi (timezone) içermek zorundadır.
- Duygu listesi yalnızca `emotion.py` içinde tanımlıdır.
- Metinler İngilizcedir (radyo içeriği).

## Özet

| Model | Üreten | Kullanan |
|---|---|---|
| `Emotion` | — (ortak) | DJ Brain, Voice & Broadcast |
| `Track` | Music & Platform | DJ Brain, Voice & Broadcast |
| `AnnouncementSpec` | DJ Brain | Voice & Broadcast |
| `TrackSegment` | Music & Platform | Voice & Broadcast |
| `AnnouncementSegment` | DJ Brain (spec), Voice & Broadcast (`audio_url`) | Voice & Broadcast |
| `BulletinSegment` | DJ Brain | Voice & Broadcast |
| `ListenerContext` | Music & Platform | DJ Brain |
| `RequestIntent` | DJ Brain | Music & Platform |
| `SongRequest` | Music & Platform | DJ Brain, Voice & Broadcast |

## Emotion

Anın veya anonsun duygusu. Değerler: `happy`, `sad`, `excited`, `calm`, `serious`, `surprised`, `neutral`. DJ Brain seçer, Voice & Broadcast sesin tonunu buna göre ayarlar.

## Track

Bir müzik parçası. Müzik kataloğundan Music & Platform üretir. Dosya yolu bilerek yoktur (veritabanının iç detayı). `valence` ve `arousal` 0–1 arasıdır ve müzik analizi (S4) gelince dolar; o zamana kadar `null` olabilir. Lisans bilgisi her parçada zorunludur.

```json
{
  "id": "trk_001",
  "title": "Morning Rain",
  "artist": "Some Artist",
  "duration_seconds": 184.5,
  "license": "CC BY 4.0",
  "license_url": "https://creativecommons.org/licenses/by/4.0/",
  "source_url": "https://example.org/tracks/morning-rain",
  "mood_tags": [
    "calm",
    "acoustic"
  ],
  "valence": 0.62,
  "arousal": 0.25
}
```

## AnnouncementSpec

DJ'in ne söyleyeceği, hangi duyguyla ve yaklaşık kaç saniyede söyleyeceği. DJ Brain üretir, Voice & Broadcast seslendirir. `kind` değerleri: `song_intro`, `back_announce`, `request_shoutout`, `greeting`, `bulletin_intro`. `target_seconds` 3–120 arasıdır. `language` şimdilik yalnızca `"en"`.

```json
{
  "kind": "song_intro",
  "text": "Here is a gentle one to start your morning.",
  "emotion": "calm",
  "target_seconds": 8.0,
  "language": "en"
}
```

## Segment

Yayın kuyruğundaki bir öğe. `type` alanına göre üç türden biridir (`track`, `announcement`, `bulletin`). Her türün ortak alanları:

- `id`: Yayın planlayıcı kuyruktaki parçaları bu id ile takip eder.
- `duration_seconds` (opsiyonel): Planlayıcı sıralama ve zamanlamada kullanır. Bilinmiyorsa `null`.

### TrackSegment

Çalınacak şarkı. Music & Platform üretir. `selection_reason` "neden bu şarkı?" sorusunun cevabıdır. `request_id` şarkı bir dinleyici isteğiyle çalıyorsa dolar; planlayıcı istek anonsunu buna göre bağlar.

```json
{
  "type": "track",
  "id": "seg_001",
  "duration_seconds": 184.5,
  "track_id": "trk_001",
  "selection_reason": "Matches your calm morning mood.",
  "request_id": "req_001"
}
```

### AnnouncementSegment

DJ anonsu. `spec`'i DJ Brain üretir; Voice & Broadcast sesi üretince `audio_url`'i doldurur (öncesinde `null`).

```json
{
  "type": "announcement",
  "id": "seg_002",
  "duration_seconds": 8.0,
  "spec": {
    "kind": "song_intro",
    "text": "Here is a gentle one to start your morning.",
    "emotion": "calm",
    "target_seconds": 8.0,
    "language": "en"
  },
  "audio_url": "/audio/seg_002.mp3"
}
```

### BulletinSegment

Haber bülteni. DJ Brain üretir. En az bir madde içermelidir; her madde kaynak adı, kaynak bağlantısı ve yayın zamanı taşır.

```json
{
  "type": "bulletin",
  "id": "seg_003",
  "duration_seconds": 45.0,
  "items": [
    {
      "title": "City opens new bike lanes",
      "summary": "Ten kilometers of lanes opened downtown today.",
      "source_name": "Example News",
      "source_url": "https://example.org/news/bike-lanes",
      "published_at": "2025-01-15T08:30:00Z"
    }
  ]
}
```

## ListenerContext

Dinleyiciye kişisel bir yayın üretmek için kullanılan bağlam. Music & Platform doldurur, DJ Brain kullanır.

> **Uyarı:** Bu model LLM'e gönderilebilir. Ad, e-posta, telefon gibi kişisel veri **kesinlikle** içermez; fazladan alan gelirse reddedilir.

```json
{
  "local_time": "2025-01-15T09:00:00+03:00",
  "city": "Istanbul",
  "weather_summary": "Light rain, 8°C",
  "preferred_genres": [
    "jazz",
    "ambient"
  ],
  "news_topics": [
    "technology",
    "science"
  ]
}
```

## RequestIntent ve SongRequest

Dinleyicinin yazılı şarkı isteği. `SongRequest`'i Music & Platform tutar (istek kuyruğu); DJ Brain yazıyı anlayıp `RequestIntent` çıkarır. `status` değerleri: `received`, `accepted`, `rejected`, `played`. Reddedilirse `reject_reason` dolar; kabul edilirse `estimated_play_time` verilebilir.

`RequestIntent`:

```json
{
  "song_title": "Morning Rain",
  "artist": null,
  "mood": "calm",
  "message": "For my sister's birthday"
}
```

`SongRequest`:

```json
{
  "id": "req_001",
  "session_id": "ses_001",
  "raw_text": "Play Morning Rain for my sister's birthday",
  "intent": {
    "song_title": "Morning Rain",
    "artist": null,
    "mood": "calm",
    "message": "For my sister's birthday"
  },
  "status": "accepted",
  "reject_reason": null,
  "estimated_play_time": "2025-01-15T09:10:00+03:00"
}
```

## Akış

1. **Music & Platform → `TrackSegment`:** Dinleyici için şarkı seçer; `track_id`, `selection_reason` ve (istekse) `request_id` ile segmenti oluşturur.
2. **DJ Brain → `AnnouncementSpec`:** `ListenerContext`, şarkı ve istek bilgisine bakıp anonsun metnini, duygusunu ve süresini belirler. Haber gerekiyorsa `BulletinSegment` üretir.
3. **Voice & Broadcast:** `AnnouncementSpec`'ten sesi üretir, `AnnouncementSegment.audio_url`'i doldurur ve `Segment` kuyruğunu kullanıcı başına sıraya dizip yayınlar.

```
Music & Platform --TrackSegment--------------DJ Brain ---------AnnouncementSpec/Bulletin---> Voice & Broadcast --> Segment kuyruğu --> yayın
```
