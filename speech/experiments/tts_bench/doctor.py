"""Check that this machine and this virtual environment are ready.

    python -m tts_bench.doctor                     # system + this environment
    python -m tts_bench.doctor --engines kokoro elevenlabs

Prints one line per check (OK / WARN / FAIL) and exits with 1 if anything
required is missing. Send the output when asking for help.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
import platform
import shutil
import sys
from pathlib import Path

from .engines.base import EMOTIONS

ROOT = Path(__file__).resolve().parent.parent

# engine -> modules that must import in its environment
ENGINE_MODULES = {
    "kokoro": ["torch", "kokoro"],
    "chatterbox": ["torch", "torchaudio", "chatterbox.tts"],
    "chatterbox-turbo": ["torch", "torchaudio", "chatterbox.tts_turbo"],
    "styletts2": ["torch", "torchaudio", "styletts2.tts", "nltk"],
    "orpheus-hf": ["torch", "transformers", "snac"],
    "orpheus": ["torch", "vllm", "orpheus_tts"],
    "elevenlabs": [],
}


class Report:
    def __init__(self) -> None:
        self.failed = 0
        self.warned = 0

    def line(self, status: str, label: str, detail: str = "") -> None:
        if status == "FAIL":
            self.failed += 1
        elif status == "WARN":
            self.warned += 1
        print(f"[{status:<4}] {label:<28} {detail}".rstrip())

    def ok(self, label: str, detail: str = "") -> None:
        self.line("OK", label, detail)

    def warn(self, label: str, detail: str) -> None:
        self.line("WARN", label, detail)

    def fail(self, label: str, detail: str) -> None:
        self.line("FAIL", label, detail)


def check_system(r: Report) -> None:
    print("== system")
    release = platform.release()
    if "microsoft" in release.lower():
        if "WSL2" in release or "microsoft-standard" in release:
            r.ok("platform", f"WSL2 ({release})")
        else:
            r.fail("platform", f"WSL1 ({release}): convert with 'wsl --set-version Ubuntu 2' in PowerShell")
        if str(ROOT).startswith("/mnt/"):
            r.warn("project location", f"{ROOT} is on the Windows disk (slow); clone into ~ instead")
    else:
        r.ok("platform", f"{platform.system()} {release}")

    v = sys.version_info
    if (3, 10) <= (v.major, v.minor) <= (3, 12):
        r.ok("python", f"{platform.python_version()} ({sys.executable})")
    else:
        r.fail("python", f"{platform.python_version()}: use Python 3.11 (3.10-3.12 supported)")
    if sys.prefix == sys.base_prefix:
        r.warn("virtual environment", "not inside a venv; activate one (source .venv-<name>/bin/activate)")

    for tool, why in (("ffmpeg", "audio conversion"), ("espeak-ng", "Kokoro fallback pronunciation")):
        path = shutil.which(tool)
        if path:
            r.ok(tool, path)
        else:
            r.warn(tool, f"not found ({why}); sudo apt install {tool}")

    free_gb = shutil.disk_usage(ROOT).free / 2**30
    (r.ok if free_gb >= 15 else r.warn)("disk free", f"{free_gb:.0f} GB (models need about 10 GB)")
    try:
        import psutil

        total = psutil.virtual_memory().total / 2**30
        avail = psutil.virtual_memory().available / 2**30
        (r.ok if total >= 7.5 else r.warn)("memory", f"{total:.1f} GB total, {avail:.1f} GB available")
    except ImportError:
        r.warn("memory", "psutil missing; pip install -e .")


def check_project(r: Report) -> None:
    print("== project")
    from .test_set import load_test_set

    items = load_test_set()
    emotions = {it.request.emotion for it in items}
    if len(items) == 35 and emotions == set(EMOTIONS):
        r.ok("test set", f"{len(items)} sentences, {len(EMOTIONS)} emotions")
    else:
        r.fail("test set", f"{len(items)} sentences, emotions {sorted(emotions)}")
    for module, why in (("soundfile", "writing wav files"), ("openpyxl", "listening sheets")):
        if importlib.util.find_spec(module):
            r.ok(module)
        else:
            r.fail(module, f"missing ({why}); pip install -e .")

    refs = ROOT / "refs"
    present = [e for e in EMOTIONS if (refs / f"{e}.wav").exists()]
    if len(present) == len(EMOTIONS):
        r.ok("reference clips", "all 7 emotions")
    elif present:
        r.warn("reference clips", f"{len(present)}/7 ({', '.join(present)}); missing ones use neutral.wav")
    else:
        r.line("INFO", "reference clips", "none yet (optional; needed for --refs runs)")


def check_engine(r: Report, engine: str) -> None:
    print(f"== engine: {engine}")
    for module in ENGINE_MODULES.get(engine, []):
        try:
            mod = importlib.import_module(module)
        except Exception as exc:  # noqa: BLE001 - report any import problem
            r.fail(f"import {module}", f"{type(exc).__name__}: {exc}"[:150])
            continue
        if module == "torch":
            cuda_build = getattr(mod.version, "cuda", None)
            detail = f"{mod.__version__}" + (f" (CUDA {cuda_build} build)" if cuda_build else " (CPU build)")
            if cuda_build and not mod.cuda.is_available():
                r.warn("torch", detail + ": no usable GPU here, the CPU build is enough and much smaller")
            else:
                r.ok("torch", detail)
        else:
            r.ok(f"import {module}", getattr(mod, "__version__", ""))

    if engine == "elevenlabs":
        from .engines.elevenlabs_engine import load_api_key

        key = load_api_key(ROOT)
        if key:
            r.ok("ELEVENLABS_API_KEY", f"{key[:4]}...{key[-2:]} (from env or .env)")
        else:
            r.fail("ELEVENLABS_API_KEY", f"missing; put it in {ROOT / '.env'}")
        env_file = ROOT / ".env"
        if env_file.exists() and os.name == "posix" and env_file.stat().st_mode & 0o077:
            r.warn(".env permissions", "readable by others; chmod 600 .env")
        from .engines.elevenlabs_engine import load_env_value

        voice = load_env_value("ELEVENLABS_VOICE_ID", ROOT)
        if voice:
            r.ok("ELEVENLABS_VOICE_ID", voice)
        else:
            r.warn(
                "ELEVENLABS_VOICE_ID",
                "not set: the default voice is male, the other engines are female; "
                "pick one with: python -m tts_bench.elevenlabs_tools voices --gender female",
            )
    if engine == "styletts2":
        try:
            import nltk

            nltk.data.find("tokenizers/punkt")
            r.ok("nltk punkt")
        except Exception:  # noqa: BLE001
            r.fail("nltk punkt", "python -c \"import nltk; nltk.download('punkt'); nltk.download('punkt_tab')\"")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--engines", nargs="*", default=[], choices=sorted(ENGINE_MODULES), metavar="ENGINE")
    parser.add_argument("--skip-system", action="store_true")
    args = parser.parse_args(argv)

    r = Report()
    if not args.skip_system:
        check_system(r)
        check_project(r)
    for engine in args.engines:
        check_engine(r, engine)

    print(f"== result: {r.failed} failed, {r.warned} warnings")
    raise SystemExit(1 if r.failed else 0)


if __name__ == "__main__":
    main()
