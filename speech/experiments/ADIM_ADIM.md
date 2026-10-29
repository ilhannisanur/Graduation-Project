# #4 Adım adım rehber (Ubuntu)

Bu rehber, issue #4'ü (duygulu İngilizce TTS modellerini karşılaştırma) baştan sona yapmak içindir. Her adımda ne yaptığımız, neden yaptığımız, hangi komutları çalıştıracağın, ne görmen gerektiği ve sorun çıkarsa ne yapacağın yazıyor.

Kurulum ayrıntıları `README.md` dosyasında. Sonuçlar `docs/tts-karsilastirma.md` raporuna girer.

## Issue ile eşleşme

| Issue'daki madde | Nerede karşılanıyor |
|---|---|
| Adaylar: Chatterbox, Orpheus, StyleTTS2, Kokoro (+ ElevenLabs) | `tts_bench/engines/` içinde her biri için bir motor |
| Lisans ve filigran notu | Rapor, bölüm 3 |
| `speech/experiments/` altında tek komutla çalışan script | `./run_experiments.sh` (kurulum: `./setup_ubuntu.sh`) |
| 7 duygu × 5 cümle | `tts_bench/test_set.json`; duygular ekibin listesiyle aynı |
| Her modelde duygunun nasıl verildiği | Rapor bölüm 3 (yöntem) ve 4.4 (gerçekten kullanılan değerler, otomatik) |
| Hız (gerçek zaman oranı) | Rapor 4.1, `RTF` sütunu |
| GPU belleği | Rapor 4.1, Colab T4 ölçümleri (laptoptaki MX350 kullanılamıyor) |
| Kabul: 3 kişinin kör dinleme puanları bir tabloda | Rapor 4.2 (`summarize` üretir) |
| Kabul: seçilen model, yedek model, nedenleri | Rapor "Özet ve karar" ve bölüm 6 |
| Kabul: ses dosyaları repoya girmedi | `.gitignore` + Adım 9'daki kontrol |

---

## Adım 0 — Temiz başlangıç

**Ne:** Önceki denemelerden kalan klasörleri ve branch'i silip `main`'den yeni bir branch açıyoruz.

**Neden:** Eski 15 cümlelik sonuçlar ya da Windows'ta kurulmuş ortamlar yeni ölçümlere karışmasın. Bütün yerel ölçümler aynı işletim sisteminde (Ubuntu) yapılmalı ki karşılaştırma adil olsun.

1. **Kayıtları koru.** Referans ses kaydın varsa önce başka bir yere taşı.
2. **Temizle ve yeni branch aç:**

```bash
cd ~/Graduation-Project
git switch main && git pull
git branch -D feat/tts-comparison 2>/dev/null
git push origin --delete feat/tts-comparison 2>/dev/null   # açık PR varsa önce GitHub'da kapat
rm -rf speech/benchmarks speech/experiments docs/research docs/tts-karsilastirma.md
git switch -c feat/tts-comparison
```

3. **Panoyu güncelle.** #4'e kendini ata ve kartı **In progress**'e taşı.

**Beklenen:** `git status` temiz; `git branch --show-current` çıktısı `feat/tts-comparison`.

---

## Adım 1 — Kodu yerleştir ve kur

**Ne:** Zip'i repoya açıp tek komutla bütün ortamları kuruyoruz.

**Neden ayrı ortamlar:** Her modelin istediği paket sürümleri birbiriyle çakışıyor; örneğin Chatterbox `torch==2.6.0` istiyor, StyleTTS2 eski bir `transformers` istiyor. Bu yüzden her model kendi sanal ortamına kuruluyor:

| Ortam | İçindeki modeller |
|---|---|
| `.venv-kokoro` | Kokoro ve ElevenLabs |
| `.venv-chatterbox` | Chatterbox ve Turbo |
| `.venv-styletts2` | StyleTTS2 |

