# DJ anons örnekleri (song intro) — #59

Bu belge, DJ Brain'in şarkı anonslarından 20 gerçek örneği ve LLM'in ne kadar sürede cevap verdiğini gösterir. #3'ün kabul kriteri için hazırlandı; ekip birlikte okuyup yorum yapabilir.

## Nasıl üretildi?

- Tarih: 3 Kasım 2026 (Salı öğleden sonra, Europe/Istanbul).
- Model: `gemini-3.1-flash-lite` (`.env` içindeki `GEMINI_MODEL`).
- Kod: yayındaki planlayıcının kullandığı `generate_song_intro` ile aynı; `POST /api/dj/song-intro-preview` üzerinden çağrıldı.
- Script: `scripts/sample_song_intros.py`. Şarkılar sırayla gönderildi; her istekte bir önceki şarkı ve son 3 anons da vardı (gerçek yayın gibi).
- Katalog boş olduğu için (Postgres kapalıydı) script'teki uydurma şarkılar kullanıldı. 2 şarkıda valence/arousal yok (bilerek).
- Ham sonuçlar (gönderilen prompt dahil): `docs/samples/song-intros-raw.json`.
- Süre yalnızca LLM süresidir; TTS (ses üretimi) dahil değildir.

## Örnekler

Sütunlar: V/A = valence / arousal, Kelime = kullanılan / izin verilen en fazla, Gün = prompt'ta gün ve saat verildi mi, Önceki = prompt'ta önceki şarkı verildi mi.

| # | Şarkı | V/A | Duygu | Anons | Kelime | Gün | Önceki | LLM (ms) |
|---|---|---|---|---|---|---|---|---|
| 1 | Morning Tide — Lena Hart | 0.80 / 0.40 | happy | Up next is Morning Tide by Lena Hart. It's a lovely track to keep the good vibes going. | 18/39 |  |  | 4100 |
| 2 | Neon Run — The Static Kids | 0.70 / 0.90 | excited | Keep that energy climbing with Neon Run by The Static Kids. It's coming up right now. | 16/29 |  | ✓ | 2519 |
| 3 | Grey Window — Owen Marsh | 0.20 / 0.20 | sad | Moving on to something a bit more mellow, here's Grey Window by Owen Marsh. It's a quiet track for this Tuesday afternoon. | 22/27 | ✓ | ✓ | 3814 |
| 4 | Paper Boats — Mila Rae | 0.60 / 0.30 | calm | Hope you are having a nice Tuesday afternoon. Let us settle in with Paper Boats by Mila Rae. | 18/46 | ✓ | ✓ | 6872 |
| 5 | Thunder Road Home — Northbound | 0.50 / 0.80 | neutral | We are keeping the momentum going. This is Thunder Road Home by Northbound. | 13/34 |  |  | 3680 |
| 6 | Slow Coffee — June Avenue | 0.70 / 0.20 | calm | It is a peaceful Tuesday afternoon. Let us enjoy Slow Coffee by June Avenue. | 14/36 | ✓ |  | 5625 |
| 7 | Lost Signal — Echo Field | 0.30 / 0.60 | serious | Moving right along, here is Lost Signal by Echo Field. | 10/14 |  | ✓ | 2730 |
| 8 | Sunday Bikes — The Fernwoods | 0.90 / 0.60 | happy | It is a beautiful Tuesday afternoon, so let's keep that energy high. This is Sunday Bikes by The Fernwoods. | 19/50 | ✓ |  | 3674 |
| 9 | Cold Harbor — Ada Quinn | 0.10 / 0.40 | sad | For this Tuesday afternoon, let's turn to Cold Harbor by Ada Quinn. | 12/36 | ✓ |  | 3732 |
| 10 | Fireflies — Sol & Moon | 0.80 / 0.70 | happy | Time to brighten up your Tuesday afternoon with Fireflies by Sol and Moon. | 13/17 | ✓ |  | 2655 |
| 11 | Long Way Down — Brass Hollow | — | neutral | Moving right along, here is Long Way Down by Brass Hollow. | 11/16 |  | ✓ | 2933 |
| 12 | City Lights — Kai Rivers | — | neutral | Keep it locked right here for City Lights by Kai Rivers. | 11/31 | ✓ |  | 2651 |
| 13 | Small Hours — Nora Vale | 0.40 / 0.10 | sad | That was Kai Rivers. Now, let's drift into Small Hours by Nora Vale. | 13/24 | ✓ | ✓ | 2764 |
| 14 | Jump Start — Volt Club | 0.90 / 0.95 | excited | Time to get moving with Jump Start by Volt Club. | 10/12 |  |  | 3092 |
| 15 | Old Photographs — Henry Lake | 0.35 / 0.30 | sad | Moving on to something a bit more pensive. This is Old Photographs by Henry Lake. | 15/31 |  |  | 2757 |
| 16 | Riverbend — Clara Moss | 0.60 / 0.50 | neutral | It is time for some Clara Moss. Here is Riverbend. | 10/34 |  |  | 3081 |
| 17 | Midnight Train — The Lanterns | 0.40 / 0.70 | serious | That was Riverbend from Clara Moss. Now, let's keep things moving with Midnight Train by The Lanterns. | 17/45 |  | ✓ | 2993 |
| 18 | Golden Hour — Iris Bloom | 0.85 / 0.50 | happy | Hope you enjoyed that. Now, let's brighten up this Tuesday afternoon with Golden Hour by Iris Bloom. | 17/27 | ✓ | ✓ | 10988 |
| 19 | Static Rain — Low Orbit | 0.25 / 0.50 | sad | Moving into the afternoon with something a bit more moody. This is Static Rain by Low Orbit. | 17/30 | ✓ |  | 3265 |
| 20 | Weekend Plans — Sunny Days Band | 0.95 / 0.80 | excited | Time for Weekend Plans by Sunny Days Band to kick off your day. | 13/14 |  | ✓ | 5081 |

