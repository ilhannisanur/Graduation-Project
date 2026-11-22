# Emotion-Aware AI Radio

**Duygu Odaklı Yapay Zekâ Radyosu**

Sunuculuğunu yapay zekânın yaptığı, tüm dinleyicilere tek bir ortak yayın akışı sunan, konuştuğu içeriğe uygun duyguyu sesine katan, bu duygunun doğru aktarılıp aktarılmadığını kendisi ölçen ve şarkıları bağlama ve ruh hâline göre seçen bir radyo. **Radyo yayını İngilizcedir.**

* **Duygulu sunuculuk:** Haber, hava durumu ve şarkı anonslarını içeriğe uygun duyguyla seslendirme; sevinçli bir haberde heyecanlı, üzücü bir olayda üzgün bir ton
* **Duygu doğrulama:** Üretilen sesin duygusunu kendi modelimizle ölçme; hedef duygu tutmazsa yeni adaylar üretip en uygununu yayına verme
* **Ortak yayın:** Tek bir canlı yayın akışı; anonslar bir kez üretilir ve aynı anda bütün dinleyicilere ulaşır
* **Bağlama duyarlılık:** Hava durumu, günün saati, gündem ve özel günlere göre yayının ruh hâlini belirleme
* **Ruh hâline göre müzik:** Yağmurlu bir akşamda sakin, güzel bir haberde neşeli parça seçme; dinleyici profili seçim puanının bir bileşenidir
* **Açıklanabilirlik:** "Bu şarkıyı yağmur yağdığı için seçtim" gibi kararlarının nedenini gösterme
* **İstekler:** Yazılı şarkı istekleri ortak kuyruğa alınır, uygun olduğunda çalınır ve sunucu isteği anonsla duyurur
* **Web ve mobil:** Radyoyu tarayıcıdan ve telefondan canlı dinleyebilme

Bitirme Projesi · Ankara Bilim Üniversitesi · 2026–2027<br>
Danışman: Prof. Dr. Hakan Çağlar

## Durum

🚧 **3. sprint: ortak yayın akışı ve istekler.**

* **M1 tamamlandı:** şarkı → dil modeliyle yazılan DJ anonsu → seslendirme → web oynatıcı zinciri uçtan uca çalışıyor. Katalogda 400 Creative Commons parça var.
* **Kapsam:** Tek ortak yayın akışı. Kullanıcı başına ayrı akış, sesli ve telefonla istek ve avatar ana kapsamın dışındadır; zaman kalırsa 2. dönemde ek özellik olarak ele alınır.
* Projenin ana zorluğu: **sese duygu verme ve bu duygunun doğrulanması**.

## Nasıl Çalışacak?

```
Bağlam toplama        → hava durumu, saat, gündem, özel günler
        ↓
Müzik seçimi          → bağlama, ruh hâline ve dinleyici profiline uygun parça; seçim gerekçesi
        ↓
Duygu belirleme       → haberin / şarkının değerlik ve uyarılmışlığı → 2–3 sunuş tonu adayı
        ↓
Sunucu metni          → dil modeli adaylardan tonu seçer ve İngilizce DJ metnini yazar
        ↓
Duygulu ses üretimi   → metnin bu tonda seslendirilmesi, prozodi ayarı
        ↓
Duygu doğrulama       → sesin duygusunun ölçülmesi; tutmazsa en fazla 3 ek aday, en iyisi seçilir
        ↓
Yayın akışı           → tek ortak sıra: anons, şarkı ve dinleyici istekleri; geçişler, ses seviyesi
        ↓
Web ve mobil          → canlı dinleme, çalan şarkı, "neden bu şarkı?", istek gönderme
```

## Sese Duygu Verme Yaklaşımı

Duygulu ses katman katman geliştirilecek. Her katman tek başına çalışır, bir üstteki katman sonucu iyileştirir:

1. **Temel duygulu ses:** Açık kaynak bir İngilizce ses modeli, 7 duygunun her biri için metin içi etiketlerle veya referans seslerle yönlendirilir.
2. **Prozodi kontrolü:** Duyguya göre konuşma hızı, ses perdesi ve duraklamaların vokoder tabanlı analiz-sentezle (WORLD) kendi kodumuzla ayarlanması.
3. **Duygu doğrulama döngüsü:** Üretilen sesin duygusunu ölçen kendi sesten duygu tanıma modelimiz (5 sınıf: mutlu, üzgün, kızgın, şaşkın, nötr). Hedef duygu olasılığı eşiğin altındaysa en fazla 3 ek aday üretilir, en yüksek olasılıklı aday yayına verilir.
4. **İnce ayar (2. dönem):** Ses modelinin duygu etiketli kayıtlarla iyileştirilmesi.

