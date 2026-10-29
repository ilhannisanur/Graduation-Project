# Duygulu İngilizce TTS Modellerinin Karşılaştırması

Issue: #4 · Sprint: S1 · Modül: Voice & Broadcast · İlgili gereksinimler: 5, 6, 18 · Hazırlayan: Azra İdiz
Durum: _taslak; ölçümler tamamlanınca doldurulacak_

## Özet ve karar

* **Seçilen model:** _model_ — _2–3 cümlelik gerekçe (dinleme puanı, duygu kontrolü, hız, lisans)_
* **Yedek model:** _model_ — _gerekçe_. Ana model veya GPU kullanılamazsa devreye girer (#26).
* **Nerede çalışacak:** _laptop CPU / okul GPU'su / bulut_

## 1. Amaç

Radyonun DJ anonslarını seslendirecek modeli kanıta dayanarak seçmek. Model şu üç şartı karşılamalı:

* DJ Brain'in belirlediği duyguyu sese yansıtabilmeli.
* Doğal bir İngilizce sunucu gibi konuşmalı (gereksinim 6: doğru telaffuz, uygun vurgu, doğal hız).
* Elimizdeki donanımda yayını aksatmayacak hızda çalışmalı.

## 2. Yöntem

**Test seti:** 7 duygu × 5 cümle = 35 cümle (`speech/experiments/tts_bench/test_set.json`).

* Duygular: neutral, happy, excited, calm, sad, serious, surprised. Bu etiketler ekibin ortak duygu listesiyle aynıdır: DJ Brain anonsun duygusunu bu etiketlerle belirler, Music modülü şarkı seçiminde aynı etiketleri müzik etiketlerine eşler.
* Her duygudan 1 cümle **ortak metin**dir: aynı cümle 7 duyguda okunur, duyguyu sadece ses taşır.
* Kalan 4 cümle, metni de o duyguya uyan gerçekçi anonslardır.

**Tek komut:** `speech/experiments/run_experiments.sh` (Ubuntu; Windows için `run_experiments.ps1`). Her modeli kendi sanal ortamında çalıştırır ve özet tabloları üretir. Kurulum da tek komut: `setup_ubuntu.sh`.

**Donanım:**

| Ortam | Donanım | Not |
|---|---|---|
| Laptop | Intel i7-1165G7 (4 çekirdek), 16 GB RAM, Ubuntu _sürüm_ | NVIDIA MX350 (2 GB, Pascal) var ama kullanılamıyor: güncel PyTorch sürümleri bu mimariyi desteklemiyor ve 2 GB modellere yetmiyor. Bu yüzden yerel ölçümler CPU'da yapıldı. |
| Colab | NVIDIA T4, 16 GB | Bütün açık kaynak adayların GPU hızı ve **GPU belleği**; Orpheus yalnızca burada çalışır |
| ElevenLabs | Bulut API | Ticari referans; RTF ağ gecikmesini de içerir |

**Ölçümler:**

* RTF (üretim süresi / ses süresi)
* Model yükleme süresi
* RAM ve GPU tepe belleği
* Ses seviyesi ve baştaki/sondaki sessizlik
* Hazır bir konuşma-duygu modeliyle kaba otomatik duygu kontrolü
* Her modelin her duygu için kullandığı gerçek ayarlar ve etiketler (4.4, otomatik)

**Kör dinleme testi:**

* 3 kişi; model adları gizli, herkes farklı rastgele sırada dinler.
* Her modelden 14 klip (her duygudan 2).
* Her klip için doğallık (1–5) ve algılanan duygu (7 seçenekten biri) işaretlenir. Yanlış okunan kelimeler ve ses bozuklukları not sütununa yazılır (gereksinim 6).
* 7 duyguda şans düzeyi yaklaşık %14'tür.
* Bütün modeller **kadın sesiyle** konuşur: Kokoro `af_heart`, Chatterbox yerleşik ses, StyleTTS2 LJSpeech, Orpheus `tara`, ElevenLabs: _seçilen ses adı_. Böylece puanlar ses cinsiyetinden etkilenmez.

**Yayın ölçütü:** Bir sonraki anons, şarkı çalarken arka planda üretilir. 15 saniyelik bir anons 3 dakikalık bir şarkı bitmeden üretilebiliyorsa model o donanımda tek dinleyici için yeterlidir.

## 3. Adaylar: duygu kontrolü, ses seçimi, lisans ve filigran

| Model | Boyut | Duygu nasıl verilir | Ses seçimi (gereksinim 5) | Lisans | Filigran |
|---|---|---|---|---|---|
| Kokoro | 82M | Duygu girdisi yok; sadece hız ve ses seçimi | Hazır İngilizce sesler (Amerikan ve İngiliz, kadın ve erkek) | Apache-2.0 | Yok |
| Chatterbox | 500M | `exaggeration`, `cfg_weight`, duygu başına referans ses | Yerleşik ses + rızası alınmış kısa bir kayıttan istenen ses | MIT | Var: Resemble Perth (duyulmaz) |
| Chatterbox Turbo | 350M | Referans ses, `[laugh]`/`[chuckle]`. `exaggeration` ve `cfg_weight` kaynak kodda yok sayılıyor | Rızası alınmış referans kayıttan | MIT | Var: Perth |
| StyleTTS2 | — | `embedding_scale`, referans ses | Referans kayıttan (çok konuşmacılı model) | Kod MIT; ön eğitimli model için yazarların kullanım koşulu: _kontrol et_ | Yok |
| Orpheus | 3B | Metin içi etiketler (`<laugh>`, `<sigh>`, `<gasp>`); sayısal ayar yok | 8 hazır ses (tara, leah, jess, leo, dan, mia, zac, zoe) | Apache-2.0 (Llama tabanlı; model sayfasındaki koşullar kabul edilmeli) | Yok |
| ElevenLabs | Kapalı (bulut) | `eleven_v3` etiketleri (`[excited]`, `[sad]`...), `stability` | Geniş hazır ses kütüphanesi | Ticari hizmet. Ücretsiz plan: ticari olmayan kullanım, kaynak belirtme şartı, aylık ~10.000 karakter. Yayın için ücretli plan gerekir | Ücretli bulut servisi; dinleyici verisi gönderilemez |

Her duygu için gerçekten kullanılan değerler 4.4'teki otomatik tabloda. Dinleyerek değiştirdiğin değerler varsa burada kısaca nedenini yaz: _doldur_

## 4. Sonuçlar

_`results/summary.md` içindeki dört tabloyu buraya yapıştır:_

### 4.1 Hız ve kaynak

### 4.2 Kör dinleme puanları (3 kişi)

### 4.3 Duygu bazında tanınma

### 4.4 Her modelin duyguyu nasıl verdiği (kullanılan ayarlar)

## 5. Gözlemler

| Model | Güçlü yanı | Zayıf yanı | Telaffuz hataları (dinleyici notları) | Kurulum / çalıştırma notu |
|---|---|---|---|---|
| Kokoro | | | | _doldur_ |
| Chatterbox | | | | CPU'da 35 cümle: _süre_ |
| Chatterbox Turbo | | | | |
| StyleTTS2 | | | | _doldur_ |
| Orpheus | | | | Laptopta çalıştırılamadı (vLLM sadece Linux+GPU; 3B model CPU'da gerçek zamandan onlarca kat yavaş). Colab sonucu: _doldur_ |
| ElevenLabs | | | | Bulut, API anahtarı ile; maliyet: _doldur_ |

## 6. Karar gerekçesi

_Seçilen ve yedek modelin neden seçildiğini, elenen modellerin neden elendiğini yaz. Ölçütler: dinleme testindeki duygu tanınma oranı, doğallık, telaffuz (gereksinim 6), ses seçimi imkânı (gereksinim 5), laptopta veya hedef sunucuda yeterli hız, lisans ve maliyet, Türkiye'den erişim ve kişisel veri kuralı (bulut servislere dinleyici verisi gönderilmez)._

## 7. S2'ye etkisi (#8 Speech servisi)

* Servis, `tts_bench/engines/base.py` arayüzünü (`SynthesisRequest` → `Audio`) kullanacak. Motor değiştirmek böylece tek satırlık bir değişiklik olacak.
* Aynı metin, duygu ve ses için önbellek kullanılacak.
* Veri sözleşmesinde Voice tarafını ilgilendiren alanlar:
  * DJ Brain'den gelenler: `text`, `emotion`, `intensity`, `voice_id`, `target_duration_s`
  * Voice'un döndürdükleri: `audio_uri`, `duration_s`, `sample_rate`, `loudness_lufs`

## 8. Ses kaynakları ve izinler

| Referans dosyası | Kimin sesi | Rıza | Tarih |
|---|---|---|---|
| refs/neutral.wav | | | |
| refs/happy.wav | | | |
| refs/excited.wav | | | |
| refs/calm.wav | | | |
| refs/sad.wav | | | |
| refs/serious.wav | | | |
| refs/surprised.wav | | | |

Konu belgesinin 18. maddesi gereği gerçek kişilerin sesi izinsiz taklit edilmez. Ses dosyaları repoda tutulmaz; dinleme testi klipleri ekip Drive'ında saklanır.

## 9. Kabul kriterleri

- [ ] Üç kişinin kör dinleme puanları bir tabloda (4.2)
- [ ] GPU belleği ve hız ölçüldü (4.1; Colab T4)
- [ ] Her modelde duygunun nasıl verildiği not edildi (3 ve 4.4)
- [ ] Seçilen model, yedek model ve nedenleri (Özet ve 6. bölüm)
- [ ] Ses dosyaları repoya girmedi (`git ls-files "*.wav"` boş döner)
