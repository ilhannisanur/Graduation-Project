# Speech servisi (#8)

Anons metnini sese çeviren, backend'den **ayrı** çalışan servis. Kendi Python ortamında çalışır; backend ona yalnızca HTTP üzerinden (`backend/app/speech_client`) bağlanır. TTS modeli backend'e hiç yüklenmez.

* **Model:** #4'ün kararına göre GPU varsa **Orpheus**, yoksa **Kokoro**. Hangi modelin çalışacağı koddan değil, ayardan seçilir (`TTS_ENGINE`). Model değişirse servis, backend ve yayın planlayıcı (#9) değişmez.
* **Motorlar:** `speech/experiments/tts_bench/engines` içindeki motorlar kullanılır. Bunlar #4'te ölçülen kodun aynısı olduğu için servis ile karşılaştırma hiçbir zaman birbirinden ayrışmaz.
* **Çıktı:** Hangi model kullanılırsa kullanılsın çıktı aynı biçimdedir: **24 kHz, mono, 16-bit WAV**.

## Kurulum

### Ubuntu (laptop, GPU yok)

Komutlar `speech/service` klasöründe çalıştırılır.

```bash
cd speech/service
uv venv --seed --python 3.11 .venv
.venv/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -e "../experiments[kokoro]" -e ".[dev]"
.venv/bin/python -m spacy download en_core_web_sm
cp .env.example .env
```

### Windows (PowerShell)

```powershell
cd speech\service
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -e "..\experiments[kokoro]" -e ".[dev]"
.\.venv\Scripts\python.exe -m spacy download en_core_web_sm
copy .env.example .env
```

Windows'ta `espeak-ng` de kurulu olmalı (Kokoro bilinmeyen kelimeleri onunla okur).

### GPU'lu makine (Orpheus)

1. **Paketleri kur.** CUDA'lı torch'u ve Orpheus'u kur:

   ```bash
   .venv/bin/python -m pip install torch
   .venv/bin/python -m pip install -e "../experiments[kokoro,orpheus-hf]" -e ".[dev]"
   ```

2. **Hugging Face'e giriş yap.** Orpheus'un model sayfasında (`canopylabs/orpheus-3b-0.1-ft`) koşullar bir kez kabul edilmeli. Ardından şunu çalıştır:

   ```bash
   .venv/bin/hf auth login
   ```

   Windows'ta: `.\.venv\Scripts\hf.exe auth login`. Eski `huggingface-cli` komutu yeni sürümlerde yoktur. "Paste an access token" seçeneğini seç ve Hugging Face'ten (Settings → Access Tokens) oluşturduğun **Read** yetkili token'ı yapıştır. Token projede değil, kullanıcı klasöründe (`~/.cache/huggingface`) saklanır.