## LLM süresi

- 20 istekte 20 başarılı cevap; hiçbiri yedek şablona düşmedi, hiçbir istekte yeniden deneme gerekmedi.
- En az 2519 ms, ortanca 3178 ms, ortalama 3950 ms, en fazla 10988 ms (tek uç değer; ikinci en yüksek 6872 ms).
- 15 sn'lik istemci zaman aşımı (`TIMEOUT_MS=15000`) hiçbir istekte dolmadı.
- Sonuç: Flash Lite ile LLM tarafı yavaş değil. Yayındaki bekleme hissi büyük olasılıkla TTS'ten geliyor; bunu speech servisiyle ayrıca ölçmek gerekiyor.

## Kalite gözlemleri

İyi olanlar:
- Çıktı her seferinde geçerli JSON, duygu her seferinde 7 duygudan biri.
- Kelime sınırı hiç aşılmadı.
- Duygu seçimi valence/arousal'a uyuyor (ör. 0.10 / 0.40 → sad, 0.90 / 0.95 → excited); değer yokken neutral seçildi.
- Gün/saat verilmeyen anonslarda gün adı geçmedi; önceki şarkı verilmeyenlerde önceki şarkıdan bahsedilmedi.

Geliştirilmesi gerekenler:
- **Kalıp tekrarı:** "Moving right along, here is X by Y." (#7 ve #11 neredeyse aynı), "Moving on to something a bit more ..." (#3, #15), "Time to ..." (#10, #14, #20). Son 3 anons prompt'ta olduğu hâlde, 4 anons önceki kalıp geri geliyor. Açılış tipi listesi (Python rastgele seçer) gerekiyor gibi görünüyor.
- **"Tuesday afternoon" çok sık:** Gün/saat verildiği 10 anonsun 8'inde kullanıldı. "You may mention them lightly" kuralı LLM için "kullan" anlamına geliyor.
- **Önceki şarkı neredeyse hiç kullanılmadı:** Verildiği 10 anonsun yalnızca 2'sinde geçti (#13, #17).
- **Hep hem şarkı adı hem sanatçı:** 20 anonsun 20'sinde ikisi de söyleniyor (çoğu "X by Y" kalıbında). Prompt "title, artist or both" dese de yalnızca birini söyleyen anons ("Hadise bizlerle" tarzı) hiç yok.
- **Anonslar kısa:** 10–22 kelime; izin verilen sınır 12–50 arasında rastgele seçildiği hâlde uzun anons hiç yok. Sebep, prompt'taki "upper bound, not a target. Do not pad." cümlesi. Uzunluk çeşitliliği isteniyorsa bu cümle gözden geçirilmeli.
- **Küçük kural ihlalleri:** Kısaltma kuralına rağmen "Let us", "It is" (#4, #6, #8, #16); gün/saat verilmediği hâlde "kick off your day" (#20, öğleden sonra).
- **"sad" duygusu 5 kez seçildi:** Hüzünlü şarkıda DJ'in de hüzünlü konuşması doğru mu, yoksa "calm" mı daha uygun? C4'te (#17) değerlendirilebilir.
