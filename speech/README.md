# Speech (duygulu ses servisi)

Henüz kod yok. Ses modelleri (TTS) ileride bu klasörde, backend'ten **ayrı bir Python ortamında** ve **ayrı bir servis** olarak çalışacak. Sebep: Chatterbox gibi modeller Python 3.11 ister, backend ise Python 3.12 kullanır.

Backend bu servisle `backend/app/speech_client/` altındaki arayüz üzerinden konuşacak.

Üretilen ses dosyaları (`*.wav`, `*.mp3`, ...) repoya commit'lenmez.
