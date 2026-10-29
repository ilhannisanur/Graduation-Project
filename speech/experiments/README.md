# TTS deneyleri (#4)

Duygulu İngilizce TTS adaylarını **aynı 35 cümleyle (7 duygu × 5 cümle) ve aynı ölçümlerle** karşılaştıran araç. Çıktısı `docs/tts-karsilastirma.md` raporuna girer.

| Model | Nerede çalışır | Duygu nasıl verilir |
|---|---|---|
| Kokoro | Laptop (CPU) | Duygu girdisi yok; sadece konuşma hızı |
| Chatterbox | Laptop (CPU), Colab (GPU) | `exaggeration`, `cfg_weight`, referans ses |
| Chatterbox Turbo | Laptop (CPU) | Referans ses ve `[laugh]` gibi etiketler |
| StyleTTS2 | Laptop (CPU) | `embedding_scale`, referans ses |
| Orpheus 3B | Sadece Colab (GPU) | Metin içi etiketler: `<laugh>`, `<sigh>`, `<gasp>` |
| ElevenLabs | Bulut API | `eleven_v3` etiketleri: `[excited]`, `[sad]` |

Motorlar ortak bir arayüzü (`tts_bench/engines/base.py`) uygular. Seçilen motor, S2'deki Speech servisinde (#8) aynı arayüzle kullanılacak.

## Duygular ve test seti

Duygular: `neutral, happy, excited, calm, sad, serious, surprised`. Bu liste `tts_bench/engines/base.py` dosyasındaki `EMOTIONS` değişkenindedir ve DJ Brain'in veri sözleşmesindeki duygu etiketleriyle **aynı olmalıdır**.

Test seti `tts_bench/test_set.json` dosyasındadır. Her duygu için 5 cümle var:

* **1 ortak cümle:** 7 duyguda da aynı metin. Duyguyu sadece ses taşır, bu yüzden duygu kontrol edilebilirliğini ölçer.
* **4 içerik cümlesi:** Metni de o duyguya uyan gerçekçi anonslar.

`listen: true` işaretli 14 cümle (her duygudan 2 tane) kör dinleme testine girer.

## Ne ölçülüyor?