Her katman ayrı ayrı açılıp kapatılabilir; böylece temel ses, prozodi ayarlı ses ve doğrulama döngüsü karşılaştırmalı olarak ölçülebilir.

## Teknolojiler

| Alan | Teknoloji | Durum |
|---|---|---|
| Duygulu ses (TTS) | Orpheus (ana, GPU), Kokoro (yedek, CPU); referans sesle ek karşılaştırma sürüyor | Kullanımda |
| Prozodi | pyworld (WORLD vokoderi), librosa | Planlanan |
| Metin duygu analizi | EmoBank ile ince ayarlı dönüştürücü model (değerlik ve uyarılmışlık regresyonu) + ton adayı eşleme tablosu | Planlanan |
| Sesten duygu tanıma | ESD, RAVDESS, CREMA-D ile eğitilen öz-denetimli ön eğitimli model + sınıflandırıcı; ayrıca bağımsız hazır bir model (ölçüm için) | Planlanan |
| Sunucu metni | `LLMClient` arkasında Gemini (geliştirme); gerekirse ücretli model veya yerel model | Kullanımda |
| Müzik | MTG-Jamendo (Creative Commons, ND hariç); librosa özelliklerinden ruh hâli etiketleriyle eğitilen değerlik ve enerji tahmini | Katalog hazır, analiz planlanan |
| Bağlam verisi | Hava durumu API'si, haber RSS | Planlanan |
| Backend | Python, FastAPI, PostgreSQL | Kullanımda |
| Yayın | Tek ortak ses akışı (HLS) | Planlanan |
| Web | React + TypeScript | Kullanımda |
| Mobil | PWA | Planlanan |
| Kalite | GitHub Actions, pytest, ruff | Kullanımda |

## Ölçülebilir hedefler

| Bileşen | Hedef |
|---|---|
| Metinden duygu | Test bölmesinde değerlik r ≥ 0,60, uyarılmışlık r ≥ 0,40; ekipçe etiketlenen 300 haber başlığının en az %70'inde önerilen ton adaylarından biri insan etiketiyle örtüşür |
| Sunucu metni | 100 örnek anonsta kaynakta olmayan bilgi 0; en az %90'ı hedef sürenin ±%20'si içinde |
| Sesten duygu tanıma | Eğitimde görülmeyen konuşmacılarda 5 sınıfta ağırlıksız ortalama doğruluk ≥ %70 |
| Doğrulama döngüsü | Anonsların en az %70'i bağımsız bir modelce hedef duyguda sınıflandırılır; temel modele göre en az 15 yüzde puanı artış |
| Müzik | En az 400 parçanın analizi; değerlik ve enerji tahmininde Pearson r ≥ 0,50; 1 saatlik akışta tekrar yok |
| Yayın | Ortak akış en az 3 eş zamanlı dinleyiciye; 1 saatlik testte 2 sn'den uzun istenmeyen sessizlik yok |
| Dinleyici testi | En az 24 katılımcı; doğallık ≥ 3,5/5; 7 duyguda doğru tanıma ≥ %55 |

## Yol Haritası

İki haftalık sprintler. Ayrıntılı görevler GitHub Project panosunda takip edilir.

**1. dönem**

| Sprint | Tarih | Milestone | Hedef |
|---|---|---|---|
| S1 | 26 Eki – 8 Kas | M1 Temel radyo ✅ | Proje iskeleti, LLM bağlantısı, müzik kataloğu, ses modeli karşılaştırması |
| S2 | 9 – 22 Kas | M1 Temel radyo ✅ | Yayın planlayıcı, DJ anonsları, speech servisi, web oynatıcı |
| S3 | 23 Kas – 6 Ara | M2 Ortak radyo | Tek ortak yayın akışı, yazılı istek ve ortak kuyruk, şarkı arama, ruh hâli etiketlerinden ilk değerlik/enerji |
| S4 | 7 – 20 Ara | M3 Duygulu sunucu | Metinden duygu ve ton adayları, 7 duygu için ses ayarları, müzik analizi, bağlama göre parça seçimi |
| S5 | 21 Ara – 3 Oca | M3 Duygulu sunucu | Sesten duygu tanıma ve doğrulama döngüsü, prozodi, hava durumu ve haber |
| S6 | 4 – 17 Oca | M4 Dönem sonu | PWA, yönetim paneli, yedek içerik, ölçüm kayıtları, dinleyici testi sayfası, rapor ve demo |

