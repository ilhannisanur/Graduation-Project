"""Speech service tests. They use fake engines, so no model is downloaded
(mock data only in tests, as the team rules require)."""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient
from tts_bench.engines.base import Audio, SynthesisRequest, TTSEngine

from speech_service.app import create_app
from speech_service.config import Settings
from speech_service.synthesizer import SynthesisFailed, Synthesizer


class FakeEngine(TTSEngine):
    """A tone whose length follows the text; counts calls; can be told to fail."""

    calls: list[str] = []
    fail_names: set[str] = set()
    fail_load: set[str] = set()
    rate = 22_050  # deliberately different from the service rate, to test resampling
    delay = 0.0

    def load(self) -> None:
        if self.name in self.fail_load:
            raise RuntimeError("model download failed")

    def settings_for(self, req: SynthesisRequest) -> dict:
        return {}

    def synthesize(self, req: SynthesisRequest) -> Audio:
        FakeEngine.calls.append(f"{self.name}:{req.emotion}:{req.text}")
        if FakeEngine.delay:
            time.sleep(FakeEngine.delay)
        if self.name in self.fail_names:
            raise RuntimeError("CUDA out of memory")
        n = int(self.rate * (0.3 + len(req.text) / 100))
        t = np.arange(n) / self.rate
        return Audio((0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32), self.rate)


def factory(name: str, device: str = "cpu", **options) -> TTSEngine:
    engine = FakeEngine(device=device, **options)
    engine.name = name
    return engine


@pytest.fixture(autouse=True)
def reset_fake():
    FakeEngine.calls = []
    FakeEngine.fail_names = set()
    FakeEngine.fail_load = set()
    FakeEngine.delay = 0.0


def make_settings(tmp_path: Path, **kw) -> Settings:
    return Settings(audio_dir=tmp_path / "audio", **kw)


def make_client(tmp_path: Path, gpu: bool = False, **kw) -> TestClient:
    settings = make_settings(tmp_path, **kw)
    synth = Synthesizer(settings, factory=factory, gpu=gpu)
    return TestClient(create_app(settings, synth))


# --- engine choice (the README promises this behaviour) -------------------------------


def test_auto_engine_without_gpu_uses_kokoro_on_cpu(tmp_path: Path):
    synth = Synthesizer(make_settings(tmp_path), factory=factory, gpu=False)
    assert synth.primary.name == "kokoro" and synth.primary.device == "cpu"
    assert synth.fallback is None  # kokoro is already the main engine


def test_auto_engine_with_gpu_uses_orpheus_and_kokoro_as_fallback(tmp_path: Path):
    synth = Synthesizer(make_settings(tmp_path), factory=factory, gpu=True)
    assert (synth.primary.name, synth.primary.device) == ("orpheus-hf", "cuda")
    assert (synth.fallback.name, synth.fallback.device) == ("kokoro", "cpu")


def test_gpu_engine_requested_without_gpu_falls_back(tmp_path: Path):
    synth = Synthesizer(make_settings(tmp_path, engine="orpheus-hf"), factory=factory, gpu=False)
    assert synth.primary is None and synth.fallback.name == "kokoro"
    status = synth.status()
    assert status["status"] == "degraded" and "needs a CUDA GPU" in status["notes"][0]


def test_no_engine_at_all_is_an_error(tmp_path: Path):
    with pytest.raises(SynthesisFailed):
        Synthesizer(make_settings(tmp_path, engine="orpheus-hf", fallback_engine=""), factory=factory, gpu=False)


def test_settings_from_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for key in ("TTS_ENGINE", "TTS_ENGINE_OPTIONS", "SPEECH_AUDIO_DIR"):
        monkeypatch.delenv(key, raising=False)
    env = tmp_path / ".env"
    env.write_text("# comment\nTTS_ENGINE=kokoro\nTTS_ENGINE_OPTIONS=voice=af_bella, lang=a\nSPEECH_AUDIO_DIR=/x/a\n")
    monkeypatch.setenv("TTS_FALLBACK_ENGINE", "")
    s = Settings.from_env(env)
    assert s.engine == "kokoro" and s.engine_options == {"voice": "af_bella", "lang": "a"}
    assert s.audio_dir == Path("/x/a") and s.fallback_engine == ""


# --- API ----------------------------------------------------------------------------------


def test_synthesize_returns_a_playable_wav_and_caches_it(tmp_path: Path):
    with make_client(tmp_path) as client:
        body = {"text": "Good evening, Ankara!", "emotion": "calm", "intensity": 0.6}
        first = client.post("/synthesize", json=body)
        assert first.status_code == 200, first.text
        data = first.json()
        assert data["engine"] == "kokoro" and data["cached"] is False and data["sample_rate"] == 24_000
        assert data["audio_url"].startswith("/audio/") and data["audio_url"].endswith(".wav")

        wav = client.get(data["audio_url"])
        assert wav.status_code == 200 and wav.headers["content-type"] == "audio/wav"
        path = tmp_path / "audio" / data["audio_url"].rsplit("/", 1)[1]
        info = sf.info(str(path))
        assert info.samplerate == 24_000 and info.channels == 1  # resampled from 22.05 kHz
        assert data["duration_s"] == pytest.approx(info.frames / 24_000, abs=0.01)

        again = client.post("/synthesize", json={**body, "text": "  Good evening,   Ankara! "})
        assert again.json() == {**data, "cached": True, "loudness_lufs": None}
        assert len(FakeEngine.calls) == 1, "same text + emotion is served from the cache"

        other = client.post("/synthesize", json={**body, "emotion": "happy"}).json()
        assert other["audio_url"] != data["audio_url"] and len(FakeEngine.calls) == 2


