# Emotion-Aware AI Radio

**Duygu Odaklı Yapay Zekâ Radyosu**

Sunuculuğunu yapay zekânın yaptığı, her dinleyiciye kişisel yayın akışı sunan, konuştuğu konuya göre sesine duygu katan ve ruh hâline uygun şarkı seçen bir radyo. **Radyo yayını İngilizcedir.**

* **Duygulu sunuculuk:** Sevinçli bir haberde heyecanlı ve içten, üzücü bir olayda üzgün bir ses tonuyla konuşma
* **Kişisel yayın:** Her kullanıcıya kendi profiline, dinleme geçmişine ve isteklerine göre ayrı bir yayın akışı
* **Bağlama duyarlılık:** Hava durumu, günün saati, gündem ve özel günlere göre yayının ruh hâlini belirleme
* **Ruh hâline göre müzik:** Yağmurlu bir akşamda sakin, güzel bir haberde neşeli şarkı seçme
* **Açıklanabilirlik:** "Bu şarkıyı yağmur yağdığı için seçtim" gibi kararlarının nedenini gösterme
* **İstekler:** Yazılı (ileride sesli ve telefonla) şarkı istekleri ve istek kuyruğu
* **Web ve mobil:** Radyoyu tarayıcıdan ve telefondan canlı dinleyebilme

Bitirme Projesi · Ankara Bilim Üniversitesi · 2026–2027<br>
Danışman: Prof. Dr. Hakan Çağlar

## Durum

🚧 **1. sprint: proje iskeleti ve temel radyo altyapısı.**

* Proje konusu ve 1. dönem planı belirlendi.
* Konu belgesindeki 20 fonksiyonel gereksinim iki dönemde tamamlanacak; büyük bölümü 1. dönemde.
* Sıra: önce temel radyo altyapısı, sonra duygulu ses, sonra hava durumu ve haber bağlamı.
* Projenin ana zorluğu: **sese duygu verme**.

## Nasıl Çalışacak?

```
Bağlam toplama        → hava durumu, saat, gündem, özel günler
        ↓
Duygu analizi         → haberin / anın duygusu (happy, sad, excited, calm...)
        ↓
Sunucu metni          → duyguya uygun İngilizce DJ metni (LLM)
        ↓
Duygulu ses üretimi   → metnin doğru duygu tonunda seslendirilmesi
        ↓
Duygu kontrolü        → üretilen sesin duygusunun ölçülmesi, gerekirse yeniden üretim
        ↓
Müzik seçimi          → kullanıcıya ve ruh hâline uygun şarkının seçilmesi
        ↓
Yayın akışı           → kullanıcı başına konuşma ve şarkı sırası, geçişler, ses seviyesi
        ↓
Web ve mobil          → canlı dinleme, çalan şarkı, "neden bu şarkı?"
```

## Sese Duygu Verme Yaklaşımı

Duygulu ses katman katman geliştirilecek. Her katman tek başına çalışır, bir üstteki katman sonucu iyileştirir:

1. **Temel duygulu ses:** Açık kaynak bir İngilizce ses modeli, duyguya uygun örnek seslerle ve ayarlarla yönlendirilir.
2. **Prozodi kontrolü:** Duyguya göre konuşma hızı, ses perdesi, vurgu ve duraklamaların kendi kodumuzla ayarlanması.
3. **Duygu tanıma ile kalite kontrolü:** Üretilen sesin duygusunu ölçen kendi modelimiz; istenen duygu tutmazsa ses yeniden üretilir.
4. **İnce ayar (2. dönem):** Ses modelinin duygu etiketli kayıtlarla iyileştirilmesi.

## Planlanan Teknolojiler

