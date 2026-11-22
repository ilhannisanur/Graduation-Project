# Ruh Hâli Etiketlerinden Değerlik ve Enerji (#75)

Bu belge, katalogdaki MTG-Jamendo ruh hâli etiketlerinden her parçaya ilk **değerlik** ve **enerji** değerinin nasıl verildiğini açıklar. Ses analizi modeli (#20) hazır olunca bu değerlerin yerini onun çıktısı alacak.

## Tanımlar

- **Değerlik (`tracks.valence`):** müziğin ne kadar olumlu hissettirdiği. 0 = olumsuz (hüzünlü, karanlık), 1 = olumlu (neşeli).
- **Enerji (`tracks.arousal`):** müziğin ne kadar yoğun olduğu. 0 = çok sakin, 1 = çok yoğun. Veritabanında sütun adı `arousal` olarak kalmıştır.
- İkisi de 0 ile 1 arasındadır (veritabanında kısıtla da zorunlu).

## Yöntem

1. Parçanın her etiketi aşağıdaki tabloda aranır. Tabloda olmayan etiket yok sayılır.
2. Bulunan etiketlerin değerlik ve enerjisinin **düz ortalaması** alınır (3 ondalığa yuvarlanır).
3. Tabloda bilinen hiç etiketi olmayan parçanın değerleri **boş kalır** (NULL).
4. Değerin kaynağı `tracks.affect_source` sütununa `tags` olarak yazılır. #20 sonrasında `audio` yazılacak ve iki kaynak karşılaştırılabilecek.

Değerleri sayı olarak seçmenin gerekçesi: etiketler (calm, happy…) kişi başına değil, parça başına birkaç kelimelik bir özet. Bu kabaca bir tahmindir; amaç, ses modeli gelene kadar duyguya göre seçimin ve DJ anonslarının çalışabilmesidir. Tablo bilimsel bir ölçüm değil, Russell'ın değerlik–uyarılma düzlemindeki yaygın yerleşime dayanan bir **sezgisel** eşlemedir; #20 geldiğinde değerler karşılaştırılıp tablo düzeltilebilir.

## Eşleme tablosu

Kod: `backend/app/music/mood_valence.py` (`TAG_VALENCE_ENERGY`). Belge ile kod birlikte güncellenir.

| Grup | Etiket (değerlik / enerji) | Gerekçe |
|---|---|---|
| Olumlu ve canlı | happy (0,85 / 0,65), upbeat (0,80 / 0,75), positive (0,80 / 0,55), uplifting (0,80 / 0,60), fun (0,80 / 0,70), funny (0,75 / 0,60), party (0,80 / 0,90), groovy (0,70 / 0,70), summer (0,75 / 0,65), children (0,80 / 0,55), game (0,60 / 0,70) | Neşeli etiketler: yüksek değerlik, orta-yüksek enerji. |
| Umutlu ve hedefli | hopeful (0,70 / 0,45), inspiring (0,75 / 0,55), motivational (0,75 / 0,70), adventure (0,60 / 0,75), travel (0,65 / 0,50), cool (0,60 / 0,55), sexy (0,65 / 0,50) | Olumlu ama daha ölçülü ya da hareketli. |
| Yoğun | energetic (0,65 / 0,90), powerful (0,50 / 0,90), action (0,45 / 0,90), fast (0,55 / 0,90), epic (0,50 / 0,85), trailer (0,40 / 0,80) | Enerji yüksek; değerlik orta çünkü bu etiketler duygu yönü taşımaz. |
| Gergin ve karanlık | dark (0,15 / 0,50), dramatic (0,30 / 0,70), drama (0,30 / 0,65), horror (0,08 / 0,75) | Düşük değerlik, orta-yüksek enerji. |
| Hüzünlü ve yavaş | sad (0,12 / 0,25), melancholic (0,20 / 0,25), emotional (0,35 / 0,40), ballad (0,35 / 0,30), slow (0,40 / 0,15), deep (0,35 / 0,30) | Düşük değerlik, düşük enerji. |
| Sakin ve yumuşak | calm (0,60 / 0,10), relaxing (0,65 / 0,12), soft (0,60 / 0,15), meditative (0,55 / 0,08), mellow (0,60 / 0,20), dream (0,65 / 0,20), nature (0,65 / 0,20), soundscape (0,50 / 0,15), romantic (0,75 / 0,30), love (0,80 / 0,35), melodic (0,60 / 0,40) | Çok düşük enerji; değerlik orta-yüksek (huzurlu, hüzünlü değil). |
| Tema etiketleri (zayıf sinyal) | christmas (0,75 / 0,45), holiday (0,75 / 0,45), documentary (0,45 / 0,35), film (0,45 / 0,50), movie (0,45 / 0,50), space (0,50 / 0,35), background (0,50 / 0,25), corporate (0,65 / 0,45), advertising (0,65 / 0,50), commercial (0,65 / 0,50) | Duygudan çok kullanım alanını anlatır; değerler ortaya yakın tutuldu. |

Katalogdaki 55 etiketin hepsi tabloda vardır.

## Komut

Backend klasöründen, Postgres açıkken ve `alembic upgrade head` çalıştırıldıktan sonra:

```powershell
python -m app.music.fill_valence_energy
```

- Tekrar çalıştırmak güvenlidir. `affect_source` boş ya da `tags` olan parçalar yeniden hesaplanır (tablo değişince değerler güncellenir).
- Kaynağı `audio` olan (ses modelinden gelen) değerlere dokunulmaz.
- Çıktı: kaç parça dolduruldu, güncellendi, değişmedi, tahmin edilemedi.

## Sonuç (400 parça)

İlk çalıştırmada 400 parçanın 400'ü dolduruldu; ikinci çalıştırmada 400'ü değişmedi olarak göründü.
