# Emotion-Aware AI Radio

**Duygu Odaklı Yapay Zekâ Radyosu**

Sunuculuğunu yapay zekânın yaptığı, konuştuğu konuya göre sesine duygu katan ve dinleyicinin ruh hâline uygun şarkı seçen bir radyo. Planlanan yetenekler:

* **Duygulu sunuculuk:** Sevinçli bir haberde heyecanlı ve içten, üzücü bir olayda üzgün bir ses tonuyla Türkçe konuşma
* **Bağlama duyarlılık:** Hava durumu, günün saati, gündem ve özel günlere göre yayının ruh hâlini belirleme
* **Ruh hâline göre müzik:** Yağmurlu bir akşamda sakin, güzel bir haberde neşeli şarkı seçme
* **Açıklanabilirlik:** "Bu şarkıyı yağmur yağdığı için seçtim" gibi kararlarının nedenini gösterme
* **Web ve mobil:** Radyoyu tarayıcıdan ve telefondan canlı dinleyebilme

Bitirme Projesi · Ankara Bilim Üniversitesi · 2026–2027<br>
Danışman: Prof. Dr. Hakan Çağlar

## Durum

🚧 **Planlama ve araştırma aşaması.**

* Proje konusu belirlendi.
* Projenin büyük bölümünün 1. dönemde tamamlanması hedefleniyor.
* Projenin ana zorluğu: **sese duygu verme**.
* Hoca onayı bekleniyor: ses modeli ve metin üretimi için kullanılacak hazır araçlar.

## Nasıl Çalışacak?

```
Bağlam toplama        → hava durumu, saat, gündem, özel günler
        ↓
Duygu analizi         → haberin / anın duygusu (mutlu, üzgün, heyecanlı, sakin...)
        ↓
Sunucu metni          → duyguya uygun konuşma metni ("Güüünaydın sevgili dinleyiciler...")
        ↓
Duygulu ses üretimi   → metnin doğru duygu tonunda seslendirilmesi
        ↓
Duygu kontrolü        → üretilen sesin duygusunun ölçülmesi, gerekirse yeniden üretim
        ↓
Müzik seçimi          → ruh hâline uygun şarkının seçilmesi
        ↓
Yayın akışı           → konuşma ve şarkıların sıralanması, geçişler
        ↓
Web ve mobil          → canlı dinleme, çalan şarkı, "neden bu şarkı?"
```

## Sese Duygu Verme Yaklaşımı

Duygulu ses katman katman geliştirilecek. Her katman tek başına çalışır, bir üstteki katman sonucu iyileştirir:

1. **Temel duygulu ses:** Türkçe destekleyen açık kaynak bir ses modeli, duyguya uygun örnek seslerle yönlendirilir.
2. **Prozodi kontrolü:** Duyguya göre konuşma hızı, ses perdesi, vurgu ve duraklamaların kendi kodumuzla ayarlanması.
3. **Duygu tanıma ile kalite kontrolü:** Üretilen sesin duygusunu ölçen bir model; istenen duygu tutmazsa ses yeniden üretilir.
4. **İnce ayar (2. dönem):** Ses modelinin duygu etiketli Türkçe kayıtlarla iyileştirilmesi.

## Planlanan Teknolojiler

| Alan | Aday teknolojiler | Durum |
|---|---|---|
| Duygulu ses (TTS) | Chatterbox Multilingual | Denenecek, hoca onayı bekleniyor |
| Ses işleme | librosa, pyworld | Araştırılacak |
| Metin duygu analizi | BERTurk | Araştırılacak |
| Sesten duygu tanıma | Türkçe duygu etiketli ses veri setleri | Araştırılacak |
| Sunucu metni | LLM API | Hoca onayı bekleniyor |
| Müzik analizi | librosa, telifsiz (Creative Commons) müzik arşivi | Araştırılacak |
| Bağlam verisi | Hava durumu ve haber API'leri | Araştırılacak |
| Backend | Python, FastAPI | Olası |
| Web | React | Olası |
| Mobil | React Native veya PWA | Belirlenmedi |
| Yayın | Canlı ses akışı (streaming) | Araştırılacak |

## Klasör Yapısı (taslak)

Teknolojiler belirlendikçe değişecek.

```
Graduation-Project/
├── context/        bağlam toplama: hava durumu, saat, gündem
├── emotion/        metin duygu analizi ve sesten duygu tanıma
├── script/         sunucu metni üretimi
├── tts/            duygulu ses üretimi ve prozodi kontrolü
├── music/          müzik analizi ve ruh hâline göre seçim
├── broadcast/      yayın akışı ve canlı ses akışı
├── backend/        API
├── web/            web arayüzü
├── mobile/         mobil uygulama
└── docs/           rapor, araştırma notları, toplantı notları
```

## Yol Haritası

**1. dönem**
- [ ] Literatür ve araç araştırması
- [ ] Türkçe duygulu ses denemeleri
- [ ] Bağlam toplama ve metin duygu analizi
- [ ] Sunucu metni üretimi
- [ ] Duygulu ses üretimi ve prozodi kontrolü
- [ ] Sesten duygu tanıma ile kalite kontrolü
- [ ] Müzik analizi ve ruh hâline göre şarkı seçimi
- [ ] Yayın akışı ve canlı yayın
- [ ] Web ve mobil arayüz

**2. dönem**
- [ ] Ses modelinin ince ayarı
- [ ] Dinleyici testleri ve değerlendirme
- [ ] Rapor ve sunum

## Çalışma Kuralları

* Ses kayıtları ve müzik dosyaları repoya commit'lenmez.
* API anahtarları yalnızca `.env` dosyasına yazılır, commit'lenmez.

## Ekip

* Nisanur İlhan · Software Engineering
* Nisa Nur Aklan · Software Engineering
* Azra İdiz · Information Systems Engineering
