#!/usr/bin/env bash
# Runs the TTS comparison (issue #4) with every engine whose virtual
# environment exists, then writes results/summary.md. One command:
#
#     ./run_experiments.sh
#
# Each engine runs in its own virtual environment (their packages conflict).
# Engines without a virtual environment, or ElevenLabs without an API key in
# .env, are skipped with a warning. Runs resume where they stopped, so running
# the command again only generates what is missing.
#
# Examples:
#     ./run_experiments.sh                                   # all engines, 35 sentences each
#     ./run_experiments.sh --limit 2                         # quick check, 2 sentences each
#     ./run_experiments.sh --engines kokoro,elevenlabs       # only these engines
#     ./run_experiments.sh --engines chatterbox,chatterbox-turbo,styletts2 --refs refs
#     ./run_experiments.sh --engines chatterbox --fresh      # delete old results and start over
#
# Windows: use run_experiments.ps1 instead.

set -uo pipefail
cd "$(dirname "$0")" || exit 1

ENGINES="kokoro,chatterbox,styletts2,elevenlabs"
REFS=""
LIMIT=0
DEVICE="cpu"
FRESH=0

usage() { sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        -e|--engines) ENGINES="$2"; shift 2 ;;
        -r|--refs)    REFS="$2"; shift 2 ;;
        -l|--limit)   LIMIT="$2"; shift 2 ;;
        -d|--device)  DEVICE="$2"; shift 2 ;;
        --fresh)      FRESH=1; shift ;;
        -h|--help)    usage 0 ;;
        *) echo "Unknown option: $1" >&2; usage 1 ;;
    esac
done

# engine -> virtual environment that has its packages (edit if yours are named differently)
venv_for() {
    case "$1" in
        kokoro|elevenlabs)           echo ".venv-kokoro" ;;
        chatterbox|chatterbox-turbo) echo ".venv-chatterbox" ;;
        styletts2)                   echo ".venv-styletts2" ;;
        *)                           echo "" ;;
    esac
}
uses_refs() { [[ "$1" == "chatterbox" || "$1" == "chatterbox-turbo" || "$1" == "styletts2" ]]; }

has_elevenlabs_key() {
    [[ -n "${ELEVENLABS_API_KEY:-}" ]] && return 0
    [[ -f .env ]] && grep -Eq '^[[:space:]]*ELEVENLABS_API_KEY[[:space:]]*=[[:space:]]*[^[:space:]]+' .env
}

if [[ -n "$REFS" && ! -d "$REFS" ]]; then
    echo "Reference folder '$REFS' not found." >&2
    exit 1
fi

yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
cyan()   { printf '\033[36m%s\033[0m\n' "$*"; }

summary_python=""
report=()

IFS=',' read -ra engine_list <<< "$ENGINES"
for engine in "${engine_list[@]}"; do
    engine="$(echo "$engine" | xargs)"
    [[ -z "$engine" ]] && continue
    venv="$(venv_for "$engine")"
    py="$venv/bin/python"
    if [[ -z "$venv" || ! -x "$py" ]]; then
        yellow "SKIP $engine : virtual environment '${venv:-?}' not found"
        report+=("$engine : skipped (no venv)")
        continue
    fi
    if [[ "$engine" == "elevenlabs" ]] && ! has_elevenlabs_key; then
        yellow "SKIP elevenlabs : ELEVENLABS_API_KEY not found in .env"
        report+=("elevenlabs : skipped (no API key)")
        continue
    fi
    [[ -z "$summary_python" ]] && summary_python="$py"

    use_refs=0
    if [[ -n "$REFS" ]] && uses_refs "$engine"; then use_refs=1; fi
    if [[ "$engine" == "elevenlabs" ]]; then
        label="elevenlabs-cloud"
    elif [[ $use_refs -eq 1 ]]; then
        label="$engine-refs-$DEVICE"
    else
        label="$engine-$DEVICE"
    fi
    [[ $FRESH -eq 1 && -d "results/$label" ]] && rm -rf "results/$label"

    args=(-m tts_bench.run --engine "$engine" --device "$DEVICE" --label "$label" --resume)
    [[ $use_refs -eq 1 ]] && args+=(--refs "$REFS")
    [[ "$LIMIT" -gt 0 ]] && args+=(--limit "$LIMIT")

    echo
    cyan "=== $label ==="
    started=$SECONDS
    "$py" "${args[@]}"
    code=$?
    minutes=$(awk "BEGIN { printf \"%.1f\", ($SECONDS - $started) / 60 }")
    if [[ $code -eq 0 ]]; then
        report+=("$label : OK ($minutes min)")
    else
        yellow "$label finished with errors; rerun the same command to retry the missing sentences."
        report+=("$label : errors (exit $code, $minutes min)")
    fi
done

if [[ -n "$summary_python" ]]; then
    echo
    cyan "=== summary ==="
    "$summary_python" -m tts_bench.summarize > /dev/null && echo "Wrote results/summary.md"
fi

echo
printf '%s\n' "${report[@]}"
