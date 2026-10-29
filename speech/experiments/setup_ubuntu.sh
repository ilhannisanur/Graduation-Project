#!/usr/bin/env bash
# One-time setup of the TTS experiments on Ubuntu (native or WSL2).
# Safe to run again: existing environments are kept unless --recreate.
#
#     ./setup_ubuntu.sh                      # everything (asks for the sudo password once)
#     ./setup_ubuntu.sh --only kokoro        # one environment
#     ./setup_ubuntu.sh --skip-apt           # system packages are already installed
#     ./setup_ubuntu.sh --recreate --only chatterbox
#     ./setup_ubuntu.sh --dry-run            # print the commands only
#
# Creates .venv-kokoro (Kokoro + ElevenLabs), .venv-chatterbox (Chatterbox and
# Turbo) and .venv-styletts2, each with the CPU build of PyTorch.
# Install logs: logs/setup-<env>.log

set -uo pipefail
cd "$(dirname "$0")" || exit 1

ONLY="kokoro,chatterbox,styletts2"
SKIP_APT=0
RECREATE=0
DRY=0
PYTHON_VERSION="3.11"
TORCH_INDEX="${TORCH_INDEX:-https://download.pytorch.org/whl/cpu}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --only)      ONLY="$2"; shift 2 ;;
        --skip-apt)  SKIP_APT=1; shift ;;
        --recreate)  RECREATE=1; shift ;;
        --dry-run)   DRY=1; shift ;;
        -h|--help)   sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

green()  { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
red()    { printf '\033[31m%s\033[0m\n' "$*"; }
step()   { printf '\n\033[36m== %s\033[0m\n' "$*"; }
run()    { echo "+ $*"; if [[ $DRY -eq 0 ]]; then "$@"; fi; }

# --- 0. where are we? ----------------------------------------------------------
step "Checking the machine"
kernel="$(uname -r)"
if [[ "$kernel" == *Microsoft* && "$kernel" != *WSL2* ]]; then
    red "This is WSL1 ($kernel). Convert it first, in Windows PowerShell:"
    red "    wsl --set-version Ubuntu 2"
    exit 1
fi
if [[ "$(pwd)" == /mnt/* ]]; then
    yellow "The project is on the Windows disk ($(pwd)); this is 5-10x slower. Clone it into ~ instead."
fi
echo "kernel: $kernel"
echo "folder: $(pwd)"

# --- 1. system packages -----------------------------------------------------------
if [[ $SKIP_APT -eq 0 ]]; then
    step "Installing system packages (sudo)"
    run sudo apt-get update
    run sudo apt-get install -y git ffmpeg espeak-ng build-essential libsndfile1 curl zip unzip tmux
fi

# --- 2. uv and Python 3.11 ---------------------------------------------------------------
step "Installing uv and Python $PYTHON_VERSION"
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv > /dev/null; then
    if [[ $DRY -eq 1 ]]; then
        echo "+ curl -LsSf https://astral.sh/uv/install.sh | sh"
    else
        curl -LsSf https://astral.sh/uv/install.sh | sh || { red "uv installation failed"; exit 1; }
    fi
fi
run uv python install "$PYTHON_VERSION"

# --- 3. one virtual environment per model ------------------------------------------------
mkdir -p logs
declare -A RESULT

setup_env() {
    local name="$1"
    local venv=".venv-$name"
    local log="logs/setup-$name.log"
    local py="$venv/bin/python"

    step "Environment $venv (log: $log)"
    if [[ -d "$venv" && $RECREATE -eq 1 ]]; then
        run rm -rf "$venv"
    fi
    if [[ ! -x "$py" ]]; then
        run uv venv --seed --python "$PYTHON_VERSION" "$venv" || return 1
    fi

    # torch first, from the CPU index: otherwise pip pulls several GB of CUDA libraries
    local torch_pkgs=(torch)
    local extras="$name,dev"
    case "$name" in
        chatterbox) torch_pkgs=(torch==2.6.0 torchaudio==2.6.0) ;;
        styletts2)  torch_pkgs=(torch torchaudio) ;;
    esac

    if [[ $DRY -eq 1 ]]; then
        echo "+ $py -m pip install --upgrade pip"
        echo "+ $py -m pip install ${torch_pkgs[*]} --index-url $TORCH_INDEX"
        echo "+ $py -m pip install -e .[$extras]"
        return 0
    fi
    {
        "$py" -m pip install --upgrade pip &&
        "$py" -m pip install "${torch_pkgs[@]}" --index-url "$TORCH_INDEX" &&
        "$py" -m pip install -e ".[$extras]"
    } > "$log" 2>&1 || { red "install failed, see the end of $log:"; tail -n 15 "$log"; return 1; }

    case "$name" in
        kokoro)
            # Kokoro's English front end needs this spaCy model; get it now instead of at the first sentence
            "$py" -m spacy download en_core_web_sm >> "$log" 2>&1 || yellow "spaCy model download failed (Kokoro will retry on first use)"
            ;;
        styletts2)
            "$py" -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('punkt_tab', quiet=True)" >> "$log" 2>&1
            ;;
    esac

    # ElevenLabs may not have a key yet, so only the model engines decide success here
    local engines=("$name")
    [[ "$name" == "chatterbox" ]] && engines+=(chatterbox-turbo)
    "$py" -m tts_bench.doctor --skip-system --engines "${engines[@]}" || return 1
}

IFS=',' read -ra envs <<< "$ONLY"
for name in "${envs[@]}"; do
    name="$(echo "$name" | xargs)"
    case "$name" in
        kokoro|chatterbox|styletts2) ;;
        *) red "unknown environment '$name' (kokoro, chatterbox, styletts2)"; RESULT[$name]="unknown"; continue ;;
    esac
    if setup_env "$name"; then RESULT[$name]="OK"; else RESULT[$name]="FAILED"; fi
done

# --- 4. tests and summary ---------------------------------------------------------------------
kokoro_ready=0
[[ $DRY -eq 0 && "${RESULT[kokoro]:-}" == "OK" ]] && kokoro_ready=1
if [[ $DRY -eq 0 && $kokoro_ready -eq 0 && -x .venv-kokoro/bin/python ]]; then
    .venv-kokoro/bin/python -c "import tts_bench, pytest" 2> /dev/null && kokoro_ready=1
fi
if [[ $kokoro_ready -eq 1 ]]; then
    step "Running the tests"
    if .venv-kokoro/bin/python -m pytest -q; then RESULT[tests]="OK"; else RESULT[tests]="FAILED"; fi
fi

step "Summary"
status=0
for key in "${!RESULT[@]}"; do
    if [[ "${RESULT[$key]}" == "OK" ]]; then green "$key: OK"; else red "$key: ${RESULT[$key]}"; status=1; fi
done
if [[ $kokoro_ready -eq 1 ]]; then
    echo
    .venv-kokoro/bin/python -m tts_bench.doctor --engines elevenlabs || true
fi
if [[ $status -ne 0 && $DRY -eq 0 ]]; then
    echo
    yellow "Something failed. Fix it (see the log shown above) and run this script again;"
    yellow "finished environments are kept. Use --recreate --only <name> to rebuild one."
fi
exit $status
