# Kullanıcılar, giriş, profil ve kişisel veri

Bu belge #15'i (hesap, profil, izinler ve kişisel veri hakları) ve alınan kararları açıklar.

## Kararlar ve nedenleri

| Konu | Karar | Neden |
|---|---|---|
| Giriş kimliği | Kullanıcı adı ve parola; e-posta alınmaz | KVKK'nın en az veri ilkesi. E-posta gönderme altyapısı yok; e-posta alınsa da doğrulanamaz, parola sıfırlanamazdı. |
| Kullanıcı adı | 3–32 karakter: küçük harf, rakam, `.`, `_`, `-`. Küçük harfe çevrilerek saklanır; Türkçe `İ`/`ı` da `i` sayılır | `Nisa`, `NİSA` ve `nisa` aynı hesaptır. Python'un küçük harf dönüşümü Türkçe I harflerini bilmediği için bu ayrıca yapılır. |
| Parola | En az 8, en çok 128 karakter; karmaşıklık kuralı yok | NIST SP 800-63B uzunluğu önerir, zorunlu karakter türlerini önermez. Üst sınır hash'lemeyi ucuz tutar. |
| Parola saklama | argon2id (`argon2-cffi`, kütüphane varsayılanları) | OWASP'ın ilk önerisi. Ayarlar ileride güçlenirse eski hash'ler girişte otomatik yenilenir. |
| Oturum | Rastgele 256 bitlik belirteç, `radio_auth` çerezinde; veritabanında yalnızca SHA-256 hash'i | Veritabanı sızsa bile çalışan çerez elde edilemez. Çıkış ve hesap silme oturumu sunucuda anında bitirir. |
| Çerez | `HttpOnly`, `SameSite=Lax`, `Path=/api`, 30 gün; `COOKIE_SECURE=true` ile yalnızca HTTPS | Sayfa betikleri çerezi okuyamaz. Lax, başka sitelerin POST/PUT/DELETE isteklerinde çerezin gönderilmesini engeller (CSRF). `<audio>` ve HLS istekleri çerezi kendiliğinden gönderir. |
| Hatalı giriş | Her durumda aynı mesaj ve aynı süre | "Bu kullanıcı adı var mı?" sorusu yanıttan ya da süreden anlaşılmaz. Olmayan kullanıcıda da sahte bir hash doğrulanır. |
| LLM'e giden veri | Yalnızca `listener_context(profil, ...)` ile, bkz. [contracts.md](contracts.md#listenercontext) | Fonksiyon hesabı değil profili alır; kullanıcı adı ve kimliği yapı gereği giremez. Sanatçılar da dışarıda kalır (bir arkadaşın grubu kişisel olabilir). |
| Yayın oturumu | Dinleyici giriş çerezinden alınır; hesabın oturumuna yalnızca sahibi erişir | İstekte gelen `user_id`'ye güvenilseydi herkes başkası adına yayın açabilirdi. |
| İzinler | Tek isteğe bağlı izin: tercih öğrenme. Varsayılanı kapalı, kutu önceden işaretli değil | KVKK'da açık rıza özgür iradeyle ve açıkça verilir; önceden işaretli kutu rıza sayılmaz. |
| İzin kaydı | Her karar yeni bir satır (`user_consents`); satırlar değiştirilmez | Hangi kararın ne zaman ve hangi aydınlatma metni sürümüyle verildiği kanıtlanabilir. Kayıtta "hayır" da kaydedilir: seçeneğin sunulduğu görünür. |
| Aydınlatma metni | `backend/app/users/privacy.py`, sürüm numaralı; `GET /api/privacy` ile herkese açık | Kayıt olmadan okunabilir. Metin anlamca değişirse `NOTICE_VERSION` değiştirilir. |
| Verilerimi indir | JSON dosyası: hesap, profil, izin geçmişi, giriş zamanları | Parola hash'i ve oturum belirteçleri dosyaya girmez; yalnızca saldırgana yarar. |
| Hesap silme | Parola tekrar sorulur; satırlar `ON DELETE CASCADE` ile silinir; açık yayın oturumları kapatılır | Açık unutulmuş bir sekmeden hesap silinemez. Yayın oturumları bellekte durduğu için ayrıca kapatılır. |

## Tablolar

- `users`: `id` (`usr_...`), `username` (benzersiz, küçük harf), `password_hash`, `created_at`
- `auth_sessions`: `token_hash` (birincil anahtar), `user_id`, `created_at`, `expires_at`
- `user_profiles`: `user_id`, `genres`, `artists`, `languages`, `news_topics`, `weather_city`, `updated_at`
- `user_consents`: `id`, `user_id`, `kind`, `granted`, `notice_version`, `created_at`

Kullanıcıya ait veri tutan her tablo `users.id`'ye `ON DELETE CASCADE` ile bağlıdır. `tests/test_privacy.py` bunu bütün tablolar için denetler: yeni bir tablo kullanıcı verisi tutup bu kuralı unutursa test kırılır. Süresi dolan oturumlar kullanıcı tekrar giriş yaptığında silinir.

## API

| Uç | Açıklama |
|---|---|
| `POST /api/auth/register` | `{username, password, preference_learning?}` → 201, hesabı açar ve giriş yapar. Ad alınmışsa 409. |
| `POST /api/auth/login` | `{username, password}` → 200 ve çerez; yanlışsa 401. |
| `POST /api/auth/logout` | 204; oturumu sunucuda siler ve çerezi temizler. |
| `GET /api/me` | Giriş yapmış kullanıcı; yoksa 401. |
| `GET /api/me/profile`, `PUT /api/me/profile` | Profili okur ve tümüyle değiştirir. Bilinmeyen seçenek 422. |
| `GET /api/profile/options` | Profil formundaki sabit seçenekler (herkese açık). |
| `GET /api/privacy` | Aydınlatma metni ve izin açıklamaları (herkese açık). |
| `GET /api/me/consents`, `PUT /api/me/consents` | İzinleri okur; `{preference_learning: bool}` ile değiştirir. Karar değişmediyse yeni satır eklenmez. |
| `GET /api/me/data` | Bütün verileri JSON dosyası olarak indirir. |
| `DELETE /api/me` | `{password}` → 204; hesabı ve bütün verileri siler. Yanlış parolada 403. |

Profil seçenekleri `backend/app/users/options.py`'dedir. Tür değerleri Jamendo'nun tür etiketleriyle aynı yazılır; katalogda henüz tür bilgisi olmadığı için tür tercihi şimdilik şarkı seçimini etkilemez (#48).

## Diğer modüller için

- Dinleme davranışından öğrenen her kod (#23 kişisel seçim, beğen/atla kaydı) önce `app.users.service.may_learn_preferences(db, user_id)`'yi çağırmalıdır. `False` ise dinleme geçmişi kişiselleştirme için kullanılmaz.
- Kullanıcıya ait yeni bir tablo `users.id`'ye `ON DELETE CASCADE` ile bağlanmalı ve "Verilerimi indir" dosyasına (`service.export_user_data`) eklenmelidir.

## Bilinen sınırlar

- Giriş denemesi sınırı (brute-force koruması) yok. Açık bir sunucuya çıkmadan önce eklenmeli.
- Parola sıfırlama yok (e-posta alınmadığı için).
- Yönetici rolü #27'de eklenecek.
- Aydınlatma metni hukuki inceleme görmedi; bir bitirme projesi için hazırlandı.