| Alan | Aday teknolojiler | Durum |
|---|---|---|
| Duygulu ses (TTS) | Chatterbox, Orpheus, StyleTTS2, Kokoro | Karşılaştırılacak |
| Ses işleme | librosa, pyworld | Araştırılacak |
| Metin duygu analizi | GoEmotions veri seti ile kendi modelimiz | Araştırılacak |
| Sesten duygu tanıma | ESD, RAVDESS, CREMA-D veri setleri | Araştırılacak |
| Sunucu metni | LLM API: geliştirmede Gemini ücretsiz kota, sonra ücretli model (ör. Claude Haiku); yedek olarak yerel model | Başlıyor |
| Müzik | MTG-Jamendo (Creative Commons), librosa ile kendi özellik çıkarımımız | Başlıyor |
| Bağlam verisi | Hava durumu ve haber API'leri / RSS | Araştırılacak |
| Backend | Python, FastAPI, PostgreSQL | Başlıyor |
| Yayın | Kullanıcı başına ses akışı (HLS) | Araştırılacak |
| Web | React + TypeScript | Başlıyor |
| Mobil | PWA | Planlanan |
| Kalite | GitHub Actions, pytest | Başlıyor |

## Yol Haritası

İki haftalık sprintler. Ayrıntılı görevler GitHub Project panosunda takip edilir.

**1. dönem**

| Sprint | Tarih | Milestone | Hedef |
|---|---|---|---|
| S1 | 26 Eki – 8 Kas | M1 Temel radyo | Proje iskeleti, LLM bağlantısı, müzik kataloğu, ses modeli karşılaştırması |
| S2 | 9 – 22 Kas | M1 Temel radyo | Kullanıcı başına yayın akışı, DJ anonsları, web oynatıcı |
| S3 | 23 Kas – 6 Ara | M2 Kişisel radyo | Profil, kişisel şarkı seçimi, beğen/atla, yazılı istek ve kuyruk |
| S4 | 7 – 20 Ara | M3 Duygulu sunucu | Duygu belirleme, duyguya göre metin, prozodi, ruh hâline göre müzik |
| S5 | 21 Ara – 3 Oca | M3 Duygulu sunucu | Duygu kalite kontrolü, hava durumu ve haber, yayın ayarları |
| S6 | 4 – 17 Oca | M4 Dönem sonu | PWA, yönetim paneli, yedek içerik, değerlendirme, rapor ve demo |

**2. dönem**
- Telefonla arama ve sesli şarkı isteği
- Avatarlar ve dudak senkronu
- Gelişmiş tercih öğrenme
- Ses modelinin ince ayarı
- Dinleyici testleri, final raporu ve sunum

## Modüller

Her modülün bir sorumlusu vardır; sorumlu o alanı takip eder ve kararlarını verir. Issue'lar atanmamış açılır, herkes her sprintte kendini atar: önce kendi modülünden, gerekirse diğerlerinden. Sprint yükü tahmini puanlarla dengelenir, PR'lar çapraz incelenir. Modüllerin 1. dönem iş yükü yaklaşık eşittir ve her birinde bir yapay zekâ parçası vardır.

| Modül | Kapsam | Sorumlu |
|---|---|---|
| 🧠 DJ Brain & Emotion | Anın duygusunu belirleme (metin), sesten duygu tanıma ile kalite kontrolü, LLM metin servisi, yönetmen (anonsun tonu ve süresi), haber hattı ve tekrarları azaltma, hava durumu, güvenlik filtresi, yazılı istekleri anlama, değerlendirme ölçümleri | Nisa Nur Aklan |
| 🎙️ Voice & Broadcast | Duygulu ses (TTS), prozodi kontrolü, yayın planlayıcı (kullanıcı başına sıra), ses karıştırma (geçişler, ses seviyesi), HLS akışı, yedek içerik; 2. dönemde konuşma tanıma ve telefon | Azra İdiz |
| 🎵 Music & Platform | Müzik kataloğu ve lisanslar, müzik analizi (ruh hâli, enerji), şarkı seçimi ve kişiselleştirme, "neden bu şarkı?", istek kuyruğu, backend API, kullanıcılar ve KVKK, web/PWA oynatıcı, yönetim paneli; 2. dönemde avatarlar | Nisanur İlhan |

**Modüller arası sınır:** DJ Brain her anons için ne söyleneceğine, hangi duyguyla ve ne kadar sürede söyleneceğine karar verir. Voice & Broadcast anonsları seslendirir, şarkılarla birlikte kullanıcı başına sıraya dizer ve yayınlar. Music & Platform şarkıları, kullanıcıları ve istekleri sağlar. Bu sınır ortak bir veri sözleşmesiyle tanımlanır.

## Klasör Yapısı

