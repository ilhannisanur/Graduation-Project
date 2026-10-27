# Yayın planlayıcı (#9)

Her dinleyici için **şarkı → anons → şarkı** sırasını kuran yayın omurgası.

* Sıradaki şarkıyı Music'ten (#11) alır.
* Anonsun ne söyleyeceğini yönetmenden (#6) alır.
* Anonsun sesini Speech servisinden (#8) alır.
* Bir sonraki parçayı **önceden hazırlar**. Anons hazır değilse sessizlik yerine şarkıya geçer.

S2'de oynatıcı `GET /api/sessions/{id}/next` ile sıradaki parçayı çeker. S3'te bu yapının yerini kullanıcı başına HLS akışı (#14) alacak; planlayıcının çekirdeği aynı kalır.

## Dosyalar

| Dosya | Görev |
|---|---|
| `models.py` | Girdi modelleri (`TrackInfo`, `AnnouncementPlan`, `SpeechAudio`) ve oynatıcıya giden modeller (`QueuedTrack`, `QueuedAnnouncement`, `NextSegmentResponse`) |
| `ports.py` | Diğer modüllerden beklenen üç arayüz: `MusicSource`, `AnnouncementDirector`, `SpeechSynthesizer` |
| `planner.py` | Oturumlar, blok kuyruğu, önceden hazırlama, sessizlik koruması |
| `router.py` | HTTP uçları |
| `wiring.py` | Uygulamadaki tek planlayıcı örneği; #12'de gerçek servislerle bağlanır |
| `adapters.py` | Speech servisine HTTP adaptörü |

Testler `backend/tests/test_planner.py` içinde. Sahte servisler sadece orada tanımlı.

## Nasıl çalışır?

Planlayıcı her oturum için **blok** hazırlar. Blok, bir şarkı ve isteğe bağlı olarak onu tanıtan bir anonstan oluşur:

```
blok 0: [şarkı A]
blok 1: [anons "...sırada B"] [şarkı B]
blok 2: [anons "...sırada C"] [şarkı C]
```

1. **Arka planda hazırlık başlar.** `/next` bir parça verdiği anda bir sonraki blok hazırlanmaya başlar.
2. **Önce şarkı seçilir.** Bu adım hızlıdır.
3. **Sonra anons hazırlanır.** Yönetmen metni yazar, Speech servisi seslendirir. Bu adım yavaştır ama şarkı çalarken (~3 dakika) arka planda yapılır.
4. **Sıradaki parça hazır olur.** Oynatıcı bir sonraki parçayı istediğinde parça normalde hazırdır.

`songs_per_announcement` ayarı, iki anons arasında kaç şarkı çalınacağını belirler (gereksinim 12). Varsayılan değer 1'dir.

## Sessizlik koruması (gereksinim 8)

| Durum | Ne olur |
|---|---|
| Anons henüz hazır değil | Anons atlanır, şarkı çalınır (`announcement_skipped: "announcement not ready"`) |
| Yönetmen veya Speech hata verdi | Anons atlanır, şarkı çalınır (`"announcement failed"`) |
| Music servisi cevap vermiyor | Son çalınan şarkılardan biri tekrar çalınır (ama az önce çalan değil) |
| Hiç şarkı yok | `503 No song available right now` |

`/next` **asla Speech servisini beklemez.** Bekleme süresi `announcement_wait_s` ayarıyla belirlenir; varsayılanı 0'dır. Bu davranış `test_no_silence_*` testleriyle gösterildi.

## API

| Uç | Açıklama |
|---|---|
| `POST /api/sessions` | Oturum açar. Gövde isteğe bağlıdır: `{"user_id": "guest"}`. Yanıt `201 {"session_id", "user_id"}` |
| `GET /api/sessions/{id}/next` | Şimdi çalınacak parçayı döner |
| `DELETE /api/sessions/{id}` | Oturumu kapatır (204) |

Hata kodları:

* `404`: oturum yok ya da süresi doldu. Boşta kalan oturumlar 2 saat sonra kapanır.
* `503`: çalınacak şarkı yok, ya da planlayıcı henüz bağlanmadı (#12 öncesi).

### `/next` yanıt biçimi (#10 ile netleştirilecek öneri)

Şarkı:

```json
{
  "session_id": "6f1c...",
  "position": 3,
  "segment": {
    "kind": "track",
    "segment_id": "a1b2c3d4e5f6",
    "track_id": "42",
    "title": "Rainy Streets",
    "artist": "Some Artist",
    "license": "CC BY 4.0",
    "reason": null,
    "duration_s": 183.0,
    "audio_url": "/api/tracks/42/audio"
  },
  "announcement_skipped": null
}
```

Anons:

```json
{
  "session_id": "6f1c...",
  "position": 2,
  "segment": {
    "kind": "announcement",
    "segment_id": "f6e5d4c3b2a1",
    "text": "It's a rainy evening... up next, Rainy Streets.",
    "emotion": "calm",
    "duration_s": 11.4,
    "audio_url": "http://localhost:8001/audio/3f2a.wav",
    "introduces_track_id": "42"
  },
  "announcement_skipped": null
}
```

Oynatıcı için kurallar:

* `kind` alanına göre arayüzde şarkı ya da anons gösterilir.
* `audio_url` her zaman çalınabilir bir adrestir.
* Bir parça bitince `/next` tekrar çağrılır.
* Şarkı sesi #42'deki `GET /api/tracks/{id}/audio` ucundan gelir. Kontratlardaki `TrackSegment` ses adresi içermediği için adresi planlayıcı ekler.

## Kişisel veri

Yönetmene giden `AnnouncementRequest` içinde kullanıcı bilgisi yoktur; sadece önceki ve sonraki şarkı vardır. Kişisel veri LLM'e gitmez.

## Entegrasyon (#12) kontrol listesi

1. **Music adaptörü.** #11'in "sıradaki şarkı" fonksiyonunu çağıran ve sonucu `TrackInfo`'ya çeviren bir sınıf yaz. Sınıf `MusicSource` arayüzüne uymalı.
2. **Yönetmen adaptörü.** #6'nın yönetmenini çağıran ve sonucu `AnnouncementPlan`'a çeviren bir sınıf yaz. Sınıf `AnnouncementDirector` arayüzüne uymalı.
3. **Speech adaptörü.** `HttpSpeechSynthesizer(base_url=<Speech servisi adresi>)` kullan.
4. **Uygulamaya bağla.** Uygulama açılırken:
   ```python
   configure_planner(BroadcastPlanner(music, director, speech))
   ```
   Kapanırken: `await shutdown_planner()`
5. **httpx bağımlılığı.** `httpx` backend'in ana bağımlılıklarında yoksa ekle. Bu ortak bir dosya; küçük bir PR yeterli.