3. **Gereksinim:** En az 8 GB VRAM gerekir (T4'te ölçülen tepe değer 6,7 GB).

#### Windows'ta CUDA'lı torch

Windows'ta varsayılan `pip install torch` CPU sürümünü kurar. `torch.cuda.is_available()` `False` dönerse CUDA'lı sürümü kur (RTX 4060 ve CUDA 12.4 ile denendi):

```powershell
.\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu124 --force-reinstall
.\.venv\Scripts\python.exe -m pip install -e "..\experiments[kokoro,orpheus-hf]" -e ".[dev]"
```

#### 8 GB'lık kartta (RTX 4060 Laptop) ölçümler

Model dosyaları yaklaşık 14 GB iner (32 bit), servis bunu 16 bit yükler ve GPU'da yaklaşık 7 GB yer tutar. 8 GB kartta bellek sınırdadır; taşan kısım sistem RAM'ine gider.

| Durum | 5 sn'lik anons için üretim süresi |
|---|---|
| Servis yalnız başına çalışıyor | yaklaşık 21 sn |
| Aynı anda başka istekler, başka GPU işleri | 50 – 100 sn |

Canlı yayında anons şarkı başlayınca hazırlanır; süre uzarsa o anons atlanır ve şarkı çalınır (yayın susmaz). Üretim sırasında GPU'yu kullanan başka program (oyun, video) açık olmasın. Demo için anonsları önceden üretip önbelleğe almak da mümkündür (aynı istek ikinci kez anında gelir).

#### Duygu

Orpheus duyguyu ton ayarıyla değil, metne eklenen etiketlerle verir: `happy` → `<chuckle>`, `excited` → `<laugh>`, `sad` → `<sigh>`, `surprised` → `<gasp>` (yoğunluk 0,5 ve üzeri). Diğer duygular için metin olduğu gibi okunur. Ses tonunu büyük ölçüde cümlenin kendisi belirler. `TTS_ENGINE_OPTIONS=temperature=0.85` gibi bir ayarla daha ifadeli (ama daha az tutarlı) okuma denenebilir.

## Çalıştırma

```bash
.venv/bin/uvicorn speech_service.app:app --host 127.0.0.1 --port 8001
```

Windows'ta komut: `.\.venv\Scripts\uvicorn.exe speech_service.app:app --host 127.0.0.1 --port 8001`

* Model ilk açılışta yüklenir. İlk çalıştırmada model internetten indirildiği için birkaç dakika sürebilir.
* **Kontrol:** `http://127.0.0.1:8001/health`
* **API belgesi:** `http://127.0.0.1:8001/docs`

Hızlı deneme:

```bash
curl -s -X POST http://127.0.0.1:8001/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text": "Good evening, Ankara!", "emotion": "calm", "intensity": 0.6}'
```

Dönen `audio_url` adresi tarayıcıda açılınca ses çalar.

## GPU yoksa ne olur?

| Durum | Ne olur |
|---|---|
| `TTS_ENGINE=auto` (varsayılan), GPU yok | Servis **Kokoro ile CPU'da** çalışır. Laptopta 15 sn'lik bir anons yaklaşık 5 sn'de üretilir (#4 ölçümü). Kokoro'nun duygu girdisi yoktur, sadece konuşma hızı değişir. |
| `TTS_ENGINE=auto`, GPU var | Ana motor **Orpheus** (GPU), yedek motor **Kokoro** (CPU) olur. |
| `TTS_ENGINE=orpheus-hf` ama GPU yok | Orpheus denenmez; CPU'da gerçek zamandan onlarca kat yavaş olduğu için yayına uygun değildir. Servis yedek motorla (Kokoro) çalışır ve `/health` bunu `degraded` olarak, nedeniyle birlikte gösterir. |
| Ana motor yüklenemiyor ya da üretim sırasında hata veriyor (ör. GPU belleği doldu) | O istek yedek motorla (Kokoro) üretilir; yanıttaki `engine` alanı hangi motorun kullanıldığını söyler. |
| Bütün motorlar hata veriyor | `503` döner. Yayın planlayıcı (#9) bu durumda anonsu atlayıp şarkıya geçer; sessizlik olmaz. |

Servisin o an hangi motorla çalıştığını görmek için `/health` adresini aç. `status` alanı `ok` ya da `degraded` olur; `primary` ve `fallback` alanları motor adını, cihazı, hazır olup olmadığını ve varsa hata mesajını gösterir.

## API

### `POST /synthesize`

```json
{"text": "Up next, a calm one.", "emotion": "calm", "intensity": 0.6, "voice_id": null, "target_duration_s": null}
```

| Alan | Açıklama |
|---|---|
| `text` | Zorunlu, en fazla 1000 karakter. Fazla boşluklar temizlenir. |
| `emotion` | `neutral, happy, excited, calm, sad, serious, surprised` (ekibin ortak listesi). Varsayılan `neutral`. |
| `intensity` | 0–1 arası duygu yoğunluğu, varsayılan 0.5 |
| `voice_id` | Şimdilik yalnızca `default` ya da boş. Rol adları (ör. `host_female_1`) sunucu seçimiyle (#5) gelecek. |
| `target_duration_s` | Kabul edilir ama henüz kullanılmaz (prozodi, #22) |

Yanıt:

```json
{"audio_url": "/audio/cd29e8...d0ff.wav", "duration_s": 3.42, "sample_rate": 24000, "engine": "kokoro", "cached": false, "loudness_lufs": null}
```

Hata kodları:

* `422`: Geçersiz istek (boş metin, bilinmeyen duygu ya da ses, çok uzun metin).
* `503`: Hiçbir motor ses üretemedi.

### `GET /audio/{ad}.wav`

Üretilen ses dosyasını döndürür. Yalnızca servisin ürettiği dosyalar verilir; başka bir dosya istenirse `404` döner.

### `GET /health`

Hangi motorun hangi cihazda çalıştığını, hazır olup olmadığını ve varsa hatayı gösterir.

## Önbellek

Bir sesin dosya adı içeriğinden hesaplanır: motor, ayarlar, ses, duygu, yoğunluk ve metin. Aynı istek tekrar geldiğinde model yeniden çalışmaz; dosya `data/audio/` klasöründen verilir ve yanıtta `"cached": true` olur. Önbellek servis yeniden başlasa da korunur.

Aynı anda gelen iki aynı istek tek bir üretimi paylaşır. Motorlar aynı anda yalnızca bir istek işler, çünkü TTS modelleri aynı anda birden fazla çağrıya güvenli değildir.

`data/` klasörü repoya girmez (`.gitignore`). Önbelleği temizlemek için:

```bash
rm -rf data/audio
```

## Ayarlar (`.env`)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `TTS_ENGINE` | `auto` | `auto`, `kokoro`, `orpheus-hf`, `chatterbox`, `styletts2`, `indextts2`, `qwen3-tts` |
| `TTS_FALLBACK_ENGINE` | `kokoro` | Ana motor çalışmazsa kullanılır, her zaman CPU'da. Boş bırakılırsa yedek kullanılmaz. |
| `TTS_DEVICE` | `auto` | `auto`, `cpu` ya da `cuda` |
| `TTS_ENGINE_OPTIONS` | (boş) | Motor ayarları, ör. `voice=af_heart` |
| `SPEECH_AUDIO_DIR` | `data/audio` | Önbellek klasörü |
| `SPEECH_SAMPLE_RATE` | `24000` | Çıktı örnekleme hızı |
| `SPEECH_LOAD_ON_STARTUP` | `true` | `false` olursa model ilk istekte yüklenir |

**Modeli değiştirmek:** Yalnızca `.env` dosyasındaki `TTS_ENGINE` değişir. Yeni modelin paketi kurulur (ör. `pip install -e "../experiments[qwen3-tts]"`) ve servis yeniden başlatılır.

## Testler

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

Testler sahte motor kullanır; model indirmez, GPU ya da internet gerektirmez.

## Backend'den kullanım

Backend tarafındaki `app.speech_client` modülü:

* `SpeechClient`: arayüz
* `HttpSpeechClient`: bu servise bağlanan gerçek istemci
* `get_speech_client`: FastAPI bağımlılığı

Servisin adresi backend'de `SPEECH_SERVICE_URL` ile verilir (varsayılan `http://localhost:8001`). Backend testleri sahte bir `SpeechClient` kullanır; servisin çalışması gerekmez.