| Ölçüm | Nasıl |
|---|---|
| Hız | Gerçek zaman oranı (RTF = üretim süresi / ses süresi), model yükleme süresi |
| Kaynak | RAM tepe değeri, GPU belleği (Colab'da) |
| Ses | Seviye (LUFS, tepe), baştaki/sondaki sessizlik |
| Duygu (otomatik) | Hazır bir konuşma-duygu modeliyle kaba kontrol (`score_emotion`) |
| Duygu ve doğallık (insan) | 3 kişilik kör dinleme testi: model adları gizli, herkes farklı sırada dinler |

## Kurulum: Ubuntu (Python 3.11)

Tek komut. sudo şifresini bir kez sorar; tekrar çalıştırmak güvenlidir.

```bash
./setup_ubuntu.sh
```

Betik sırasıyla şunları yapar:

1. **Sistem paketleri:** git, ffmpeg, espeak-ng, tmux vb.
2. **Python:** `uv` ve Python 3.11 (sistem Python'una dokunmaz).
3. **Model ortamları:** Her model için ayrı bir sanal ortam kurar ve PyTorch'un **CPU** sürümünü kullanır. Linux'ta varsayılan torch CUDA'lı gelir ve birkaç GB tutar.
   * `.venv-kokoro`: Kokoro ve ElevenLabs
   * `.venv-chatterbox`: Chatterbox ve Turbo
   * `.venv-styletts2`: StyleTTS2
4. **Kontrol:** Testleri çalıştırır, sonunda `doctor` ile durumu yazdırır.

Kurulum günlükleri `logs/setup-<ortam>.log` dosyalarına yazılır. Bir ortam hata verirse betik günlüğün sonunu gösterir. Sorunu düzeltip betiği tekrar çalıştır; tamamlanan ortamlar korunur.

```bash
./setup_ubuntu.sh --only chatterbox              # tek ortam
./setup_ubuntu.sh --recreate --only chatterbox   # o ortamı silip yeniden kur
./setup_ubuntu.sh --skip-apt                     # sistem paketleri zaten kurulu
```

Durum kontrolü (istediğin zaman):

```bash
.venv-kokoro/bin/python -m tts_bench.doctor --engines kokoro elevenlabs
.venv-chatterbox/bin/python -m tts_bench.doctor --engines chatterbox chatterbox-turbo
.venv-styletts2/bin/python -m tts_bench.doctor --engines styletts2
```

Her satır `[OK]`, `[WARN]` ya da `[FAIL]` ile başlar. Yardım isterken bu çıktıyı gönder.

Tek komutla deney: `./run_experiments.sh` (seçenekler aşağıda).

## Kurulum: Windows (PowerShell, Python 3.11)

Her model **kendi sanal ortamında** kurulur, çünkü paket sürümleri çakışır. Komutların hepsi `speech\experiments` klasöründe çalıştırılır.

Ölçüm yapmadan önce laptopu şarja tak ve güç modunu **En iyi performans** yap.

### Kokoro (ve ElevenLabs)

ElevenLabs ek paket istemediği için bu ortamda çalışır.

```powershell
py -3.11 -m venv .venv-kokoro
.\.venv-kokoro\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e ".[kokoro,dev]"
python -m pytest
deactivate
```

### Chatterbox

```powershell
py -3.11 -m venv .venv-chatterbox
.\.venv-chatterbox\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[chatterbox,dev]"
deactivate
```

### StyleTTS2

```powershell
py -3.11 -m venv .venv-styletts2
.\.venv-styletts2\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e ".[styletts2,dev]"
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"
deactivate
```

## ElevenLabs (ticari referans)

ElevenLabs, açık kaynak modelleri bir üst sınırla kıyaslamak için karşılaştırmaya dahil edilir.

1. **Anahtar al.** elevenlabs.io'da ücretsiz hesap aç. **Developers → API Keys → Create** ile bir anahtar oluştur. İzinlerden **Text to Speech** ve **Voices** için *Access*, **User** için *Read* seç.
2. **Anahtarı kaydet.** `speech/experiments/.env` dosyasına yaz. Bu dosya `.gitignore`'da; **asla commit'leme**.
   ```
   ELEVENLABS_API_KEY=sk_...
   ```
   Ubuntu'da `chmod 600 .env` ile dosyayı sadece kendine görünür yap.
3. **Ses seç.** Diğer modellerin hepsi varsayılan olarak **kadın** sesiyle konuşuyor. Kör dinleme testinin adil olması için ElevenLabs'ta da bir kadın sesi seç:
   ```bash
   .venv-kokoro/bin/python -m tts_bench.elevenlabs_tools voices --gender female
   ```
   Seçtiğin sesin kimliğini `.env` dosyasına ekle:
   ```
   ELEVENLABS_VOICE_ID=...
   ```
4. **Kontrol et.** Komut anahtarı, planı, kalan kotayı, seçilen sesi ve tam bir çalıştırmanın kaç karakter tutacağını gösterir:
   ```bash
   .venv-kokoro/bin/python -m tts_bench.elevenlabs_tools check
   ```

**Kota.** Ücretsiz plan ayda yaklaşık 10.000 karakter veriyor; tam test seti yaklaşık 3.400 karakter tutuyor. `--fresh` ile tekrar tekrar çalıştırma; her çalıştırma kotadan düşer.

**Kullanım koşulları.** Ücretsiz planın çıktıları ticari olmayan kullanım içindir ve paylaşılırken kaynak belirtilmelidir. Rapora "ElevenLabs (ücretsiz plan)" diye yaz.

**Gizlilik.** ElevenLabs'a sadece sabit test cümleleri gönderilir; dinleyici verisi asla gönderilmez.

**Olası hatalar:**

* `eleven_v3` hesabında kullanılamıyorsa komuta `--option model=eleven_multilingual_v2` ekle.
* Ham PCM formatı planında yoksa araç kendiliğinden MP3'e geçer.

## Tek komutla çalıştırma

Ubuntu:

```bash
./run_experiments.sh                                  # bütün motorlar, 35'er cümle, sonunda results/summary.md
./run_experiments.sh --limit 2                        # hızlı kontrol
./run_experiments.sh --engines kokoro,elevenlabs
./run_experiments.sh --engines chatterbox,chatterbox-turbo,styletts2 --refs refs
```

Windows:

```powershell
.\run_experiments.ps1                 # bütün motorlar, 35'er cümle, sonunda results\summary.md
.\run_experiments.ps1 -Limit 2        # hızlı kontrol
.\run_experiments.ps1 -Engines kokoro,elevenlabs
.\run_experiments.ps1 -Engines chatterbox,chatterbox-turbo,styletts2 -Refs refs
```

* Sanal ortamı olmayan motorlar ve anahtarı olmayan ElevenLabs atlanır.
* Yarıda kesilen veya hata veren bir çalıştırmada aynı komutu tekrar çalıştır. Sadece eksik cümleleri üretir.
* `--fresh` (Windows'ta `-Fresh`) eski sonuçları silip baştan başlatır.
* Betik "dijital olarak imzalanmamış" hatası verirse bir kez `Unblock-File .\run_experiments.ps1` çalıştır.

Tek bir motoru elle çalıştırmak istersen (ortam aktifken):

```powershell
python -m tts_bench.run --engine kokoro --resume
```

## Tek cümleyle hızlı deneme

```powershell
python -m tts_bench.say --engine chatterbox --emotion sad --intensity 0.9 --play "Some difficult news tonight."
```

`--intensity` duygunun yoğunluğudur (0–1). Kullanılan ayarlar ekrana yazdırılır. `--play` dosyayı varsayılan oynatıcıda açar: Ubuntu'da `xdg-open` ile, WSL'de Windows oynatıcısıyla.

## Referans sesler (`refs\`)

Chatterbox, Turbo ve StyleTTS2 bir referans sesin tonunu taklit edebilir. Konu belgesinin 18. maddesi gereği **gerçek bir kişinin sesi izinsiz kullanılmaz**. Bu yüzden referansları ekipten biri, açık rızasıyla, kendi sesinden kaydeder.

1. Test cümlelerinden **farklı** bir metni her duygu için 8–10 saniye oku. Örnek metin: *"Hello everyone, welcome back to the show. Let's see what's coming up next."*
2. Kaydı dönüştür:
   ```powershell
   ffmpeg -i happy.m4a -ac 1 -ar 24000 refs\happy.wav
   ```
3. Dosya adları duygu adlarıyla aynı olmalı. Eksik duygular için `neutral.wav` kullanılır.
4. Rıza bilgisini raporun 8. bölümüne yaz.

Ses dosyaları repoya girmez.

## GPU ölçümleri ve Orpheus (Colab)

Issue #4 her aday için **GPU belleği** ve GPU hızının ölçülmesini istiyor. Laptoptaki MX350 bunun için kullanılamadığından bu ölçümler ücretsiz Colab T4'te yapılır. `colab/tts_benchmark_gpu.ipynb` dört bölümden oluşur:

| Bölüm | Model | Not |
|---|---|---|
| A | Orpheus 3B | Sadece burada çalışır. Hugging Face'te model koşullarını kabul edip bir Read token gerekir. |
| B | Chatterbox | GPU belleği ve hız |
| C | StyleTTS2 | GPU belleği ve hız |
| D | Kokoro | GPU belleği ve hız |

* **Bölümler arası:** Her bölüm farklı paket sürümleri kurduğu için aralarda **Runtime → Restart session** yap.
* **Sonuçlar:** Her bölümün sonunda bir zip iner. İçinde zaten `results` klasörü olduğu için zip'i `speech/experiments` klasörüne aç (`results` içine değil).

## Kör dinleme testi

```bash
.venv-kokoro/bin/python -m tts_bench.listening --raters azra nisa nisanur --labels <modeller>
.venv-kokoro/bin/python -m tts_bench.listening_page --raters azra nisa nisanur
```

1. **Klipler.** `listening` komutu `clips/` (adları gizlenmiş klipler), `key.csv` (hangi klip hangi model; puanlama bitene kadar açılmaz) ve her kişiye bir `rating_<isim>.xlsx` üretir.
2. **Sayfalar.** `listening_page` komutu her kişiye **tek dosyalık bir dinleme sayfası** üretir: `dinle_<isim>.html`. Sesler dosyanın içine gömülüdür; Windows, Mac ve Linux'ta çift tıklayınca tarayıcıda açılır. Puanlar otomatik kaydedilir. Kişi bitince `rating_<isim>.csv` dosyasını indirip geri gönderir.
3. **Özet.** Gelen CSV dosyalarını `listening/` klasörüne koy ve özeti çalıştır:

```bash
.venv-kokoro/bin/python -m tts_bench.summarize      # results/summary.md: 5 bölüm
```

Her kişi için `rating_<isim>.xlsx` ve `rating_<isim>.csv` dosyalarından **en çok doldurulmuş** olan kullanılır.

Adım adım anlatım ve arkadaşlarına gönderilecek hazır mesaj: `ADIM_ADIM.md`, Adım 7.

İsteğe bağlı otomatik duygu kontrolü (Chatterbox ortamında, transformers orada var):

```bash
.venv-chatterbox/bin/python -m tts_bench.score_emotion
```

## Klasör yapısı

```
speech/experiments/
├── setup_ubuntu.sh      tek komutla kurulum (Ubuntu)
├── run_experiments.sh    tek komutla deney (Ubuntu)
├── run_experiments.ps1   tek komut (Windows)
├── tts_bench/
│   ├── engines/          ortak arayüz ve motorlar (duygu → parametre tabloları burada)
│   ├── test_set.json     7 duygu × 5 cümle
│   ├── doctor.py         kurulum kontrolü
│   ├── elevenlabs_tools.py  ElevenLabs anahtar, kota ve ses seçimi
│   ├── say.py            tek cümle deneme
│   ├── run.py            üretim ve ölçüm (kaldığı yerden devam eder)
│   ├── listening.py      kör dinleme testi: klip seçimi, key.csv, xlsx
│   ├── listening_page.py her kişiye tek dosyalık dinleme sayfası (HTML)
│   ├── score_emotion.py  otomatik kaba duygu kontrolü
│   └── summarize.py      rapor tabloları
├── colab/                Orpheus ve GPU deneyleri
├── tests/                sahte motorla testler (model indirmez)
└── refs/                 referans sesler (repoya girmez)
```

Duygu → parametre tabloları (`SPEED_FULL`, `EXAGGERATION_FULL`, `V3_TAGS` vb.) başlangıç tahminleridir. Dinleyerek ayarla ve son değerleri rapora yaz.
