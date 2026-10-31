# M1 entegrasyonu: ilk çalışan AI radyo (#12)

Bu belge, M1'de birleştirilen parçaların nasıl bağlandığını, bir parça eksikken ne olduğunu ve teslimden önce yapılacak kontrolleri anlatır. Kurulum adımları kök [README](../README.md) dosyasındadır (adım 1–7).

## Zincir

```
Tarayıcı (web, #10)
  │  POST /api/sessions, GET /api/sessions/{id}/next
  ▼
Backend (FastAPI, 8000)
  └─ Yayın planlayıcı (#9) ── kullanıcı başına sıra: şarkı → anons → şarkı
       ├─ müzik:    CatalogMusicSource (#11)     → Postgres'teki katalogdan şarkı seçer
       ├─ yönetmen: SongIntroDirector (#6)       → anons metnini ve duygusunu LLM ile yazar
       └─ ses:      SpeechClientSynthesizer (#8) → speech servisine (8001) seslendirtir

Ses dosyaları da backend'den gelir:
  şarkı: GET /api/tracks/{id}/audio      (data/music/ altındaki MP3, #42)
  anons: GET /api/speech/audio/{ad}.wav  (backend, speech servisinden alıp iletir)
```

Bağlantı `backend/app/radio/integration.py` dosyasında yapılır. Backend açılırken (`app/main.py`, `lifespan`) planlayıcı gerçek modüllerle kurulur, kapanırken arka plandaki işler iptal edilir.

**Anons sesi neden backend'den geçiyor?** Speech servisi yalnızca kendi bilgisayarında dinler (`127.0.0.1:8001`). Tarayıcı ona doğrudan bağlanmaya çalışsaydı, Vite proxy'si arkasında ya da aynı ağdaki bir telefonda ses gelmezdi. Böylece oynatıcı her şey için tek adres kullanır (`/api`). Range istekleri iletilir; mobil tarayıcılar ve ileri sarma şarkılardaki gibi çalışır.

## Oynatıcı için sözleşme (#10)

1. `POST /api/sessions` → `{"session_id": "...", "user_id": "guest"}`. Giriş yapılmışsa oturum o hesaba aittir (çerezden okunur).
2. `GET /api/sessions/{session_id}/next` → çalınacak parça:

   ```json
   {"session_id": "...", "position": 2,
    "segment": {"kind": "announcement", "text": "...", "emotion": "calm", "duration_s": 6.1,
                "audio_url": "/api/speech/audio/3f2a....wav", "introduces_track_id": "..."},
    "announcement_skipped": null}
   ```

   `kind` ya `track` (ek alanlar: `title`, `artist`, `license`, `track_id`) ya da `announcement` olur. İki türde de `audio_url` doğrudan `<audio>` ile çalınabilir.
3. Parça bitince (`ended`) yeniden `/next` çağrılır. Cevap beklemez; sıradaki parça arka planda hazırlanmıştır.
4. Dinleme bitince `DELETE /api/sessions/{session_id}`. Kapatılmayan oturum 2 saat sonra kendiliğinden silinir.

`announcement_skipped` doluysa anons hazır olmadığı ya da üretilemediği için atlanmış, yerine şarkı gelmiştir. Bu bir hata değildir; isteğe bağlı olarak geliştirici panelinde gösterilebilir.

## Bir parça eksikse

| Durum | Ne olur | Log'daki uyarı |
|---|---|---|
| `GEMINI_API_KEY` boş | Anons DJ Brain'in şablon cümlesiyle seslendirilir | `LLM not available (...)` |
| Gemini hata veriyor ya da geç cevap veriyor | Aynı şablon cümle kullanılır (`generate_song_intro`) | — |
| Speech servisi kapalı | Şarkılar anonssuz çalar, servis açılınca anonslar geri gelir | `speech service not reachable (...)` |
| Speech servisi bilinmeyen bir duygu alırsa | Anons nötr sesle okunur | `unknown emotion ...` |
| Katalog boş, veritabanı kapalı | `/next` → 503 "No song available right now" | — |
| Müzik kaynağı geçici olarak hata veriyor | Yakın zamanda çalan bir şarkı tekrar çalınır | `music source failed ...` |

