# Müzik Kaynağı Araştırması (#31)

Bu belge, Creative Commons müzik kataloğunun (üst iş #5) nereden ve nasıl oluşturulacağını açıklar. İlk bölümler (#31) yalnızca resmî kaynaklara dayanır. Canlı doğrulama sonuçları (#33) ilgili yerlerde "Doğrulandı" notuyla işaretlidir. İndirme komutu: `python -m app.music.download` (backend klasöründen).

## Karar özeti

| Konu | Karar |
|---|---|
| Aday listesi ve ruh hâli etiketleri | MTG-Jamendo veri seti (`autotagging_moodtheme.tsv`) |
| Başlık, sanatçı, lisans, ses bağlantısı | Jamendo API `/v3.0/tracks` (şarkı id'siyle) |
| Lisansın kaynağı | Jamendo API yanıtındaki lisans URL'si (MTG dosyasında lisans yok) |
| Eleme | ND lisanslılar, lisansı boş/tanınmayan ve indirmeye izin vermeyenler elenir |
| Anahtar (`.env`) | `JAMENDO_CLIENT_ID` |
| Hedef | 400 şarkı (1500 aday taranır, varsayılan; ölçüm aşağıda) |
| Ses formatı | `mp31` (96 kbps) |
| Boyut | 400 şarkı için yaklaşık 0,8 GB (5 şarkıda ölçüldü) |

## 1. MTG-Jamendo veri seti ne veriyor?

Kaynak: [MTG-Jamendo GitHub sayfası](https://github.com/MTG/mtg-jamendo-dataset)

- `autotagging_moodtheme.tsv` sütunları: `TRACK_ID`, `ARTIST_ID`, `ALBUM_ID`, `PATH`, `DURATION`, `TAGS` ([dosya](https://raw.githubusercontent.com/MTG/mtg-jamendo-dataset/master/data/autotagging_moodtheme.tsv)). Örnek satır: `track_0000948  artist_000087  album_000149  48/948.mp3  212.7  mood/theme---background`.
- **Başlık, sanatçı adı ve şarkı başına lisans bu dosyada yoktur.** Sanatçı için yalnızca bir id vardır.
- README, ses dosyalarının Creative Commons altında olduğunu ve lisansların `audio_licenses.txt` içinde bulunduğunu söyler. Bu dosyanın aranan adresi (`data/audio_licenses.txt`) 404 verdi; içeriği doğrulanamadı. Bu yüzden **lisans kaynağı olarak kullanılmayacak.**
- 59 ruh hâli/tema etiketi vardır ([moodtheme.txt](https://raw.githubusercontent.com/MTG/mtg-jamendo-dataset/master/data/tags/moodtheme.txt)). Ruh hâli alt kümesi 18.486 şarkıdır.
- Veri seti lisansları: kod Apache-2.0, metadata CC BY-NC-SA 4.0, ses Creative Commons (şarkıya göre değişir). Veri seti "yalnızca ticari olmayan araştırma ve akademik kullanım" için sunulur; okul projesi bu kapsama girer. Ticari kullanım için Jamendo S.A.'dan yazılı izin gerekir.
- Şarkı id'si (`track_0000948`) ile yol (`48/948.mp3`) birbirine uyar; bu, Jamendo'daki sayısal şarkı id'sinin (948) aynısı olarak kullanılacak. **Doğrulandı (#33):** 948, 950, 951 id'leriyle yapılan sorguda Jamendo aynı şarkıları (ör. 950 = "May") döndürdü; eşleşme doğru. MTG dosyasında etiketler `TAGS` sütununda tek hücre değil, 6. sütundan itibaren her biri ayrı sekme sütunudur ve `mood/theme---happy` biçimindedir (CRLF satır sonu); bir satırda 1 ile 8 arası etiket olabilir.

> **Uyarı:** MTG-Jamendo 2019 tarihli bir anlık görüntüdür. Bazı şarkılar Jamendo'dan kaldırılmış, lisansı ya da indirme izni değişmiş olabilir. Bu yüzden her aday Jamendo API'den yeniden sorgulanır ve sonuç API'ye göre belirlenir. 400 şarkı hedefi için **1200–1500 aday** taranması gerekir (ölçüm 4. bölümde).

## 2. Jamendo API ne veriyor?

Kaynak: [Jamendo API /tracks](https://developer.jamendo.com/v3.0/tracks)

- Uç nokta: `GET https://api.jamendo.com/v3.0/tracks/?client_id=...&format=json&id=<id>[+<id>...]&include=licenses&audioformat=mp31`
- Resmî dokümanda doğrulanan parametreler: `client_id` (zorunlu), `format`, `limit` (varsayılan 10, en çok 200), `id`, `tags`, `include` (`licenses`, `musicinfo`, `stats`, `lyrics`), `ccnd` (No Derivs filtresi), `audioformat`, `audiodlformat`.
- Resmî dokümanda doğrulanan yanıt alanları: `audio` (dinleme/akış bağlantısı), `audiodownload` (indirme bağlantısı), `audiodownload_allowed` (boolean; false ise `audiodownload` boş gelir).
- **Canlı yanıtla doğrulanan alanlar (#33):** `name`, `artist_name`, `duration` (tam sayı, saniye), `license_ccurl` (lisans URL'si; `http://` ile başlar), `shareurl` (şarkı sayfası, `https://www.jamendo.com/track/<id>`), ayrıca `id`, `audiodownload`, `audiodownload_allowed`. `include=licenses` ek olarak `licenses` nesnesi ekler (`ccnd`, `ccnc`, `ccsa` değerleri "true"/"false" metni); kod ND için bunu da ikinci kontrol olarak kullanır. `licensecurl` adı kullanılmaz. Üçüncü taraf [JamendoR](https://search.r-project.org/CRAN/packages/JamendoR/readme/README.html) örneklerinde bu adlarla görünüyorlar (ör. `license_ccurl` = `http://creativecommons.org/licenses/by-nc-sa/3.0/`, `shareurl` = `http://www.jamendo.com/track/114069`). 
- `audioformat` (`audio` alanını belirler): `mp31` (96 kbps, varsayılan), `mp32` (VBR, "iyi kalite"), `ogg`, `flac`. `audiodlformat` aynı seçeneklerle `audiodownload` alanını belirler; verilmezse `audioformat` değeri, o da yoksa `mp32` kullanılır. **Doğrulandı (#33):** yalnızca `audioformat=mp31` vermek yeterli; `audiodownload` bağlantısı `.../download/track/<id>/mp31/` olur ve anahtar içermez. Kod `audiodlformat` göndermez. Kaynak: [Jamendo API /tracks](https://developer.jamendo.com/v3.0/tracks).

### Geliştirici anahtarı

[Jamendo API girişine](https://developer.jamendo.com/v3.0) göre okuma istekleri `client_id` ile yapılır. Anahtar, [devportal.jamendo.com](https://devportal.jamendo.com) üzerinde hesap açıp bir uygulama oluşturarak alınır; bu sırada API şartlarının kabul edilmesi gerekir. Adım adım ekran akışı dokümanlarda yazılı değildir. Anahtar `.env` dosyasında **`JAMENDO_CLIENT_ID`** adıyla tutulur, commit'lenmez; şartlara göre kişiseldir ve başkalarıyla paylaşılmaz.

### Kullanım şartları ve okul projesi

Kaynak: [Jamendo API Terms of Use](https://devportal.jamendo.com/api_terms_of_use)

- Madde 3.3: API "ticari olmayan amaçlarla serbestçe kullanılabilir." Ticari kullanım (reklam, ortaklık geliri dâhil) ayrı anlaşma gerektirir. Ticari olmayan okul projesi uygundur.
- **Canlı gözlem (#33):** Boş cevap bazen art arda birkaç denemede sürebiliyor; bu yüzden istek 6 kereye kadar, giderek uzayan aralıklarla tekrarlanır. Aynı toplu istek bazen `status: success` ile **0 sonuç** döndürüp bir sonraki denemede doğru sonucu veriyor (uyarı ya da hata yok). Kod, 6 ve daha çok id'lik bir isteğin boş dönmesini geçici hata sayıp yeniden dener; aksi hâlde tüm batch yanlışlıkla "bulunamadı" sayılırdı. 50 id'lik istekler gerçek cevapta 34–46 sonuç döndürdü; eksikler `limit` yüzünden değil, Jamendo'dan kaldırılmış şarkılar. Koddaki `limit` her zaman gönderilen id sayısına eşittir.
- Aylık istek sınırı: giriş sayfası ücretsiz katmanda 35.000 istek/ay der. Şartlar ise Jamendo'nun istek sayısı ve sıklığına sınır koyabileceğini söyler. 1500 aday için yaklaşık 30–40 istek yeterlidir (tek istekte birden fazla `id` verilebilir).
- Madde 4.1: Uygulama, sanatçıları içerik sahibi olarak ve Jamendo'yu sağlayıcı olarak belirtmeli; her şarkıdan Jamendo'daki sayfasına doğrudan bağlantı vermelidir. Projedeki `artist` ve `source_url` alanları bunun içindir.
- Madde 3.3: Önbellek yalnızca uygulamanın çalışması için "makul ölçüde gerekli" olduğu kadar kullanılabilir; uygulama "özellikle içeriği önbelleğe almak için tasarlanmamalıdır." Şartlar ses dosyası indirmeyi açıkça ne yasaklıyor ne de izin veriyor. **Risk:** yerel katalog bu maddeyle çelişebilir. Önlem: yalnızca `audiodownload_allowed=true` olan şarkılar indirilir, katalog küçük tutulur (400 şarkı), ses dosyaları commit'lenmez, Jamendo erişimi keserse dosyalar silinir. Gerekirse Jamendo'ya (licensing@jamendo.com) sorulur.

## 3. Eleme kuralı

Her aday için API yanıtı şu sırayla kontrol edilir; biri başarısızsa şarkı **elenir**:

1. Şarkı API'de bulunamadı (kaldırılmış).
2. Lisans URL'si boş ya da tanınan bir `creativecommons.org/licenses/...` adresi değil (lisansı belirsiz).
3. Lisans URL'si ND içeriyor: yol bölümünde `nd` geçen lisanslar (`by-nd`, `by-nc-nd`). API'nin `ccnd` filtresi de kullanılabilir, ama tek başına ona güvenilmez; kendi kontrolümüz esastır.
4. `audiodownload_allowed` false (sanatçı indirmeyi kapatmış).
5. Süre, başlık ya da sanatçı adı boş.
6. Şarkı 60 saniyeden kısa (jingle gibi parçalar radyoda garip durur). Bu kural sonradan eklendiği için, manifest'te kalmış daha kısa şarkılar bir sonraki çalıştırmada dosyalarıyla birlikte çıkarılır.

NC (ticari olmayan) lisanslılar kabul edilir, çünkü proje ticari değildir. `Track.license` alanına lisans adı (ör. `CC BY-NC-SA 3.0`), `license_url` alanına URL yazılır.

## 4. Sayı, etiketler ve boyut

- **Hedef:** 400 şarkı (300–500 aralığının ortası). **Ölçüm (#33, `--dry-run`, 2026-10-24):** 800 adaydan 286, 1200 adaydan 433 şarkı geçti. Elenenlerin çoğu ND lisanslı (%40 civarı) ve Jamendo'dan kaldırılmış (%20 civarı) şarkılardır; indirmeye izin vermeyen yalnızca %2–3'tür. 60 saniye kuralı eklendikten sonra 1500 adayla iki kez ölçüldü: ikisinde de **515 şarkı** geçti (ND 604, bulunamadı 304, indirme izni yok 43, 60 sn'den kısa 31, lisans belirsiz 3). Bu yüzden varsayılan aday sayısı 1500'dür; 400 hedefi için yeterlidir.
- **Etiketler** (Emotion listesiyle eşleşecek şekilde seçildi): `happy`, `sad`, `relaxing`, `calm`, `energetic`, `dark`, `dramatic`, `uplifting`, `melancholic`, `romantic`, `epic`, `positive`, `soft`, `upbeat`. Radyoya uymayanlar (`children`, `christmas`, `advertising`, `commercial`, `corporate`, `trailer` vb.) alınmaz. Aday seçimi etiketler arasında sırayla dönerek yapılır (sabit seed 42); bir şarkı tek etikete sayılır ama `mood_tags` alanında şarkının MTG'deki **tüm** ruh hâli etiketleri tutulur.
- **Boyut (ölçüldü, #33):** `mp31` ile 5 şarkı indirildi: toplam 9,9 MB, ortalama 2,0 MB ve 172 sn (süreler 32–320 sn arası, bit hızı 96–99 kbps). 400 şarkı için **yaklaşık 0,8 GB**. Örnek küçük olduğundan 400'lük indirmeden sonra gerçek toplam bu belgeye işlenebilir. 60 saniyeden kısa parçalar artık elenir (bkz. 3. bölüm). Not: MTG'nin kendi rakamları (320 kbps için 152 GB) bizim indirmemize uygulanmaz, çünkü biz sesi API'den indireceğiz.
- Ses dosyaları commit'lenmez (`CLAUDE.md` kuralı).

## 5. Sonraki adımlar

- #33 (yapıldı): `backend/app/music/download.py`; `JAMENDO_CLIENT_ID` ve `music_dir` `Settings`'te, alan adları ve boyut canlı ölçüldü.
- #34: elenmiş listeyi `tracks` tablosuna aktarır.
- #35: katalog API ucu.