**Neden CPU torch:** Linux'ta varsayılan torch CUDA'lı gelir ve birkaç GB tutar. Senin ekran kartın zaten kullanılamadığı için betik CPU sürümünü kuruyor.

```bash
unzip -o ~/Downloads/azra-s1-tts-deneyleri-ubuntu.zip -d ~/Graduation-Project
cd ~/Graduation-Project/speech/experiments
./setup_ubuntu.sh
```

**Süre:** 30–45 dakika; çoğu indirme bekleme süresi.

**Beklenen:** Sonda `kokoro: OK`, `chatterbox: OK`, `styletts2: OK`, `tests: OK` satırları. ElevenLabs satırı `FAIL` olur, çünkü anahtar henüz yok; Adım 3'te düzelecek.

**Sorun olursa:**

* Betik hatanın olduğu log dosyasının son satırlarını gösterir; tam log `logs/setup-<ortam>.log` dosyasında.
* Sorunu düzeltip betiği tekrar çalıştır; biten ortamlar korunur.
* Bir ortamı sıfırdan kurmak için: `./setup_ubuntu.sh --recreate --only chatterbox`
* Yardım isterken `doctor` çıktısını gönder:

```bash
.venv-chatterbox/bin/python -m tts_bench.doctor --engines chatterbox
```

**İlk commit ve taslak PR.** Ekip ilerlemeyi görsün diye şimdi kaydet:

```bash
cd ~/Graduation-Project
git add speech/experiments docs/tts-karsilastirma.md
git status        # .venv, logs, .env, .wav GÖRÜNMEMELİ
git commit -m "feat(speech): TTS comparison toolkit, 7 emotions x 5 sentences (#4)"
git push -u origin feat/tts-comparison
gh pr create --draft --title "[S1-Voice] Duygulu İngilizce TTS modellerini karşılaştır" --body "Closes #4"
```

---

## Adım 2 — Her modeli bir cümleyle dinle

**Ne:** Tam ölçümden önce her modelin çalıştığını ve nasıl ses çıkardığını görüyoruz.

**Neden:** Tam ölçüm saatler sürebilir. Bir model bozuksa bunu şimdi, 1 dakikada anlamak daha iyi. İlk çalıştırmada modeller de inmiş olur.

```bash
cd ~/Graduation-Project/speech/experiments
.venv-kokoro/bin/python     -m tts_bench.say --engine kokoro     --emotion happy   --play "Good morning, Ankara!"
.venv-chatterbox/bin/python -m tts_bench.say --engine chatterbox --emotion sad     --play "Some difficult news tonight."
.venv-styletts2/bin/python  -m tts_bench.say --engine styletts2  --emotion excited --play "What a finish!"
```

**Beklenen:** Her komut bir `.wav` dosyası kaydeder ve oynatıcıda açar. Ekrana kullanılan ayarlar ve RTF yazılır.

**Dikkat edilecekler:**

* **Ses cinsiyeti.** Hepsi kadın sesi olmalı. Kör dinleme testinde farklı cinsiyet puanları etkiler.
* **Duygu.** `sad` gerçekten üzgün mü? `--intensity 1.0` ile en güçlü hâlini dinleyebilirsin.
* **Kokoro'nun sınırı.** Kokoro'da sadece hız değişir. Bu modelin bilinen bir sınırı ve bir bulgu.

---

## Adım 3 — ElevenLabs

**Ne:** Ticari bir modeli üst sınır (referans) olarak karşılaştırmaya ekliyoruz.

**Neden:** Açık kaynak modellerin "ne kadar iyi" olduğunu yorumlamak için bir karşılaştırma noktası lazım. Ayrıca yedek model seçeneklerinden biri olabilir.

1. **Anahtar oluştur.** elevenlabs.io'da ücretsiz hesap aç. **Developers → API Keys → Create** ile anahtar oluştur. İzinler:
   - Text to Speech: *Access*
   - Voices: *Access*
   - User: *Read*
2. **Anahtarı kaydet.** Bu dosya git'e girmez (`.gitignore`):