**2. dönem**
- Ses modelinin ince ayarı
- En az 24 katılımcıyla dinleyici deneyi ve istatistiksel değerlendirme
- Final raporu, bildiri ve sunum
- Zaman kalırsa ek özellikler: sesli ve telefonla istek, avatar

## Modüller

Her modülün bir sorumlusu vardır; sorumlu o alanı takip eder ve kararlarını verir. Issue'lar atanmamış açılır, herkes her sprintte kendini atar: önce kendi modülünden, gerekirse diğerlerinden. Sprint yükü tahmini puanlarla dengelenir, PR'lar çapraz incelenir. Modüllerin 1. dönem iş yükü yaklaşık eşittir ve her birinde bir yapay zekâ parçası vardır.

| Modül | Kapsam | Sorumlu |
|---|---|---|
| 🧠 DJ Brain & Emotion | Metinden duygu (değerlik ve uyarılmışlık) ve ton adayları, LLM metin servisi, yönetmen (anonsun tonu ve süresi), haber ve hava durumu anonsları, güvenlik filtresi, yazılı istekleri anlama, sesten duygu tanıma modelinin eğitimi ve doğrulama ölçümleri | Nisa Nur Aklan |
| 🎙️ Voice & Broadcast | Duygulu ses (TTS) ve 7 duygu için ayarlar, prozodi kontrolü, doğrulama döngüsünün sentez hattına eklenmesi, yayın planlayıcı (ortak sıra), ses karıştırma (geçişler, ses seviyesi), HLS akışı, yayın ayarları | Azra İdiz |
| 🎵 Music & Platform | Müzik kataloğu ve lisanslar, müzik analizi (değerlik, enerji), seçim puanı ve "neden bu şarkı?", ortak istek kuyruğu, yedek içerik, backend API, kullanıcılar ve KVKK, web/PWA oynatıcı, yönetim paneli, dinleyici testi sayfası | Nisanur İlhan |

**Modüller arası sınır:** DJ Brain her anons için ne söyleneceğine, hangi duyguyla ve ne kadar sürede söyleneceğine karar verir. Voice & Broadcast anonsları seslendirir, şarkılar ve isteklerle birlikte tek ortak sıraya dizer ve bütün dinleyicilere yayınlar. Music & Platform şarkıları, kullanıcıları ve istekleri sağlar. Bu sınır ortak bir veri sözleşmesiyle tanımlanır.

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
│   │   ├── radio/          yayın planlayıcı ve uçtan uca kontrol
│   │   ├── content/        LLMClient ve GeminiClient, DJ anonsları, yönetmen
│   │   └── speech_client/  speech servisine bağlanan istemci
│   ├── alembic/            veritabanı migration'ları
│   └── tests/              pytest testleri
├── web/                    React + TypeScript (Vite) web arayüzü
├── speech/                 duygulu ses servisi ve TTS deneyleri (ayrı Python ortamı)
├── scripts/                yardımcı script'ler (ör. müzik indirme)
├── docs/                   rapor, araştırma ve toplantı notları
└── docker-compose.yml      PostgreSQL
```

## Kurulum ve çalıştırma

Gerekenler: Windows 11, Python 3.12 (backend ve speech servisi; speech 3.11 ile de çalışır), Node.js (LTS), Docker Desktop. Komutlar PowerShell içindir ve repo kök klasöründen başlar.

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

Anonsları seslendiren servis backend'den ayrı çalışır ve kendi Python ortamını (**3.12**, 3.11 de olur) kullanır. Kurulum bir kez yapılır. Ubuntu komutları, GPU'lu kurulum (Orpheus) ve ayarlar için: [speech/service/README.md](speech/service/README.md).

Yeni bir terminalde:

```powershell
cd speech\service
py -3.12 -m venv .venv
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
