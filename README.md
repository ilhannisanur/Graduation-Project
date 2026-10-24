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

Herkes panodan istediği görevi seçebilir; her modülün öncelikle ilgilenen bir sorumlusu vardır.

| Modül | Kapsam | Sorumlu |
|---|---|---|
| 🎙️ Speech | Duygulu ses (TTS), prozodi, sesten duygu tanıma; 2. dönemde konuşma tanıma ve telefon | Nisa Nur Aklan |
| 📻 Radio Engine | Müzik kataloğu ve analizi, şarkı seçimi, kişiselleştirme, yayın planlayıcı, istek kuyruğu, ses karıştırma, yayın akışı | Nisanur İlhan |
| 🧠 Platform & Content | Backend API, kullanıcılar ve izinler, web/PWA, yönetim paneli, LLM metinleri, hava durumu ve haber | Azra İdiz |

## Klasör Yapısı (taslak)

```
Graduation-Project/
├── backend/    FastAPI uygulaması (API, Radio Engine, içerik, veritabanı)
├── web/        React + TypeScript web arayüzü
├── speech/     duygulu ses servisi (ayrı Python ortamı)
├── scripts/    yardımcı script'ler (ör. müzik indirme)
└── docs/       rapor, araştırma ve toplantı notları
```

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