```bash
echo "ELEVENLABS_API_KEY=sk_buraya_anahtar" > .env
chmod 600 .env
```

3. **Bir kadın sesi seç.** Amerikan aksanlı ve kullanımı "narration" ya da "conversational" olan bir ses iyi olur. Diğer modeller kadın sesiyle konuştuğu için bu, dinleme testinin adilliği için gerekli.

```bash
.venv-kokoro/bin/python -m tts_bench.elevenlabs_tools voices --gender female
echo "ELEVENLABS_VOICE_ID=listeden_sectigin_voice_id" >> .env
```

4. **Kontrol et ve dene:**

```bash
.venv-kokoro/bin/python -m tts_bench.elevenlabs_tools check
.venv-kokoro/bin/python -m tts_bench.say --engine elevenlabs --emotion excited --play "What a finish!"
```

**Beklenen:** `check` çıktısında plan, kalan kota ve seçtiğin ses görünür. "test set: about 3,4xx characters" satırı bir tam çalıştırmanın maliyetini gösterir. Ücretsiz plan ayda yaklaşık 10.000 karakter veriyor, bu yüzden `--fresh` ile tekrar tekrar çalıştırma.

**Sorun olursa:**

* `401`: Anahtar yanlış ya da izinler eksik.
* `eleven_v3` modeli planında yoksa: komuta `--option model=eleven_multilingual_v2` ekle ve bunu rapora yaz.
* Ham ses (PCM) formatı planında yoksa araç kendiliğinden MP3'e geçer.

Rapora seçtiğin sesin adını ve planını yaz.

---

## Adım 4 — Referans sesler (isteğe bağlı, önerilir)

**Ne:** Bir ekip arkadaşının 7 duyguda kaydettiği kısa sesleri modellere örnek olarak veriyoruz.

**Neden:** Chatterbox ve StyleTTS2, verilen örneğin tonunu taklit edebiliyor. Bu, duygu kontrolünü belirgin şekilde güçlendirebilir. Konu belgesinin 18. maddesi gereği ses sahibinin **açık rızası** gerekiyor.

1. **Kayıt.** Her duygu için 8–10 saniye, sessiz bir odada, telefonla kayıt yapılabilir. Metin test cümlelerinden farklı olmalı: *"Hello everyone, welcome back to the show. Let's see what's coming up next."*
2. **Dönüştür.** Dosyaları `~/Downloads/<duygu>.m4a` adlarıyla koy ve çalıştır:

```bash
for e in neutral happy excited calm sad serious surprised; do
  ffmpeg -y -i ~/Downloads/$e.m4a -ac 1 -ar 24000 refs/$e.wav
done
```

3. **Rızayı kaydet.** Kimin sesi olduğunu ve rıza tarihini raporun 8. bölümüne yaz.

---

## Adım 5 — Tam ölçüm (tek komut)

**Ne:** Her modelle 35 cümle üretip hız, bellek ve ses ölçümlerini alıyoruz.

**Neden `tmux`:** Chatterbox CPU'da uzun sürer. `tmux` içinde çalışan iş, terminali kapatsan da devam eder.

1. **Hızlı deneme.** Her modelde 2 cümle; ElevenLabs'ta yaklaşık 200 karakter harcar:

```bash
./run_experiments.sh --limit 2
```

2. **Tam çalıştırma:**

```bash
tmux new -s tts
cd ~/Graduation-Project/speech/experiments
./run_experiments.sh                     # kokoro, chatterbox, styletts2, elevenlabs
# referans ses kaydettiysen, bitince:
./run_experiments.sh --engines chatterbox,chatterbox-turbo,styletts2 --refs refs
```

3. **tmux kullanımı.** Arka plana almak için Ctrl+B, sonra D. Geri dönmek için:

```bash
tmux attach -t tts
```

4. **Uyku.** Laptop şarjda ve otomatik askıya alma kapalı olsun.

