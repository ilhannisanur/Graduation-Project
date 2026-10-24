# CLAUDE.md

## Proje
Emotion-Aware AI Radio: yapay zekâ DJ'in sunduğu, kullanıcı başına kişisel yayın akışı olan İngilizce radyo. Ayrıntılar için README.md.

## Klasörler
- `backend/` FastAPI (Python 3.12): `app/api`, `app/core`, `app/db`, `app/radio`, `app/content` (LLM, haber, hava), `app/speech_client`
- `web/` React + TypeScript (Vite)
- `speech/` ileride ayrı Python ortamında çalışacak TTS servisi (şimdilik sadece README)
- `scripts/`, `docs/`

## Çalıştırma ve test (Windows, PowerShell)
```powershell
docker compose up -d                                  # Postgres (host portu 5433)
cd backend; .\.venv\Scripts\Activate.ps1
alembic upgrade head
uvicorn app.main:app --reload                         # http://localhost:8000
pytest; ruff check .; ruff format --check .
cd ..\web; npm run dev                                # http://localhost:5173
npm run lint; npm run format:check; npm run build
```

## Kurallar
- Telifli müzik yok; yalnızca Creative Commons (ND lisanslılar hariç). Ses/müzik dosyaları commit'lenmez.
- API anahtarları yalnızca `.env` içinde; `.env` commit'lenmez.
- LLM erişimi yalnızca `LLMClient` üzerinden (`backend/app/content/llm/`). Model adı koda gömülmez, `.env`'den gelir.
- Testler gerçek API'ye istek atmaz; sahte (fake) sınıflar kullanılır.
- Kod, kod yorumları ve radyo içeriği İngilizce; README ve belgeler Türkçe.
