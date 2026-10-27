# Kullanıcılar, giriş ve profil

Bu belge #15'in ilk bölümünü (hesap ve profil) ve alınan kararları açıklar. İzin ekranı, verilerimi gör/sil ve tercih öğrenmeyi kapatma #15'in ikinci bölümündedir.

## Kararlar ve nedenleri

| Konu | Karar | Neden |
|---|---|---|
| Giriş kimliği | Kullanıcı adı ve parola; e-posta alınmaz | KVKK'nın en az veri ilkesi. E-posta gönderme altyapısı yok; e-posta alınsa da doğrulanamaz, parola sıfırlanamazdı. |
| Kullanıcı adı | 3–32 karakter: küçük harf, rakam, `.`, `_`, `-`. Küçük harfe çevrilerek saklanır | `Nisa` ile `nisa` aynı hesap olur; benzersizlik büyük/küçük harften bağımsızdır. |
| Parola | En az 8, en çok 128 karakter; karmaşıklık kuralı yok | NIST SP 800-63B uzunluğu önerir, zorunlu karakter türlerini önermez. Üst sınır hash'lemeyi ucuz tutar. |
| Parola saklama | argon2id (`argon2-cffi`, kütüphane varsayılanları) | OWASP'ın ilk önerisi. Ayarlar ileride güçlenirse eski hash'ler girişte otomatik yenilenir. |
| Oturum | Rastgele 256 bitlik belirteç, `radio_auth` çerezinde; veritabanında yalnızca SHA-256 hash'i | Veritabanı sızsa bile çalışan çerez elde edilemez. Çıkış ve hesap silme oturumu sunucuda anında bitirir. |
| Çerez | `HttpOnly`, `SameSite=Lax`, `Path=/api`, 30 gün; `COOKIE_SECURE=true` ile yalnızca HTTPS | Sayfa betikleri çerezi okuyamaz. Lax, başka sitelerin POST/PUT/DELETE isteklerinde çerezin gönderilmesini engeller (CSRF). `<audio>` ve HLS istekleri çerezi kendiliğinden gönderir. |
| Hatalı giriş | Her durumda aynı mesaj ve aynı süre | "Bu kullanıcı adı var mı?" sorusu yanıttan ya da süreden anlaşılmaz. Olmayan kullanıcıda da sahte bir hash doğrulanır. |
| LLM'e giden veri | Yalnızca `listener_context(profil, ...)` ile, bkz. [contracts.md](contracts.md#listenercontext) | Fonksiyon hesabı değil profili alır; kullanıcı adı ve kimliği yapı gereği giremez. Sanatçılar da dışarıda kalır (bir arkadaşın grubu kişisel olabilir). |

## Tablolar

- `users`: `id` (`usr_...`), `username` (benzersiz, küçük harf), `password_hash`, `created_at`
- `auth_sessions`: `token_hash` (birincil anahtar), `user_id`, `created_at`, `expires_at`
- `user_profiles`: `user_id`, `genres`, `artists`, `languages`, `news_topics`, `weather_city`, `updated_at`

`auth_sessions` ve `user_profiles`, `users.id`'ye `ON DELETE CASCADE` ile bağlıdır. Süresi dolan oturumlar kullanıcı tekrar giriş yaptığında silinir.

## API

| Uç | Açıklama |
|---|---|
| `POST /api/auth/register` | `{username, password}` → 201, hesabı açar ve giriş yapar. Ad alınmışsa 409. |
| `POST /api/auth/login` | `{username, password}` → 200 ve çerez; yanlışsa 401. |
| `POST /api/auth/logout` | 204; oturumu sunucuda siler ve çerezi temizler. |
| `GET /api/me` | Giriş yapmış kullanıcı; yoksa 401. |
| `GET /api/me/profile`, `PUT /api/me/profile` | Profili okur ve tümüyle değiştirir. Bilinmeyen seçenek 422. |
| `GET /api/profile/options` | Profil formundaki sabit seçenekler (herkese açık). |

Profil seçenekleri `backend/app/users/options.py`'dedir. Tür değerleri Jamendo'nun tür etiketleriyle aynı yazılır; katalogda henüz tür bilgisi olmadığı için tür tercihi şimdilik şarkı seçimini etkilemez.

## Bilinen sınırlar

- Giriş denemesi sınırı (brute-force koruması) yok. Açık bir sunucuya çıkmadan önce eklenmeli.
- Parola sıfırlama yok (e-posta alınmadığı için).
- Yönetici rolü #27'de eklenecek.