```
Graduation-Project/
├── backend/                FastAPI uygulaması (Python 3.12)
│   ├── app/
│   │   ├── api/            router'lar (health, dj, tracks, auth, me)
│   │   ├── core/           ayarlar (.env) ve loglama
│   │   ├── db/             veritabanı oturumu ve temel model
│   │   ├── music/          katalog, indirme/aktarma komutları ve şarkı seçimi
│   │   ├── users/          hesaplar, giriş oturumları ve profil (bkz. docs/kullanicilar.md)
│   │   ├── radio/          yayın mantığı (şimdilik boş)
│   │   ├── content/llm/    LLMClient arayüzü ve GeminiClient
│   │   └── speech_client/  ses servisine bağlanacak arayüz (şimdilik boş)
│   ├── alembic/            veritabanı migration'ları
│   └── tests/              pytest testleri
├── web/                    React + TypeScript (Vite) web arayüzü
├── speech/                 duygulu ses servisi (ayrı Python ortamı, şimdilik sadece README)
├── scripts/                yardımcı script'ler (ör. müzik indirme)
├── docs/                   rapor, araştırma ve toplantı notları
└── docker-compose.yml      PostgreSQL
```

## Kurulum ve çalıştırma

Gerekenler: Windows 11, Python 3.12 (backend), Python 3.11 (speech servisi), Node.js (LTS), Docker Desktop. Komutlar PowerShell içindir ve repo kök klasöründen başlar.

### 1. Veritabanı (PostgreSQL)

Docker Desktop açık olmalı.

```powershell
docker compose up -d
```

Postgres, bilgisayarında **5433** portundan erişilir (5432 başka bir Postgres ile çakışmasın diye). Kullanıcı, parola ve veritabanı adı: `radio`.

### 2. Backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Backend `http://localhost:8000` adresinde çalışır. Kontrol: `http://localhost:8000/api/health`. API belgesi: `http://localhost:8000/docs`.

### 3. Gemini API anahtarı