**Beklenen:** Her model için `results/<model>-cpu/` klasörü (35 `.wav`, `metrics.csv`, `run_info.json`) ve sonda `results/summary.md`. ElevenLabs'ın klasörü `results/elevenlabs-cloud/`.

**Sorun olursa:** Yarıda kalırsa aynı komutu tekrar çalıştır; eksik cümlelerden devam eder ve ElevenLabs'ta aynı cümle için kota tekrar harcanmaz. Bir cümle hata verirse diğerleri yine üretilir; hata `run_info.json` içine yazılır.

**Ayar yapmak istersen:** Bir duygu kötü çıktıysa ilgili motor dosyasındaki tabloyu değiştir (`tts_bench/engines/<model>_engine.py`). Değişikliği `say` ile tek cümlede dinle. Beğenince o modeli baştan çalıştır:

```bash
./run_experiments.sh --engines chatterbox --fresh
```

Değişikliği ve nedenini rapora yaz.

---

## Adım 6 — GPU ölçümleri ve Orpheus (Colab)

**Ne:** Bütün açık kaynak modelleri ücretsiz Colab T4 GPU'sunda çalıştırıyoruz.

**Neden:** Issue GPU belleğinin ölçülmesini istiyor; MX350 bunun için kullanılamıyor. Orpheus da sadece GPU'da çalışabiliyor.

1. **Kodu zip'le:**

```bash
cd ~/Graduation-Project/speech/experiments
zip -r experiments.zip tts_bench pyproject.toml refs -x "*__pycache__*"
```

2. **Hugging Face'i hazırla (bir kez).** huggingface.co'da hesap aç. `canopylabs/orpheus-3b-0.1-ft` sayfasında koşulları kabul et. Settings → Access Tokens → **Read** tipinde bir token oluştur.
3. **Notebook'u aç.** colab.research.google.com → Upload → `colab/tts_benchmark_gpu.ipynb`. Runtime → Change runtime type → **T4 GPU**.
4. **Bölümleri sırayla çalıştır.** Her bölümden önce Runtime → Restart session yap ve Bölüm 0'ı çalıştır (zip'i yükler):
   - **A:** Orpheus (token ister)
   - **B:** Chatterbox
   - **C:** StyleTTS2
   - **D:** Kokoro
5. **Sonuçları ekle.** Her bölümün sonunda bir zip iner. Zip'in içinde zaten `results` klasörü olduğu için `results` içine değil, `experiments` klasörüne aç:

```bash
for z in ~/Downloads/results_*.zip; do unzip -o "$z" -d ~/Graduation-Project/speech/experiments; done
```

**Beklenen:** `results/` altında `orpheus-t4`, `chatterbox-t4`, `styletts2-t4` ve `kokoro-t4` klasörleri. Özet tablosunda bu satırların "GPU peak (MB)" sütunu dolu olur.

**Sorun olursa:** Orpheus hiçbir şekilde çalışmazsa hata mesajını rapora yaz. "Elimizdeki donanımla çalıştırılamadı" da geçerli bir bulgu.

---

## Adım 7 — Kör dinleme testi (3 kişi)

**Ne:** Üç kişi, hangi klibin hangi modele ait olduğunu bilmeden klipleri puanlıyor.

**Neden:** Issue'nun ilk kabul kriteri bu. Sayısal ölçümler duyguyu ve doğallığı tam ölçemez. Model adlarının gizli olması önyargıyı önler.

**Neden Excel değil de tarayıcı sayfası:** Excel'deki ses bağlantıları Windows'ta her tıklamada güvenlik uyarısı çıkarıyor. Mac Excel yerel ses dosyalarını çoğu zaman hiç açmıyor. Zip'in içinden açıldığında da bağlantılar kırılıyor. Bunun yerine herkese **tek bir HTML dosyası** gönderiyoruz. Bu dosyada:

* Bütün sesler dosyanın içine gömülü.
* Windows, Mac ve Linux'ta çift tıklayınca tarayıcıda açılıyor; Chrome, Edge, Safari ve Firefox'ta çalışıyor. Hiçbir şey kurmak gerekmiyor.
* Puanlar tarayıcıda otomatik kaydediliyor; kişi ara verip sonra devam edebiliyor.
* Sonunda **Sonuçları indir** düğmesi `rating_<isim>.csv` dosyasını indiriyor.

### 7.1 Klipleri ve sayfaları hazırla (Azra)

1. **Klipleri seç.** Bu adımı zaten yaptıysan, yani `listening/clips` klasörü ve `key.csv` dosyası duruyorsa, atla:

```bash
cd ~/Graduation-Project/speech/experiments
.venv-kokoro/bin/python -m tts_bench.listening --raters azra nisa nisanur --labels <dinlenecek modeller>
```

2. **Her kişi için sayfa üret:**

```bash
.venv-kokoro/bin/python -m tts_bench.listening_page --raters azra nisa nisanur
```

**Beklenen çıktı:** `listening/` altında `dinle_azra.html`, `dinle_nisa.html`, `dinle_nisanur.html` dosyaları; her biri yaklaşık 15–20 MB.

* Her kişi kendi `.xlsx` dosyasındaki karışık sırayı alır; sıralar kişiden kişiye farklıdır.
* Sesler sayfaya MP3 (128 kbps) olarak gömülür. Bütün klipler aynı işlemden geçtiği için karşılaştırma adil kalır.
* Kayıpsız ses istersen komuta `--format wav` ekle; dosya yaklaşık 4 kat büyür.

3. **Kendi sayfanı kontrol et.** `dinle_azra.html` dosyasını aç: bir klip çal, bir puan ver, sayfayı kapatıp tekrar aç. Puan duruyorsa her şey çalışıyor.

### 7.2 Gönder

1. **Drive'a yükle.** `dinle_nisa.html` ve `dinle_nisanur.html` dosyalarını Drive'a yükle ve her kişiye **sadece kendi dosyasını** paylaş. WhatsApp'tan "belge" olarak da gönderebilirsin.
2. **E-posta kullanma.** 25 MB sınırına takılabilir.
3. **`key.csv` gönderme.** Bu dosyayı ve `clips` klasörünü kimseye gönderme. Sayfada model adları yok, sadece klip numaraları var.
4. **Mesajı gönder.** Arkadaşlarına şu mesajı yapıştırabilirsin:

> Merhaba! #4 için kör dinleme testi hazır. Sana özel dosya: dinle_<isim>.html (Drive'da).
> 1. Dosyayı **indir** (Drive'da önizleme açılırsa sağ üstteki indir simgesine bas) ve Masaüstüne kaydet.
> 2. Dosyaya çift tıkla: tarayıcıda açılır (Windows: Chrome/Edge, Mac: Safari/Chrome). Kurulum yok.
> 3. Kulaklık tak. Her klip için doğallığı (1–5) ve sesten duyduğun duyguyu seç. Yanlış okunan kelime varsa "telaffuz hatası"nı işaretle, kısa not yaz.
> 4. Klavye kısayolları: Boşluk = çal, 1–5 = doğallık, harfler = duygu, → = sonraki.
> 5. Ara verebilirsin: aynı dosyayı aynı tarayıcıda açınca kaldığın yerden devam eder.
> 6. Bitince en alttaki "Sonuçları indir" düğmesine bas ve inen rating_<isim>.csv dosyasını bana gönder.
> Yaklaşık 45–60 dakika sürüyor (140 klip). Bitirene kadar kliplerle ilgili konuşmayalım 🙂

### 7.3 Kendi puanlaman

`dinle_azra.html` dosyasını kullanman önerilir; böylece herkes aynı arayüzle puanlar. LibreOffice'teki `rating_azra.xlsx` dosyasını doldurmaya başladıysan o da geçerli: özet, her kişi için **en çok doldurulmuş** dosyayı kullanır.

### 7.4 Sonuçları topla

1. **Dosyaları yerleştir.** Gelen `rating_nisa.csv` ve `rating_nisanur.csv` dosyalarını, kendi dosyanla birlikte, `listening/` klasörüne koy. Tarayıcı ad sonuna "(1)" eklediyse (örneğin `rating_nisa (1).csv`) sorun değil, özet bunu tanır.
2. **Tamamlanma kontrolü.** Kimin kaç klip doldurduğunu gör:

```bash
.venv-kokoro/bin/python -m tts_bench.summarize | grep -A6 "### 2."
```

**Sorun olursa:**

| Durum | Çözüm |
|---|---|
| Sayfa açılıyor ama ses gelmiyor | Önce oynatıcıdaki ▶ düğmesine bas. Tarayıcılar ilk sesi kullanıcı tıklamadan çalmaz. |
| Kaldığı yer kayboldu | Tarayıcı geçmişi temizlenmiş ya da dosya başka bir tarayıcıda açılmış. Daha önce "Sonuçları indir" ile ara kayıt alındıysa, **Önceki CSV'yi yükle** ile kaldığı yerden devam edilir. Bu yüzden arada bir ara kayıt indirmek iyi bir alışkanlık. |
| Telefon | Bilgisayar önerilir. iPhone'da Dosyalar uygulamasının önizlemesi sayfayı çalıştırmaz. |

---

## Adım 8 — Sonuç tabloları

**Ne:** Bütün ölçümleri ve puanları rapor tablolarına dönüştürüyoruz.

1. **Puanları topla.** Doldurulan dosyaları `listening/` klasörüne geri koy; aynı adla değiştir.
2. **Tabloları üret:**

```bash
.venv-chatterbox/bin/python -m tts_bench.score_emotion   # isteğe bağlı otomatik duygu kontrolü
.venv-kokoro/bin/python -m tts_bench.summarize
```

**Beklenen:** `results/summary.md` içinde dört tablo:

1. Hız ve kaynak (RTF, şarkı süresine sığıyor mu, RAM/GPU belleği)
2. Kör dinleme puanları: her kişinin ayrı sütunu ve ortalama
3. Duygu bazında tanınma (hangi model hangi duyguyu iletebiliyor)
4. Her modelin her duygu için kullandığı ayar ve etiketler

---

## Adım 9 — Rapor, kontrol ve PR

1. **Tabloları aktar.** Dört tabloyu `docs/tts-karsilastirma.md` dosyasının 4. bölümüne yapıştır.
2. **Boşlukları doldur:**
   - Gözlemler tablosu; telaffuz hataları sütunu için dinleyici notlarını kullan.
   - **Seçilen model**, **yedek model** ve nedenleri.
   - Ubuntu sürümü (`lsb_release -d`), ElevenLabs sesi ve planı.
3. **Ses dosyalarının ve anahtarın repoya girmediğini kontrol et.** Aşağıdaki komut boş dönmeli:

```bash
cd ~/Graduation-Project
git ls-files "*.wav" "*.mp3" "*.m4a" "**/.env"
```

4. **Gönder:**

```bash
git add docs/tts-karsilastirma.md speech/experiments
git commit -m "docs: TTS comparison results and decision (#4)"
git push
gh pr ready
```

5. **İncelemeye gönder.** Reviewer olarak Nisa ya da Nisanur'u ekle, kartı **In review**'a taşı. PR onaylanınca issue'daki kutuları işaretle.

---

## Takvim (S1 8 Kasım'da bitiyor)

| Gün | Adımlar |
|---|---|
| 28 Ekim | 0, 1, 2, 3; akşam Adım 5'i başlat |
| 29 Ekim | 4 (referans sesler) ve referanslı tur |
| 30 Ekim – 2 Kasım | 6 (Colab) |
| 3 – 5 Kasım | 7 (dinleme testi) |
| 6 – 7 Kasım | 8 ve 9 (rapor ve PR) |