## Testler

`backend/tests/test_radio_integration.py` gerçek uygulamayı (`app.main`) gerçek modüllerle çalıştırır. Yalnızca dış uçlar sahtedir: veritabanı satırları, LLM cevabı ve speech servisinin HTTP cevapları. Postgres, Gemini anahtarı, speech servisi ya da internet gerekmez.

| Test | Gösterdiği |
|---|---|
| `test_radio_plays_song_then_voiced_intro_then_song` | Şarkı → seslendirilmiş anons → şarkı; anons sesi backend'den gelir |
| `test_without_a_gemini_key_the_template_intro_is_voiced` | Anahtar yokken şablon anons seslendirilir |
| `test_no_silence_while_the_speech_service_fails` | Ses üretilemezse şarkı çalar, sonraki anons gelir |
| `test_no_silence_when_the_speech_service_is_not_running` | Servis kapalıyken sessizlik olmaz |
| `test_empty_catalog_answers_503` | Şarkı yoksa anlaşılır bir hata döner |
| `test_audio_proxy_*` | Range istekleri iletilir, bilinmeyen dosya adları reddedilir |
| `test_lifespan_connects_the_real_modules` | Backend açılınca gerçek parçalar bağlanır |

## Temiz bilgisayar testi

Kabul ölçütü: "Temiz bir bilgisayarda README adımlarıyla çalışıyor". Bunu, projeyi hiç kurmamış bir bilgisayarda (ya da yeni bir kullanıcı hesabında) yalnızca README'ye bakarak dene. Takıldığın her adımı README'ye ekle.

- [ ] Repo yeni klonlandı (`git clone`), önceki kurulumdan hiçbir dosya kopyalanmadı
- [ ] Adım 1: `docker compose up -d` çalıştı
- [ ] Adım 2: backend açıldı, `http://localhost:8000/api/health` → `"db": "up"`
- [ ] Adım 3: Gemini anahtarı `backend/.env` dosyasına yazıldı (isteğe bağlı; yoksa şablon anons)
- [ ] Adım 5: katalog indirildi ve aktarıldı, `/api/tracks?limit=5` şarkı listeliyor
- [ ] Adım 6: speech servisi açıldı, `http://localhost:8000/api/speech/health` → `"status": "ok"`
- [ ] Adım 7: `python -m app.radio.check` → `RADIO WORKS END TO END`
- [ ] Adım 4 ve 7: tarayıcıda şarkı → anons → şarkı duyuldu
- [ ] `git status` temiz: `.env`, ses ve müzik dosyaları commit'lenmeye hazır görünmüyor

## Demo videosu

Video repoya **eklenmez**, ekibin ortak klasörüne yüklenir. 2–3 dakika yeterlidir.

1. Terminaller: veritabanı, backend ve speech servisi açık (backend log'unda uyarı yok).
2. Tarayıcıda `http://localhost:5173`, radyoyu başlat. İlk şarkının başı duyulur.
3. Şarkının sonuna atla ya da bekle: DJ anonsu duyulur, metni ve duygusu ekranda (ya da `/next` cevabında) görünür.
4. Anonsun tanıttığı şarkı başlar.
5. İsteğe bağlı: speech servisini kapat, radyonun susmadığını göster; tekrar aç, anonsların geri geldiğini göster.

Ekran ve sistem sesi birlikte kaydedilmeli. Ubuntu'da OBS Studio önerilir (GNOME'un yerleşik ekran kaydedicisi sistem sesini kaydetmeyebilir). Windows'ta Xbox Game Bar (`Win+G`) ya da OBS kullanılabilir.
