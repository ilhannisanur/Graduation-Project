"""Tests run without any TTS model or network: a fake engine stands in for the
real ones (mock data is only used here, as the team rules require)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from tts_bench import listening, summarize
from tts_bench.audio_stats import edge_silence_sec, peak_dbfs
from tts_bench.engines import available_engines, create_engine, register
from tts_bench.engines.base import EMOTIONS, Audio, SynthesisRequest, TTSEngine, lerp
from tts_bench.engines.chatterbox_engine import (
    CFG_WEIGHT_FULL,
    EXAGGERATION_FULL,
    ChatterboxEngine,
    ChatterboxTurboEngine,
)
from tts_bench.engines.elevenlabs_engine import ElevenLabsEngine, load_api_key
from tts_bench.engines.kokoro_engine import SPEED_FULL, KokoroEngine
from tts_bench.engines.orpheus_engine import AUDIO_TOKEN_OFFSET, apply_tag, tokens_to_snac_layers
from tts_bench.engines.styletts2_engine import EMBEDDING_SCALE_FULL
from tts_bench.run import main as run_main
from tts_bench.test_set import load_test_set

SR = 16_000


class FakeEngine(TTSEngine):
    name = "fake"
    fail_on: set[str] = set()

    def load(self) -> None:
        self.loaded = True

    def settings_for(self, req: SynthesisRequest) -> dict:
        return {"pitch": 220 + 100 * req.intensity}

    def synthesize(self, req: SynthesisRequest) -> Audio:
        if req.text in self.fail_on:
            raise RuntimeError("simulated failure")
        n = int(SR * (0.2 + len(req.text) / 200))
        t = np.arange(n) / SR
        tone = 0.3 * np.sin(2 * np.pi * self.settings_for(req)["pitch"] * t)
        silence = np.zeros(SR // 10)
        return Audio(np.concatenate([silence, tone, silence]).astype(np.float32), SR)


register("fake", FakeEngine)


# --- test set -----------------------------------------------------------------


def test_test_set_is_7_emotions_x_5_sentences():
    items = load_test_set()
    assert len(EMOTIONS) == 7
    assert len(items) == 35
    assert len({it.id for it in items}) == len(items)
    for emotion in EMOTIONS:
        mine = [it for it in items if it.request.emotion == emotion]
        assert len(mine) == 5, emotion
        assert sum(it.group == "shared" for it in mine) == 1
        assert sum(it.listen for it in mine) == 2
    shared = [it for it in items if it.group == "shared"]
    assert len({it.request.text for it in shared}) == 1, "shared items must use the same text"


def test_every_engine_maps_every_emotion():
    for table in (SPEED_FULL, EXAGGERATION_FULL, CFG_WEIGHT_FULL, EMBEDDING_SCALE_FULL):
        assert set(table) == set(EMOTIONS)


def test_request_validation():
    with pytest.raises(ValueError):
        SynthesisRequest("hi", emotion="angry")
    with pytest.raises(ValueError):
        SynthesisRequest("hi", intensity=1.5)


# --- engine settings (no model packages needed) --------------------------------


def test_lerp_and_engine_settings():
    assert lerp(0.5, 1.1, 0.0) == 0.5
    assert lerp(0.5, 1.1, 1.0) == 1.1
    kokoro = KokoroEngine()
    assert kokoro.settings_for(SynthesisRequest("x", "sad", 1.0))["speed"] < 1.0
    assert kokoro.settings_for(SynthesisRequest("x", "excited", 1.0))["speed"] > 1.0
    cb = ChatterboxEngine()
    calm = cb.settings_for(SynthesisRequest("x", "calm", 1.0))
    excited = cb.settings_for(SynthesisRequest("x", "excited", 1.0))
    assert calm["exaggeration"] < 0.5 < excited["exaggeration"]
    assert cb.settings_for(SynthesisRequest("x", "neutral", 0.0))["reference"] == "built-in voice"


def test_reference_fallback_and_turbo_tags(tmp_path: Path):
    (tmp_path / "neutral.wav").write_bytes(b"")
    (tmp_path / "sad.wav").write_bytes(b"")
    turbo = ChatterboxTurboEngine(refs_dir=tmp_path, tags="true")
    assert turbo.reference_for("sad").name == "sad.wav"
    assert turbo.reference_for("happy").name == "neutral.wav"
    assert turbo.settings_for(SynthesisRequest("x", "excited", 0.8))["tag"] == "[laugh]"
    assert turbo.settings_for(SynthesisRequest("x", "excited", 0.2))["tag"] == ""


def test_orpheus_tags_and_snac_layers():
    assert apply_tag("Hello there. More soon.", "happy", 0.7) == "Hello there. <chuckle> More soon."
    assert apply_tag("Wait, really?", "surprised", 0.7).startswith("<gasp>")
    assert apply_tag("Bad news.", "sad", 0.2) == "Bad news."
    # two frames; position i carries code (10*f + i) shifted by i*4096
    tokens = [AUDIO_TOKEN_OFFSET + i * 4096 + 10 * f + i for f in range(2) for i in range(7)]
    tokens.append(128258)  # end-of-speech token is ignored
    l1, l2, l3 = tokens_to_snac_layers(tokens)
    assert l1 == [0, 10]
    assert l2 == [1, 4, 11, 14]
    assert l3 == [2, 3, 5, 6, 12, 13, 15, 16]


def test_elevenlabs_request_without_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    (tmp_path / ".env").write_text('OTHER=1\nELEVENLABS_API_KEY="sk_test"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert load_api_key() == "sk_test"

    engine = ElevenLabsEngine()
    engine.load()
    request = engine.build_request(SynthesisRequest("What a finish!", "excited", 0.8))
    body = json.loads(request.data)
    assert request.get_header("Xi-api-key") == "sk_test"
    assert "output_format=pcm_24000" in request.full_url
    assert body["model_id"] == "eleven_v3" and body["text"].startswith("[excited]")
    assert body["voice_settings"]["stability"] in (0.0, 0.5, 1.0)

    pcm = (np.sin(np.linspace(0, 100, 24_000)) * 10_000).astype("<i2").tobytes()
    monkeypatch.setattr(engine, "_post", lambda _req: pcm)
    audio = engine.synthesize(SynthesisRequest("Hello.", "neutral", 0.0))
    assert audio.sample_rate == 24_000 and audio.duration_sec == pytest.approx(1.0)

    v2 = ElevenLabsEngine(model="eleven_multilingual_v2")
    s = v2.settings_for(SynthesisRequest("Sad news.", "sad", 1.0))
    assert s["text"] == "Sad news." and s["voice_settings"]["style"] > 0


def test_registry_lists_real_engines():
    expected = {"kokoro", "chatterbox", "chatterbox-turbo", "styletts2", "orpheus", "orpheus-hf", "elevenlabs"}
    assert expected <= set(available_engines())
    assert isinstance(create_engine("fake"), FakeEngine)


def test_audio_stats():
    samples = np.concatenate([np.zeros(SR), 0.5 * np.ones(SR), np.zeros(SR // 2)]).astype(np.float32)
    lead, tail = edge_silence_sec(samples, SR)
    assert lead == pytest.approx(1.0, abs=0.03)
    assert tail == pytest.approx(0.5, abs=0.03)
    assert peak_dbfs(samples) == pytest.approx(-6.02, abs=0.05)


# --- runner, listening test, summary ----------------------------------------------


def _run_fake(tmp_path: Path, label: str, *extra: str) -> Path:
    run_main(["--engine", "fake", "--label", label, "--out", str(tmp_path / "results"), "--no-warmup", *extra])
    return tmp_path / "results" / label


def test_run_writes_wavs_and_metrics(tmp_path: Path):
    out = _run_fake(tmp_path, "fake-cpu")
    rows = list(csv.DictReader(open(out / "metrics.csv", encoding="utf-8")))
    assert len(rows) == 35
    assert all((out / f"{r['item_id']}.wav").exists() for r in rows)
    assert sum(r["listen"] == "1" for r in rows) == 14
    assert json.loads(rows[0]["settings"])["pitch"] > 0
    info = json.loads((out / "run_info.json").read_text(encoding="utf-8"))
    assert info["engine"] == "fake" and info["items"] == 35 and info["errors"] == []


def test_failed_item_is_skipped_then_resumed(tmp_path: Path):
    items = load_test_set()
    FakeEngine.fail_on = {items[3].request.text}
    try:
        with pytest.raises(SystemExit):
            _run_fake(tmp_path, "flaky")
    finally:
        FakeEngine.fail_on = set()
    out = tmp_path / "results" / "flaky"
    info = json.loads((out / "run_info.json").read_text(encoding="utf-8"))
    assert info["items"] == 34 and info["errors"][0]["item_id"] == items[3].id

    first_wav = out / f"{items[0].id}.wav"
    stamp = first_wav.stat().st_mtime_ns
    _run_fake(tmp_path, "flaky", "--resume")
    rows = list(csv.DictReader(open(out / "metrics.csv", encoding="utf-8")))
    assert len(rows) == 35 and len({r["item_id"] for r in rows}) == 35
    assert first_wav.stat().st_mtime_ns == stamp, "finished items must not be regenerated"


def _fill_sheet(path: Path, answers: dict[str, tuple[int, str]]) -> None:
    from openpyxl import load_workbook

    wb = load_workbook(path)
    ws = wb["ratings"]
    for row in ws.iter_rows(min_row=2):
        nat, emo = answers[row[0].value]
        row[1].value = nat
        row[2].value = emo
    wb.save(path)


def test_listening_test_and_summary(tmp_path: Path):
    _run_fake(tmp_path, "fake-a")
    _run_fake(tmp_path, "fake-b")
    results, lst = tmp_path / "results", tmp_path / "listening"
    key = listening.build_listening_test(results, lst, ["r1", "r2", "r3"])
    assert len(key) == 28  # 14 listening items x 2 models
    assert len(list((lst / "clips").glob("*.wav"))) == 28
    assert all("fake" not in p.name for p in (lst / "clips").iterdir())
    orders = [[r["clip_id"] for r in listening.read_rating_sheet(lst / f"rating_{n}.xlsx")] for n in ("r1", "r2")]
    assert sorted(orders[0]) == sorted(orders[1]) and orders[0] != orders[1]

    truth = {k["clip_id"]: k["emotion"] for k in key}
    _fill_sheet(lst / "rating_r1.xlsx", {c: (4, e) for c, e in truth.items()})  # always right
    _fill_sheet(lst / "rating_r2.xlsx", {c: (2, "neutral") for c in truth})  # right only on neutral
    # r3 used a semicolon CSV (Turkish Excel) instead of the xlsx
    (lst / "rating_r3.xlsx").unlink()
    with open(lst / "rating_r3.csv", "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(listening.RATING_FIELDS)
        writer.writerows([c, 3, "happy", ""] for c in truth)

    text = summarize.summarize(results, lst)
    assert "3 raters: r1, r2, r3" in text
    fake_a = next(line for line in text.splitlines() if line.startswith("| fake-a") and "%" in line)
    cells = [c.strip() for c in fake_a.strip("|").split("|")]
    # naturalness r1 r2 r3 mean | hit r1 r2 r3 mean | shared
    assert cells[1:5] == ["4.0", "2.0", "3.0", "3.0"]
    assert cells[5:8] == ["100%", "14%", "14%"]  # 2 of 14 clips are neutral / happy
    assert cells[8] == "43%" and cells[9] == "43%"
    section3 = text.split("### 3.")[1].split("### 4.")[0]
    per_emotion = next(line for line in section3.splitlines() if line.startswith("| fake-a"))
    assert per_emotion.count("%") == 7


def test_summary_without_ratings(tmp_path: Path):
    _run_fake(tmp_path, "fake-a", "--limit", "3")
    text = summarize.summarize(tmp_path / "results", None)
    assert "| fake-a | 3/3 |" in text and "No listening ratings yet" in text


def test_say_writes_one_file(tmp_path: Path):
    from tts_bench.say import main as say_main

    out = tmp_path / "hello.wav"
    say_main(["--engine", "fake", "--emotion", "surprised", "--out", str(out), "Hello Ankara!"])
    assert out.exists() and out.stat().st_size > 1000


def test_doctor_reports_missing_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    from tts_bench import doctor

    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    with pytest.raises(SystemExit) as exit_info:
        doctor.main(["--skip-system", "--engines", "elevenlabs"])
    assert exit_info.value.code == 1
    assert "[FAIL] ELEVENLABS_API_KEY" in capsys.readouterr().out

    (tmp_path / ".env").write_text("ELEVENLABS_API_KEY=sk_test123\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exit_info:
        doctor.main(["--skip-system", "--engines", "elevenlabs"])
    assert exit_info.value.code == 0


# --- ElevenLabs helpers (no network) ----------------------------------------------------


def _wav_bytes(seconds: float = 0.5, rate: int = 24_000) -> bytes:
    import io

    import soundfile as sf

    buf = io.BytesIO()
    sf.write(buf, np.zeros(int(seconds * rate), dtype=np.float32), rate, format="WAV")
    return buf.getvalue()


def test_elevenlabs_voice_from_env_and_format_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from tts_bench.engines.elevenlabs_engine import ElevenLabsError

    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    (tmp_path / ".env").write_text("ELEVENLABS_API_KEY=sk_test\nELEVENLABS_VOICE_ID=voice123\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    engine = ElevenLabsEngine()
    engine.load()
    assert engine.voice_id == "voice123"
    urls = []

    def fake_post(request):
        urls.append(request.full_url)
        if "pcm_" in request.full_url:
            raise ElevenLabsError(422, "output_format pcm_24000 is not available for your subscription tier")
        return _wav_bytes()

    monkeypatch.setattr(engine, "_post", fake_post)
    audio = engine.synthesize(SynthesisRequest("Hello.", "happy", 0.7))
    assert audio.duration_sec == pytest.approx(0.5)
    assert "/voice123?" in urls[0] and "pcm_24000" in urls[0] and "mp3_44100_128" in urls[1]
    engine.synthesize(SynthesisRequest("Again.", "sad", 0.7))
    assert "mp3_44100_128" in urls[2], "the fallback format is kept for the rest of the run"


def test_elevenlabs_error_hints():
    from tts_bench.engines.elevenlabs_engine import ElevenLabsError

    assert "permission" in str(ElevenLabsError(401, "invalid_api_key"))
    assert "quota" in str(ElevenLabsError(401 + 1, '{"status": "quota_exceeded"}'))
    assert "elevenlabs_tools voices" in str(ElevenLabsError(404, "voice_not_found"))
    assert "eleven_multilingual_v2" in str(ElevenLabsError(400, "model eleven_v3 is not available"))


def test_elevenlabs_tools(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    from tts_bench import elevenlabs_tools as tools

    chars = tools.count_test_set_characters()
    assert 3300 < chars < 4000  # 35 sentences + emotion tags + warm-up

    voices = [
        {"voice_id": "f1", "name": "Ava", "labels": {"gender": "female", "accent": "american"}},
        {"voice_id": "m1", "name": "Bob", "labels": {"gender": "male", "accent": "british"}},
    ]
    table = tools.format_voices(voices, gender="female")
    assert "Ava" in table and "Bob" not in table and "1 voices" in table

    def fake_get(path, api_key):
        if path.startswith("/v1/voices/"):
            return voices[0]
        return {"tier": "free", "character_count": 1000, "character_limit": 10000}

    monkeypatch.setattr(tools, "_get_json", fake_get)
    assert tools.check("sk_testkey") == 0
    out = capsys.readouterr().out
    assert "9,000 left" in out and "Ava (female, american)" in out

    monkeypatch.setattr(
        tools,
        "_get_json",
        lambda p, k: (
            {"tier": "free", "character_count": 9000, "character_limit": 10000} if "subscription" in p else voices[0]
        ),
    )
    assert tools.check("sk_testkey") == 1, "warns when a full run does not fit"


def test_summary_lists_emotion_controls(tmp_path: Path):
    from tts_bench.summarize import _controls

    _run_fake(tmp_path, "fake-a")
    text = summarize.summarize(tmp_path / "results", None)
    section = text.split("### 4.")[1]
    row = next(line for line in section.splitlines() if line.startswith("| fake-a"))
    assert "pitch=220.0" in row and "pitch=290.0" in row  # neutral (0.0) and an emotion at 0.7

    assert _controls('{"model": "eleven_v3", "text": "[sad] Hi.", "voice_settings": {"stability": 0.5}}') == (
        "stability=0.5, tag [sad]"
    )
    assert _controls('{"voice": "tara", "prompt": "Hi. <chuckle> More.", "temperature": 0.6}') == (
        "temperature=0.6, tag <chuckle>"
    )
    assert _controls('{"exaggeration": 0.8, "cfg_weight": 0.45, "reference": "built-in voice"}') == (
        "exaggeration=0.8, cfg_weight=0.45"
    )