def test_cache_survives_a_restart(tmp_path: Path):
    body = {"text": "Stay with us.", "emotion": "neutral"}
    with make_client(tmp_path) as client:
        url = client.post("/synthesize", json=body).json()["audio_url"]
    with make_client(tmp_path) as client:
        again = client.post("/synthesize", json=body).json()
    assert again["cached"] is True and again["audio_url"] == url and len(FakeEngine.calls) == 1


def test_fallback_when_the_main_engine_fails(tmp_path: Path):
    FakeEngine.fail_names = {"orpheus-hf"}
    with make_client(tmp_path, gpu=True) as client:
        data = client.post("/synthesize", json={"text": "What a finish!", "emotion": "excited"}).json()
        assert data["engine"] == "kokoro"
        assert client.get("/health").json()["primary"]["ready"] is True


def test_fallback_when_the_main_engine_cannot_load(tmp_path: Path):
    FakeEngine.fail_load = {"orpheus-hf"}
    with make_client(tmp_path, gpu=True) as client:
        health = client.get("/health").json()
        assert health["status"] == "degraded" and "model download failed" in health["primary"]["error"]
        assert client.post("/synthesize", json={"text": "Hello."}).json()["engine"] == "kokoro"


def test_503_when_every_engine_fails(tmp_path: Path):
    FakeEngine.fail_names = {"orpheus-hf", "kokoro"}
    with make_client(tmp_path, gpu=True) as client:
        r = client.post("/synthesize", json={"text": "Hello."})
        assert r.status_code == 503 and "orpheus-hf" in r.json()["detail"] and "kokoro" in r.json()["detail"]
        assert not list((tmp_path / "audio").glob("*.tmp")), "no half-written files left behind"


@pytest.mark.parametrize(
    "body",
    [
        {"text": ""},
        {"text": "   "},
        {"text": "hi", "emotion": "angry"},
        {"text": "hi", "intensity": 1.5},
        {"text": "hi", "voice_id": "celebrity"},
        {"text": "x" * 1001},
    ],
)
def test_bad_requests_are_rejected(tmp_path: Path, body: dict):
    with make_client(tmp_path) as client:
        assert client.post("/synthesize", json=body).status_code == 422
    assert FakeEngine.calls == []


def test_audio_endpoint_does_not_serve_other_files(tmp_path: Path):
    (tmp_path / "secret.txt").write_text("x")
    with make_client(tmp_path) as client:
        assert client.get("/audio/../secret.txt").status_code == 404
        assert client.get("/audio/" + "0" * 32 + ".wav").status_code == 404


def test_identical_requests_at_the_same_time_share_one_synthesis(tmp_path: Path):
    FakeEngine.delay = 0.2
    synth = Synthesizer(make_settings(tmp_path), factory=factory, gpu=False)
    req = SynthesisRequest("Up next, a calm one.", "calm", 0.5)

    async def both():
        return await asyncio.gather(synth.synthesize(req), synth.synthesize(req))

    a, b = asyncio.run(both())
    assert a.file == b.file and len(FakeEngine.calls) == 1


def test_engine_calls_are_serialised(tmp_path: Path):
    """Engines are not thread-safe: two different texts must not run at the same time."""
    active, peak, lock = [0], [0], threading.Lock()
    original = FakeEngine.synthesize

    def tracked(self, req):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        try:
            time.sleep(0.05)
            return original(self, req)
        finally:
            with lock:
                active[0] -= 1

    synth = Synthesizer(make_settings(tmp_path), factory=factory, gpu=False)
    FakeEngine.synthesize = tracked
    try:

        async def many():
            return await asyncio.gather(*(synth.synthesize(SynthesisRequest(f"Line {i}.")) for i in range(4)))

        asyncio.run(many())
    finally:
        FakeEngine.synthesize = original
    assert peak[0] == 1


def test_health_and_response_match_the_planner_client(tmp_path: Path):
    """The broadcast planner (#9) reads audio_url and duration_s from this response."""
    with make_client(tmp_path) as client:
        health = client.get("/health").json()
        assert health["status"] == "ok" and health["primary"]["engine"] == "kokoro"
        data = client.post("/synthesize", json={"text": "Hi.", "voice_id": "default", "target_duration_s": 3}).json()
        assert {"audio_url", "duration_s"} <= set(data)
