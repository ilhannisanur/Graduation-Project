"""Builds tts_benchmark_gpu.ipynb (kept as code so the notebook diff stays readable).

    python colab/make_notebook.py
"""

import json
from pathlib import Path

cells: list[tuple[str, str]] = [
    ("md", """# TTS comparison – GPU runs (#4)

Runs every open-source candidate on a free **Colab T4 GPU**: Orpheus only runs here (section A), and \
issue #4 asks for the GPU speed and GPU memory of every candidate (sections B, C, D: Chatterbox, StyleTTS2, Kokoro).

1. **Runtime → Change runtime type → T4 GPU**.
2. Sections install conflicting package versions. Before each section use \
**Runtime → Restart session**, then run section 0 again.
3. Each section ends by downloading a results zip. It contains a `results` folder: extract it into `speech\\experiments` on the laptop (not into `results`)."""),
    ("md", "## 0. Setup (run before every section)"),
    ("code", "!nvidia-smi --query-gpu=name,memory.total --format=csv"),
    ("md", """The repo is private, so upload the code as a zip (without the `.venv` folders). \
On Windows, in PowerShell, inside `speech\\experiments`:

```powershell
tar -a -c -f experiments.zip tts_bench pyproject.toml refs
```

On Ubuntu, inside `speech/experiments`:

```bash
zip -r experiments.zip tts_bench pyproject.toml refs -x "*__pycache__*"
```"""),
    ("code", """import os
from google.colab import files
if not os.path.exists('/content/experiments/pyproject.toml'):
    uploaded = files.upload()  # experiments.zip
    !unzip -q -o experiments.zip -d /content/experiments
%cd /content/experiments
!ls"""),
    ("code", """# Helper: zip the results folder and download it
def download_results(name):
    !zip -q -r /content/{name}.zip results
    files.download(f'/content/{name}.zip')"""),
    ("md", """## A. Orpheus 3B (required)
The model is gated. Once, before running:
1. Sign in at huggingface.co, open https://huggingface.co/canopylabs/orpheus-3b-0.1-ft and accept the terms.
2. Settings → Access Tokens → **Create new token** (type: Read). Paste it into the `login()` box below.

`orpheus-hf` uses plain transformers + the SNAC decoder (no vLLM). 35 sentences take roughly half an hour \
on a T4; if the session is short, add `--only listen` (14 sentences, the ones used in the listening test)."""),
    ("code", """!pip install -q -e ".[orpheus-hf]"
from huggingface_hub import login
login()"""),
    ("code", """# quick check: one sentence
!python -m tts_bench.say --engine orpheus-hf --device cuda --emotion excited --out orpheus_try.wav "What a finish! Our team just won the final!"
from IPython.display import Audio
Audio('orpheus_try.wav')"""),
    ("code", """!python -m tts_bench.run --engine orpheus-hf --device cuda --label orpheus-t4 --resume"""),
    ("code", "download_results('results_orpheus')"),
    ("md", """If `orpheus-hf` fails, the official vLLM backend is an alternative (restart the session first):

```
!pip install -q orpheus-speech vllm==0.7.3
!pip install -q -e . --no-deps
!python -m tts_bench.run --engine orpheus --device cuda --label orpheus-vllm-t4
```
If neither works, write the error into the report: "could not be run within our hardware" is a valid finding."""),
    ("md", """## B. Chatterbox on GPU (required: GPU memory)
Issue #4 asks for the GPU memory of every candidate; the laptop cannot measure it. `chatterbox-tts` installs \
torch 2.6.0; if Colab asks you to restart, restart, run section 0, skip the install cell and continue."""),
    ("code", '!pip install -q -e ".[chatterbox]"'),
    ("code", """!python -m tts_bench.run --engine chatterbox --device cuda --label chatterbox-t4 --resume
# with reference clips (if refs/*.wav were in the zip):
# !python -m tts_bench.run --engine chatterbox --device cuda --refs refs --label chatterbox-refs-t4 --resume
# !python -m tts_bench.run --engine chatterbox-turbo --device cuda --refs refs --label chatterbox-turbo-refs-t4 --resume"""),
    ("code", "download_results('results_chatterbox_gpu')"),
    ("md", """## C. StyleTTS2 on GPU (required: GPU memory)
Restart the session and run section 0 first."""),
    ("code", """!pip install -q -e ".[styletts2]"
import nltk
nltk.download('punkt')
nltk.download('punkt_tab')"""),
    ("code", "!python -m tts_bench.run --engine styletts2 --device cuda --label styletts2-t4 --resume"),
    ("code", "download_results('results_styletts2_gpu')"),
    ("md", """## D. Kokoro on GPU (required: GPU memory)
Restart the session and run section 0 first."""),
    ("code", '!pip install -q -e ".[kokoro]"'),
    ("code", "!python -m tts_bench.run --engine kokoro --device cuda --label kokoro-t4 --resume"),
    ("code", "download_results('results_kokoro_gpu')"),
]


def to_cell(kind: str, src: str) -> dict:
    lines = src.splitlines(keepends=True)
    if kind == "md":
        return {"cell_type": "markdown", "metadata": {}, "source": lines}
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": lines}


notebook = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "accelerator": "GPU",
        "colab": {"gpuType": "T4", "provenance": []},
        "kernelspec": {"display_name": "Python 3", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "cells": [to_cell(k, s) for k, s in cells],
}

out = Path(__file__).with_name("tts_benchmark_gpu.ipynb")
out.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {out}")
