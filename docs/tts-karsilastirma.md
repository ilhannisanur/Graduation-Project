# Duygulu İngilizce TTS Modellerinin Karşılaştırması

Issue: #4 (ek test: #55) · Sprint: S1 · Modül: Voice & Broadcast · İlgili gereksinimler: 5, 6, 8, 18 · Hazırlayan: Azra İdiz
Durum: **tamamlandı** (29.10.2026). Ölçümler ve 3 kişilik kör dinleme testi bitti; karar aşağıda.
Güncelleme (31.10.2026): ElevenLabs ile Orpheus'un kör karşılaştırması eklendi (#55, 6.3). Karar değişmedi.

## Özet ve karar

* **Seçilen model: Orpheus 3B** (Canopy Labs).
  - Kör dinleme testinde üç dinleyicinin **üçü de** en doğal modeli Orpheus olarak puanladı (doğallık ortalaması 3,41 / 5; diğerleri 1,88–2,64).
  - Dinleyicilerin istenen duyguyu doğru tanıma oranı en yüksek bu modelde: **%52**. Diğer modellerde %29–36; 7 duyguda şans düzeyi yaklaşık %14.
  - Metnin duyguyu ele vermediği ortak cümlede de en yüksek oran onda (%29, şansın yaklaşık 2 katı).
  - Lisansı Apache-2.0, çıktıda filigran yok, 8 hazır sesi var (gereksinim 5).
  - Eksi yanları: GPU gerektiriyor (T4'te 6,7 GB) ve yavaş. 15 saniyelik bir anonsu T4'te yaklaşık 53 saniyede üretiyor. Anons şarkı çalarken (~180 sn) hazırlandığı için tek dinleyicide yayını aksatmıyor.
* **Yedek model: Kokoro 82M.**
  - CPU'da gerçek zamandan yaklaşık 3 kat hızlı (RTF 0,31; 15 saniyelik anons 4,7 sn), 1,7 GB RAM ile çalışıyor, Apache-2.0.
  - GPU kullanılamazsa ya da Orpheus hata verirse yayın susmaz (gereksinim 8; yedek içerik #26).
  - Bedeli: Kokoro'nun duygu girdisi yok; yedek modda anonslar duygusuz okunur.
* **Nerede çalışacak:** Ana model **GPU'da** çalışacak. GPU'nun kiralanması ya da okulla görüşülmesi seçenekleri değerlendiriliyor; karar #8 başında netleşecek. En az gereksinim: 8 GB'tan fazla VRAM (ölçülen tepe 6,7 GB). T4 sınıfı bir GPU tek dinleyici için yeterli.
* **ElevenLabs:** Ticari referans olarak ölçüldü (RTF 0,71) ve ayrı bir kör testte (#55, 6.3) Orpheus ile karşılaştırıldı. Orpheus en az ElevenLabs kadar iyi bulundu (doğallık 3,62'ye 3,06; duygu isabeti %47'ye %39; ortak cümlede %33'e %10). Ücretli bir servise geçmek için bir gerekçe çıkmadı.

Bu karar #8'in (Speech servisi) girdisidir: Speech servisi Orpheus'u ana motor, Kokoro'yu yedek motor olarak kullanır (7. bölüm).

## 1. Amaç

Radyonun DJ anonslarını seslendirecek modeli kanıta dayanarak seçmek. Model şu üç şartı karşılamalı:

* DJ Brain'in belirlediği duyguyu sese yansıtabilmeli.
* Doğal bir İngilizce sunucu gibi konuşmalı (gereksinim 6: doğru telaffuz, uygun vurgu, doğal hız).
* Yayını aksatmayacak hızda çalışmalı (gereksinim 8: istenmeyen sessizlik olmamalı).

## 2. Yöntem

**Test seti:** 7 duygu × 5 cümle = 35 cümle (`speech/experiments/tts_bench/test_set.json`).

* Duygular: neutral, happy, excited, calm, sad, serious, surprised. Bu etiketler ekibin ortak duygu listesiyle aynıdır: DJ Brain anonsun duygusunu bu etiketlerle belirler, Music modülü şarkı seçiminde aynı etiketleri müzik etiketlerine eşler.
* Her duygudan 1 cümle **ortak metin**dir: aynı cümle 7 duyguda okunur, duyguyu sadece ses taşır.
* Kalan 4 cümle, metni de o duyguya uyan gerçekçi anonslardır.

**Tek komut:**

* Kurulum: `speech/experiments/setup_ubuntu.sh`
* Deney: `speech/experiments/run_experiments.sh` (Windows için `run_experiments.ps1`). Her modeli kendi sanal ortamında çalıştırır ve özet tabloları üretir.
* GPU ölçümleri: `speech/experiments/colab/tts_benchmark_gpu.ipynb`

**Donanım:**

| Ortam | Donanım | Not |
|---|---|---|
| Laptop | Intel i7-1165G7 (4 çekirdek / 8 iş parçacığı), 16 GB RAM, Ubuntu 26.04 LTS | NVIDIA MX350 (2 GB, Pascal) kullanılamadı: güncel PyTorch sürümleri bu mimariyi desteklemiyor ve 2 GB modellere yetmiyor. Yerel ölçümler CPU'da yapıldı. |
| Colab | NVIDIA T4, 16 GB | Dört açık kaynak adayın GPU hızı ve GPU belleği; Orpheus yalnızca burada çalıştı |
| ElevenLabs | Bulut API (`eleven_v3`) | Ticari referans; RTF ağ gecikmesini de içerir |

**Ölçümler:**

* RTF: üretim süresi / ses süresi; 1'in altı gerçek zamandan hızlı.
* Model yükleme süresi
* RAM ve GPU tepe belleği
* Baştaki ve sondaki sessizlik
* Her modelin her duygu için kullandığı gerçek ayarlar ve etiketler (4.4)

**Kör dinleme testi:**

* 3 dinleyici: Azra, Nisa, Nisanur. Model adları gizli; herkes farklı rastgele sırada dinledi.
* Dinlenen modeller: Orpheus, Chatterbox, StyleTTS2, Kokoro (T4 çıktıları). Her modelden 35 klip, toplam 140 klip. Kişi başı 140 puan, toplam 420 puan; eksik puan yok.
* Her klip için doğallık (1–5) ve algılanan duygu (7 seçenekten biri) işaretlendi. Yanlış okunan kelimeler ve ses bozuklukları not alanına yazıldı (gereksinim 6).
* Dinleme, her kişiye özel tek dosyalık bir tarayıcı sayfasıyla yapıldı (`tts_bench.listening_page`). Sesler sayfaya MP3 (128 kbps, mono) olarak gömüldü; bütün klipler aynı dönüşümden geçti.
* 7 duyguda şans düzeyi yaklaşık %14'tür.

**Yayın ölçütü:** Bir sonraki anons, şarkı çalarken arka planda üretilir (yayın planlayıcı #9). 15 saniyelik bir anons 3 dakikalık bir şarkı bitmeden üretilebiliyorsa model, o donanımda tek dinleyici için yeterlidir.

## 3. Adaylar: duygu kontrolü, ses seçimi, lisans ve filigran

| Model | Boyut | Duygu nasıl verilir | Ses seçimi (gereksinim 5) | Lisans | Filigran |
|---|---|---|---|---|---|
| Kokoro | 82M | Duygu girdisi yok; sadece konuşma hızı | Hazır İngilizce sesler (Amerikan ve İngiliz, kadın ve erkek); testte `af_heart` (kadın) | Apache-2.0 | Yok |
| Chatterbox | 500M | `exaggeration`, `cfg_weight`; isteğe bağlı referans ses | Yerleşik ses (testte **erkek** sesi) + rızası alınmış kısa bir kayıttan istenen ses | MIT | Var: Resemble Perth (duyulmaz) |
| Chatterbox Turbo | 350M | Referans ses, `[laugh]`/`[chuckle]`. `exaggeration` ve `cfg_weight` kaynak kodda yok sayılıyor | Referans kayıttan | MIT | Var: Perth |
| StyleTTS2 | — | `embedding_scale`; isteğe bağlı referans ses | Referans kayıttan (çok konuşmacılı LibriTTS modeli); testte paketin varsayılan referans sesi | Kod ve `styletts2` paketi MIT. Ön eğitimli modellerin koşulu: eğitim setinde olmayan bir sesle üretimde, ses sahibinin izni yoksa, dinleyicilere seslerin yapay olarak üretildiği bildirilmeli. Radyo kendini yapay zekâ sunuculu olarak tanıttığı için bu koşul karşılanır. | Yok |
| Orpheus | 3B | Metin içi etiketler (`<laugh>`, `<chuckle>`, `<sigh>`, `<gasp>`); sayısal ayar yok | 8 hazır ses (tara, leah, jess, leo, dan, mia, zac, zoe); testte `tara` (kadın) | Apache-2.0. Llama tabanlı; model sayfasındaki koşullar kabul edildi. | Yok |
| ElevenLabs | Kapalı (bulut) | `eleven_v3` etiketleri (`[excited]`, `[sad]`...), `stability` | Geniş hazır ses kütüphanesi; testte `FGY2WhTYpPnrIDTdsKH5` (hazır kadın sesi) | Ticari hizmet. Ücretsiz plan ticari olmayan kullanım içindir ve kaynak belirtmeyi şart koşar; yayın için ücretli plan gerekir. | Ücretli bulut servisi; dinleyici verisi gönderilemez |

Chatterbox Turbo kuruldu ama ölçülmedi: Turbo'da duygu yalnızca referans ses ve etiketlerle verilebiliyor ve bu çalışmada referans ses kullanılmadı.

Her duygu için kullanılan değerler 4.4'te. Varsayılan eşlemeler kullanıldı; dinleme testinden önce hiçbir değer değiştirilmedi.

## 4. Sonuçlar

### 4.1 Hız ve kaynak

| Model (ortam) | Klip | Yükleme (sn) | Ort. RTF | 15 sn anons üretimi (sn) | Şarkı süresine sığar mı? | RAM / GPU tepe (MB) | Baştaki / sondaki sessizlik (sn) |
|---|---|---|---|---|---|---|---|
| chatterbox-cpu | 35/35 | 14.9 | 4.63 | 69.5 | evet | 4211 / - | 0.09 / 0.13 |
| chatterbox-t4 | 35/35 | 21.4 | 0.93 | 14.0 | evet | 2265 / 3231 | 0.09 / 0.15 |
| elevenlabs-cloud | 35/35 | 0.0 | 0.71 | 10.6 | evet | 49 / - | 0.10 / 0.10 |
| kokoro-cpu | 35/35 | 5.3 | 0.31 | 4.7 | evet | 1733 / - | 0.31 / 0.49 |
| kokoro-t4 | 35/35 | 13.6 | 0.03 | 0.4 | evet | 2072 / 696 | 0.31 / 0.49 |
| orpheus-t4 | 35/35 | 72.4 | 3.54 | 53.1 | evet | 2622 / 6678 | 0.83 / 0.45 |
| styletts2-cpu | 35/35 | 19.5 | 0.84 | 12.6 | evet | 3054 / - | 0.28 / 0.32 |
| styletts2-t4 | 35/35 | 12.9 | 0.12 | 1.8 | evet | 2065 / 1545 | 0.28 / 0.31 |

* Bütün çalıştırmalarda 35 cümlenin 35'i hatasız üretildi.
* Orpheus laptopta çalıştırılamadı: 3B parametreli model CPU'da gerçek zamandan onlarca kat yavaş, vLLM arka ucu ise yalnızca Linux ve GPU'da çalışıyor. Orpheus, Colab'da transformers + SNAC arka ucuyla (`orpheus-hf`) çalıştırıldı.
* Otomatik duygu kontrolü (`score_emotion`) isteğe bağlıydı ve çalıştırılmadı; duygu değerlendirmesi kör dinleme testine dayanıyor.

### 4.2 Kör dinleme puanları (3 kişi)

| Model | Doğallık: Azra | Doğallık: Nisa | Doğallık: Nisanur | **Doğallık: ort.** | Duygu isabeti: Azra | Duygu isabeti: Nisa | Duygu isabeti: Nisanur | **Duygu isabeti: ort.** | Ortak cümlede isabet | Telaffuz/ses hatası işaretlenen |
|---|---|---|---|---|---|---|---|---|---|---|
| **orpheus-t4** | 3.71 | 3.46 | 3.06 | **3.41** | 66% | 40% | 51% | **52%** | **29%** | 10% |
| chatterbox-t4 | 2.97 | 2.69 | 2.26 | 2.64 | 40% | 31% | 37% | 36% | 24% | 18% |
| kokoro-t4 | 2.37 | 2.83 | 1.74 | 2.31 | 43% | 26% | 20% | 30% | 5% | 8% |
| styletts2-t4 | 1.54 | 2.91 | 1.17 | 1.88 | 46% | 26% | 14% | 29% | 19% | 10% |

* **Doğallık:** 1 = robot gibi, 5 = gerçek radyo sunucusu gibi.
* **Duygu isabeti:** dinleyicinin istenen duyguyu doğru söylediği kliplerin oranı.
* **Ortak cümle:** aynı metin her duyguda okundu; duyguyu yalnızca ses taşıyor.
* Orpheus, her üç dinleyicide de hem doğallıkta hem duygu isabetinde birinci.

### 4.3 Duygu bazında tanınma (3 dinleyici birlikte)

| Model | neutral | happy | excited | calm | sad | serious | surprised |
|---|---|---|---|---|---|---|---|
| orpheus-t4 | 27% | **73%** | 20% | **87%** | **73%** | 20% | **67%** |
| chatterbox-t4 | 40% | 53% | **87%** | 20% | 7% | 20% | 27% |
| kokoro-t4 | 67% | 7% | 20% | 47% | 7% | 33% | 27% |
| styletts2-t4 | **80%** | 13% | 13% | 20% | 7% | **53%** | 13% |

* Orpheus mutlu, sakin, üzgün ve şaşkın duygularını açıkça iletiyor.
* Orpheus'un zayıf olduğu duygular: heyecanlı (%20) ve ciddi (%20). Heyecanlıda Chatterbox çok daha iyi (%87).
* Kokoro ve StyleTTS2'nin yüksek "neutral" oranı bir başarı değil: bu modeller her duyguyu düz okuduğu için dinleyiciler çoğu klibe "neutral" dedi.

### 4.4 Her modelin duyguyu nasıl verdiği (kullanılan ayarlar)

Yoğunluk 0.7 (neutral için 0). CPU ve T4 çalıştırmalarında ayarlar aynıdır. Değerler `tts_bench/engines/` içindeki tablolardan gelir.

| Model | neutral | happy | excited | calm | sad | serious | surprised |
|---|---|---|---|---|---|---|---|
| Chatterbox (`exaggeration`, `cfg_weight`; temperature=0.8) | 0.5, 0.5 | 0.71, 0.465 | 0.92, 0.36 | 0.36, 0.535 | 0.605, 0.5 | 0.43, 0.535 | 0.815, 0.43 |
| Kokoro (`speed`) | 1.0 | 1.056 | 1.126 | 0.93 | 0.895 | 0.958 | 1.07 |
| StyleTTS2 (`embedding_scale`; alpha=0.3, beta=0.7, diffusion_steps=10) | 1.0 | 1.56 | 1.84 | 1.14 | 1.56 | 1.21 | 1.7 |
| Orpheus (etiket; temperature=0.6, top_p=0.95, repetition_penalty=1.1) | — | `<chuckle>` | `<laugh>` | — | `<sigh>` | — | `<gasp>` |
| ElevenLabs (etiket; stability=0.5) | — | `[cheerfully]` | `[excited]` | `[calmly]` | `[sad]` | `[seriously]` | `[surprised]` |

## 5. Gözlemler

| Model | Güçlü yanı | Zayıf yanı | Telaffuz / ses hataları (dinleyici notları) | Kurulum / çalıştırma notu |
|---|---|---|---|---|
| Orpheus | En doğal ses; nefes ve gülme gibi insan sesleri ("gülmesi çok hoşuma gitti"); mutlu, sakin, üzgün ve şaşkın duyguları iyi | Heyecanlı ve ciddi zayıf; yoğunluk ayarı yok; yavaş (T4'te RTF 3.54); 6,7 GB VRAM | Bazı kliplerde hafif cızırtı ("cızırtı var", "biraz cızırtı var"); bir mutlu klip "aşağılama gibi" algılandı | Laptopta çalışmıyor; Colab T4'te `orpheus-hf` ile çalıştı; Hugging Face'te model koşullarının kabulü gerekiyor |
| Chatterbox | Heyecanlıda çok güçlü (%87); duygu yoğunluğu sayısal olarak ayarlanabiliyor | Üzgün (%7) ve sakin (%20) zayıf; CPU'da yavaş (RTF 4.63); yerleşik ses erkek | En çok işaretlenen model (%18): "çok cızırtı var", "dedikleri anlaşılmıyor", "hızlı konuştu diye heyecanlı olmuyor" | CPU ve T4'te sorunsuz; torch 2.6.0'a sabit |
| Kokoro | En hızlı ve en hafif; CPU'da gerçek zamandan hızlı; temiz ses | Duygu yok (ortak cümlede %5); doğallık düşük | "Ses kalitesi baya iyi ama doğallık yok"; ara ara küçük cızırtı | CPU'da sorunsuz |
| StyleTTS2 | CPU'da da gerçek zamandan hızlı (RTF 0.84) | En düşük doğallık (1.88); duyguyu düz okuyor | "Cızırtı var ve çok kötü", "haber spikeri gibi" | Eski bağımlılıklar nedeniyle ayrı sanal ortam gerekiyor |
| ElevenLabs | Hızlı (RTF 0.71, ağ dahil); geniş ses kütüphanesi; nötr, mutlu, heyecanlı ve şaşkında Orpheus'tan biraz daha iyi tanındı (6.3) | Ücretli bulut servisi; dinleyici verisi gönderilemez; ücretsiz plan yayın için kullanılamaz; üzgün (%7) ve sakin (%33) zayıf; metin aynıyken duyguyu sesle neredeyse veremedi (ortak cümlede %10) | Telaffuz hatası işaretlenmedi; bir dinleyici birçok klibi "kötü" olarak niteledi | API anahtarı yalnızca `.env` içinde; tam set yaklaşık 3.600 karakter |

**Sınırlılıklar:**

1. **Ses cinsiyeti farklıydı.** Chatterbox'ın yerleşik sesi erkek, diğer modellerin sesleri kadındı. Bir dinleyici bunu notlarında belirtti. Puanlar ses cinsiyetinden etkilenmiş olabilir. Bu fark, Orpheus'un üstünlüğünü açıklamaya yetmez: Orpheus, kadın sesli diğer iki modelden de belirgin şekilde iyi.
2. **Dinleyiciler değişkendi.** Dinleyiciler ekip üyeleri ve sayıları 3. Dinleyiciler arasında fark var. Örneğin StyleTTS2'nin doğallığı Nisa'da 2.91, diğerlerinde 1.17–1.54. "Telaffuz/ses hatası" işaretlerinin tamamı (48) tek bir dinleyiciden geldi; diğer ikisi hiç işaretlemedi. 4.2'deki son sütun bu yüzden temkinli okunmalı. Yine de sıralamanın başı her üç dinleyicide de aynı: Orpheus.
3. **Ses formatı.** Dinleme klipleri MP3 128 kbps'ye çevrildi. Bütün modellere aynı işlem uygulandığı için karşılaştırmayı bozmaz.
4. **Cızırtının kaynağı belli değil.** Bildirilen cızırtıların modelden mi, ses formatından mı geldiği ayrıştırılmadı. Orpheus için bu konu #8'de ham WAV çıktılarıyla incelenecek.
5. **#55'teki dinleyiciler Orpheus kliplerini tanıyordu.** Orpheus'un 35 klibi #4'te de dinlenmişti; ElevenLabs klipleri ise yeniydi. Sıra karışık ve klip numaraları farklıydı, ama tanıdıklık puanları etkilemiş olabilir.
6. **ElevenLabs tek bir ayarla denendi.** Tek ses (`FGY2WhTYpPnrIDTdsKH5`), `eleven_v3`, `stability=0.5`. Başka bir ses ya da ayar daha iyi sonuç verebilir.

## 6. Karar gerekçesi

### 6.1 Seçilen model: Orpheus

1. **Elenen model yok.** Dört adayın hepsi GPU'da 15 saniyelik anonsu şarkı bitmeden üretebiliyor (4.1). Bu yüzden hız kimseyi elemedi; karar dinleme sonuçlarına göre verildi.
2. **Duygu, projenin ana zorluğu.** Ortak cümlede (duygu yalnızca seste) Orpheus %29 ile en yüksek. Bütün kliplerde %52 ile açık ara önde. Duygu bazında 7 duygunun 4'ünde %67 ya da üzerinde (mutlu, sakin, üzgün, şaşkın).
3. **Doğallık.** Orpheus her üç dinleyicide de en doğal model (3.41). Ortalaması 3'ün üstünde olan tek aday.
4. **Lisans ve ses seçimi.** Apache-2.0, filigran yok, 8 hazır ses (gereksinim 5). Gerçek kişi sesi taklidi gerekmiyor (gereksinim 18).
5. **Bedeli.** GPU şart (6,7 GB VRAM) ve T4'te RTF 3.54. Tek dinleyici için anons şarkı sırasında hazırlanıyor (53 sn < 180 sn). Birden fazla eşzamanlı dinleyicide daha hızlı arka uç (vLLM) ya da daha güçlü GPU gerekecek.

### 6.2 Yedek model: Kokoro

* **Görevi:** Yedek modelin işi, ana model ya da GPU kullanılamadığında yayını sürdürmek (gereksinim 8, #26). Bu yüzden ölçüt duygu değil, **güvenilirlik ve hız**.
* **Neden Kokoro:** Laptop CPU'sunda RTF 0.31 ile gerçek zamandan hızlı, 1,7 GB RAM, Apache-2.0, filigran yok. Ses temiz; dinleyiciler "ses kalitesi iyi" dedi.
* **Neden diğerleri değil:**
  - Chatterbox duyguda daha iyi ama CPU'da 15 saniyelik anons için 70 saniye ve 4,2 GB RAM istiyor, yerleşik sesi erkek ve en çok cızırtı işaretlenen model.
  - StyleTTS2 doğallıkta en düşük.
* **Bedeli:** Yedek modda anonslar duygusuz okunur.

### 6.3 ElevenLabs ile karşılaştırma (#55)

ElevenLabs, #4'teki adaylar arasında değildi. Ticari bir üst sınır olarak sonradan eklendi. Seçilen Orpheus'un bu referansa ne kadar yakın olduğu ayrı bir kör testte ölçüldü (#55, 31.10.2026).

**Yöntem:** ElevenLabs (`eleven_v3`, hazır kadın sesi) ve Orpheus (`tara`), 35'er klip, toplam 70 klip. Klipler karışık sırada ve kör olarak dinlendi. Dinleyiciler #4'tekilerle aynı 3 kişi; kişi başı 70 puan, toplam 210 puan, eksik puan yok. #4'teki tarayıcı sayfası yöntemi kullanıldı.

**Kör dinleme puanları:**

| Model | Doğallık: Azra | Doğallık: Nisa | Doğallık: Nisanur | **Doğallık: ort.** | Duygu isabeti: Azra | Duygu isabeti: Nisa | Duygu isabeti: Nisanur | **Duygu isabeti: ort.** | Ortak cümlede isabet | Telaffuz/ses hatası işaretlenen |
|---|---|---|---|---|---|---|---|---|---|---|
| **Orpheus** | 3.46 | 3.69 | 3.71 | **3.62** | 54% | 40% | 46% | **47%** | **33%** | 2% |
| ElevenLabs | 3.46 | 3.63 | 2.09 | 3.06 | 51% | 46% | 20% | 39% | 10% | 0% |

**Duygu bazında tanınma (3 dinleyici birlikte; her hücre 15 puan):**

| Model | neutral | happy | excited | calm | sad | serious | surprised |
|---|---|---|---|---|---|---|---|
| Orpheus | 27% | 47% | 7% | **87%** | **67%** | **47%** | 47% |
| ElevenLabs | **47%** | **53%** | **40%** | 33% | 7% | 40% | **53%** |

**Sonuç:**

1. **Orpheus en az ElevenLabs kadar iyi.** Üç kişinin ortalamasında doğallıkta (3,62'ye 3,06) ve duygu isabetinde (%47'ye %39) önde.
2. **Fark tek dinleyicinin etkisinde.** Ortalamalar arasındaki farkın büyük kısmı bir dinleyiciden geliyor: Nisanur ElevenLabs'a 2,09 verdi. Diğer iki dinleyicide iki model neredeyse eşit: doğallık 3,58'e 3,55; duygu isabeti %47'ye %48,5. Bu yüzden sonuç "Orpheus daha iyi" değil, **"Orpheus en az ElevenLabs kadar iyi"** olarak okunmalı.
3. **Duyguyu yalnızca sesle vermekte Orpheus açıkça önde.** Metnin her duyguda aynı olduğu ortak cümlede Orpheus %33, ElevenLabs %10 (şans düzeyinin altında). Bu, DJ Brain'in seçtiği duygunun metinden bağımsız olarak sese yansıması için en önemli ölçüt.
4. **İki model birbirini tamamlıyor.** Orpheus sakin, üzgün ve ciddi duygularda güçlü. ElevenLabs heyecanlı (%40'a %7), nötr, mutlu ve şaşkın duygularda biraz daha iyi tanındı. Orpheus'un heyecanlı duygusundaki zayıflığı #4'te de görülmüştü (%20); #8 ve #22'de üzerinde çalışılacak.

**Karara etkisi:** #4'ün kararı değişmiyor. Ücretli bir bulut servisi, ölçülen hiçbir ana ölçütte belirgin bir üstünlük sağlamadı; üstelik sürekli maliyet getiriyor ve dinleyici verisi gönderilemiyor. Bu yüzden ElevenLabs yayında kullanılmayacak. Projede ana model Orpheus, yedek model Kokoro olarak kalıyor. GPU kiralamaya ödenecek maliyet, ücretli TTS planına göre daha mantıklı bir yatırım.

## 7. #8 (Speech servisi) için sonuçlar

* **Ana motor:** `OrpheusHFEngine` (GPU). Hazır; `tts_bench/engines/orpheus_engine.py`. Servis aynı arayüzü (`SynthesisRequest` → `Audio`) kullanacak.
* **Yedek motor:** `KokoroEngine` (CPU). GPU yoksa ya da Orpheus hata verirse otomatik devreye girer.
* **Gecikme:** Orpheus'un yavaşlığı yayın planlayıcıda (#9) önceden hazırlama ile gizleniyor; anons, önceki şarkı çalarken üretiliyor. Hazır değilse planlayıcı anonsu atlayıp şarkıya geçiyor, sessizlik olmuyor.
* **Önbellek:** Aynı metin, duygu ve ses için önbellek kullanılacak.
* **#8'de yapılacak iyileştirmeler:**
  1. Cızırtının kaynağını ham WAV üzerinde bulmak; SNAC çözücü ve örnekleme ayarlarını incelemek.
  2. Heyecanlı ve ciddi duygular için etiket ve metin stratejisi; prozodi çalışması #22.
  3. Eşzamanlı dinleyici için vLLM arka ucunu (`orpheus` motoru) ölçmek.
* **Donanım kararı:** GPU kiralama ya da okul GPU'su. En az 8 GB'tan fazla VRAM; T4 sınıfı yeterli. Karar #8 başında ekiple ve danışmanla verilecek.
* **Veri sözleşmesinde Voice tarafını ilgilendiren alanlar:**
  * DJ Brain'den gelenler: `text`, `emotion`, `intensity`, `voice_id`, `target_duration_s`
  * Voice'un döndürdükleri: `audio_uri`, `duration_s`, `sample_rate`, `loudness_lufs`

## 8. Ses kaynakları ve izinler

**Bu karşılaştırmada referans ses kaydı kullanılmadı.** Hiçbir gerçek kişinin sesi taklit edilmedi (gereksinim 18). Kullanılan sesler:

| Model | Ses | Kaynak |
|---|---|---|
| Orpheus | `tara` | Modelin hazır sesi |
| Chatterbox | Yerleşik ses | Modelle gelen hazır koşullandırma (`conds.pt`) |
| Kokoro | `af_heart` | Modelin hazır sesi |
| StyleTTS2 | Varsayılan referans sesi | `styletts2` paketinin varsayılanı |
| ElevenLabs | `FGY2WhTYpPnrIDTdsKH5` | ElevenLabs hazır ses kütüphanesi |

İleride referans ses kullanılırsa, ses sahibinin yazılı rızası alınacak ve bu bölüme kaydedilecek. Ses dosyaları repoda tutulmaz. Dinleme testi sayfaları yalnızca test süresince paylaşıldı ve test sonunda kaldırıldı.

## 9. Kabul kriterleri

- [x] Üç kişinin kör dinleme puanları bir tabloda (4.2: Azra, Nisa, Nisanur; doğallık ve duygu isabeti ayrı sütunlarda)
- [x] Hız ve GPU belleği her açık kaynak aday için ölçüldü (4.1; Colab T4)
- [x] Her modelde duygunun nasıl verildiği not edildi (3. bölüm ve 4.4)
- [x] Ek test (#55): ElevenLabs ve Orpheus için üç kişinin puanları bir tabloda (6.3)
- [x] Ek test (#55): sonuç 6.3 bölümüne eklendi
- [x] Seçilen model, yedek model ve nedenleri yazıldı ("Özet ve karar" ile 6. bölüm: Orpheus ve Kokoro)
- [x] Ses dosyaları repoya girmedi (`.gitignore`: results/, listening/, *.wav, *.mp3, .env; `git ls-files` ile kontrol edildi)