1. [Google AI Studio](https://aistudio.google.com/apikey) adresine gir ve **Create API key** ile ücretsiz bir anahtar al.
2. `backend/.env` dosyasında `GEMINI_API_KEY=` satırının sonuna yapıştır.
3. Backend'i yeniden başlat.

Anahtar yoksa `/api/dj/preview` uygun bir hata mesajıyla 503 döner. `.env` dosyasını **asla commit'leme**.

### 4. Web

Yeni bir terminalde:

```powershell
cd web
npm install
npm run dev
```

Arayüz `http://localhost:5173` adresinde açılır. `/api` istekleri otomatik olarak backend'e (8000) yönlenir.

### 5. Müzik kataloğu

Radyonun çalacağı Creative Commons şarkıları indirip veritabanına aktarır. Backend klasöründe, venv açıkken yapılır; veritabanı çalışıyor ve `alembic upgrade head` uygulanmış olmalı.

1. [Jamendo geliştirici portalından](https://devportal.jamendo.com) ücretsiz bir `client_id` al.
2. `backend/.env` dosyasında `JAMENDO_CLIENT_ID=` satırının sonuna yapıştır.
3. Şarkıları indir (yaklaşık 400 şarkı, 1 GB; internet hızına göre uzun sürebilir). Yarıda kalırsa aynı komut kaldığı yerden devam eder:

```powershell
python -m app.music.download
```

4. İndirilenleri veritabanına aktar. Tekrar çalıştırmak güvenlidir; aynı şarkı ikinci kez eklenmez:

```powershell
python -m app.music.import_catalog
```

5. Kontrol: `http://localhost:8000/api/tracks?limit=5` şarkıları listeler. Listedeki bir `id` ile `http://localhost:8000/api/tracks/<id>/audio` adresi şarkıyı tarayıcıda çalar.

Dosyalar repo kökündeki `data/music/` altına iner ve commit'lenmez. Lisans seçimi ve kaynak ayrıntıları için [docs/muzik-kaynagi.md](docs/muzik-kaynagi.md).

### 6. Speech servisi (anonsların sesi)

Anonsları seslendiren servis backend'den ayrı çalışır ve kendi **Python 3.11** ortamını kullanır. Kurulum bir kez yapılır. Ubuntu komutları, GPU'lu kurulum (Orpheus) ve ayarlar için: [speech/service/README.md](speech/service/README.md).

Yeni bir terminalde:

```powershell
cd speech\service
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -e "..\experiments[kokoro]" -e ".[dev]"
.\.venv\Scripts\python.exe -m spacy download en_core_web_sm
copy .env.example .env
.\.venv\Scripts\uvicorn.exe speech_service.app:app --host 127.0.0.1 --port 8001
```

Windows'ta `espeak-ng` de kurulu olmalı. İlk açılışta model indirildiği için birkaç dakika sürebilir. GPU yoksa servis Kokoro ile CPU'da çalışır.

Kontrol: `http://localhost:8000/api/speech/health` adresi `"status": "ok"` göstermeli.

Backend servise `backend/.env` içindeki `SPEECH_SERVICE_URL` adresinden bağlanır (varsayılan `http://localhost:8001`). Tarayıcı servise hiç bağlanmaz; anons sesleri de şarkılar gibi backend'den (`/api/speech/audio/...`) gelir.

### 7. Radyoyu dinle

Açılış sırası: veritabanı (1) → backend (2) → speech servisi (6) → web (4). Müzik kataloğu (5) bir kez aktarılmış olmalı.

**Terminalden kontrol.** Web oynatıcıya gerek duymadan bütün zinciri dener. Backend klasöründe, venv açıkken:

```powershell
python -m app.radio.check
```

Oynatıcının yaptığını yapar: oturum açar, sıradaki parçayı üç kez ister ve her sesi indirir. Şarkıdan sonra 30 sn bekler (şarkı çalıyormuş gibi), bu sürede anons yazılıp seslendirilir. Hepsi geçerse `RADIO WORKS END TO END` yazar. Sesleri dinlemek için `--save $env:TEMP\radio-check` ekle (Ubuntu'da `--save /tmp/radio-check`).

**Tarayıcıdan.** `http://localhost:5173` adresini aç ve radyoyu başlat: şarkı → seslendirilmiş DJ anonsu → şarkı.

Bir parça eksikse radyo susmaz:

| Durum | Ne olur |
|---|---|
| `GEMINI_API_KEY` boş | Anonslar DJ Brain'in şablon cümlesiyle seslendirilir: "Up next, *şarkı* by *sanatçı*." |
| Speech servisi kapalı | Şarkılar anonssuz çalar. Servis açılınca anonslar kendiliğinden geri gelir, backend'i yeniden başlatmak gerekmez. |
| Katalog boş ya da veritabanı kapalı | `/api/sessions/{id}/next` 503 döner: "No song available right now". Adım 1 ve 5'i kontrol et. |

Backend açılırken eksik parçayı log'a uyarı olarak yazar (`LLM not available ...`, `speech service not reachable ...`). Zincirin ayrıntıları ve temiz bilgisayar kontrol listesi: [docs/m1-entegrasyon.md](docs/m1-entegrasyon.md).

### Testler

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest
ruff check .
ruff format --check .

cd ..\web
npm run lint
npm run format:check
npm run build
```

Testler gerçek Gemini veya Jamendo API'sine istek atmaz. Veritabanı testleri Postgres çalışıyorsa (adım 1 ve `alembic upgrade head`) koşar, yoksa atlanır.

## Çalışma Kuralları

* Radyo içeriği ve kod İngilizce; belgeler, issue'lar ve notlar Türkçe.
* **Telifli müzik kullanılmaz.** Yalnızca Creative Commons lisanslı şarkılar kullanılır; değiştirilemez (ND) lisanslılar hariç tutulur. Her şarkının lisansı kaydedilir, sanatçı ve lisans arayüzde gösterilir.
* Ses kayıtları ve müzik dosyaları repoya commit'lenmez.
* API anahtarları yalnızca `.env` dosyasına yazılır, commit'lenmez.
* LLM'e yalnızca ortak `LLMClient` arayüzü üzerinden erişilir; kullanıcıların kişisel verileri LLM'e gönderilmez.

## Ekip

* Nisanur İlhan · Software Engineering · [@ilhannisanur](https://github.com/ilhannisanur)
* Nisa Nur Aklan · Software Engineering · [@aklanasin](https://github.com/aklanasin)
* Azra İdiz · Information Systems Engineering · [@azraidd](https://github.com/azraidd)
