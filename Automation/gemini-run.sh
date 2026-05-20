#!/usr/bin/env bash

# OPTIONS:
#   -r      path to REQ
#   -n      number of runs per specification
#   -m      model (default gemini-2.5-flash)

set -euo pipefail

REQ_PATH=""
RUNS=3
MODEL="gemini-2.5-flash"

PROMPT="You are an expert software engineer. Read the requirements specification at REQUIREMENTS.md and implement the system in the current directory. Do not ask clarifying questions. Provide a summary of the work done in SUMMARY.md. Begin SUMMARY.md with a single fenced code block containing only the run command (no surrounding text or headings)."

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNS_DIR="${REPO_ROOT}/Runs"

die() { echo "Error: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        -r) REQ_PATH="$2"; shift 2 ;;
        -n) RUNS="$2";     shift 2 ;;
        -m) MODEL="$2";    shift 2 ;;
        *)  die "Unknown option: $1" ;;
    esac
done

[[ -n "$REQ_PATH" ]]                || die "-r (REQ path) is required"
[[ -f "${REPO_ROOT}/${REQ_PATH}" ]] || die "REQ file not found: ${REPO_ROOT}/${REQ_PATH}"

ensure_sonarqube() {
    local url="${SONAR_URL:-http://localhost:9015}"
    local port="${url##*:}"; port="${port%%/*}"
    if curl -sf "${url}/api/system/status" -o /dev/null 2>/dev/null; then
        return 0
    fi
    echo "SonarQube nie odpowiada na porcie ${port} — próba uruchomienia kontenera..."
    local container
    container=$(docker ps -a --filter "publish=${port}" --format "{{.Names}}" | head -1)
    [[ -n "$container" ]] || { echo "  WARN: nie znaleziono kontenera SonarQube na porcie ${port} — pomijam"; return 1; }
    docker start "$container"
    echo -n "  Oczekiwanie na SonarQube"
    for _ in $(seq 1 20); do
        sleep 3
        echo -n "."
        if curl -sf "${url}/api/system/status" -o /dev/null 2>/dev/null; then
            echo " gotowy."
            return 0
        fi
    done
    echo " timeout — pomijam SonarQube"
    return 1
}

ensure_sonarqube || true

_REQ_DIR="$(dirname "$REQ_PATH")"
_REQ_BASENAME="$(basename "$REQ_PATH" .md)"
PROJECT="${_REQ_DIR##*-}"
REQ_ID="${_REQ_BASENAME%%-*}"
REQ_LABEL="${PROJECT}-${REQ_ID}"

# Derive short model label: gemini-2.5-flash → Gemini-Flash
_MODEL_TIER=$(echo "$MODEL" | sed 's/gemini-[0-9.]*-\([a-z]*\).*/\1/')
MODEL_LABEL="Gemini-${_MODEL_TIER^}"

mkdir -p "$RUNS_DIR"

TOTAL_INPUT=0
TOTAL_OUTPUT=0
TOTAL_CACHE_READ=0
TOTAL_CACHE_CREATE=0

START=1
while [[ -d "${RUNS_DIR}/${REQ_LABEL}-${MODEL_LABEL}-${START}" ]]; do
    (( START++ ))
done

for ((i = START; i < START + RUNS; i++)); do
    RUN_ID="${REQ_LABEL}-${MODEL_LABEL}-${i}"
    RUN_DIR="${RUNS_DIR}/${RUN_ID}"

    mkdir -p "$RUN_DIR"
    cp "${REPO_ROOT}/${REQ_PATH}" "${RUN_DIR}/REQUIREMENTS.md"
    if [[ "$PROJECT" == "SeatsReservation" ]]; then
        cp -r "${REPO_ROOT}/Problem2-SeatsReservation/UI_Mockups" "${RUN_DIR}/UI_Mockups"
    fi

    echo "=== Run ${i}/${RUNS}: ${RUN_ID} ==="

    EXIT_CODE=0
    GEMINI_JSON=$(cd "$RUN_DIR" && gemini --yolo --model gemini-2.5-flash --output-format json -p "$PROMPT") \
        || EXIT_CODE=$?

    # Dynamicznie pobierz nazwę modelu z JSON (może różnić się od aliasu)
    MODEL_KEY=$(echo "$GEMINI_JSON" | jq -r '.stats.models | keys[0]' 2>/dev/null || echo "")

    INPUT=$(echo      "$GEMINI_JSON" | jq -r ".stats.models[\"$MODEL_KEY\"].tokens.prompt     // 0" 2>/dev/null || echo "0")
    OUTPUT=$(echo     "$GEMINI_JSON" | jq -r ".stats.models[\"$MODEL_KEY\"].tokens.candidates // 0" 2>/dev/null || echo "0")
    CACHE_READ=$(echo "$GEMINI_JSON" | jq -r ".stats.models[\"$MODEL_KEY\"].tokens.cached     // 0" 2>/dev/null || echo "0")
    CACHE_CREATE=0

    if [[ "$INPUT" == "0" && "$OUTPUT" == "0" && -n "$GEMINI_JSON" ]]; then
        echo "  WARN: nie udało się sparsować tokenów. Pierwsze 300 znaków JSON:"
        echo "$GEMINI_JSON" | head -c 300
        echo ""
    fi

    TOKENS_SUM=$(( INPUT + OUTPUT + CACHE_READ + CACHE_CREATE ))

    printf "  Tokens — input: %s  output: %s  cache_read: %s  cache_create: %s\n" \
        "$INPUT" "$OUTPUT" "$CACHE_READ" "$CACHE_CREATE"

    CSV_FILE="${REPO_ROOT}/Results/${PROJECT}-static.csv"

    echo "=== Pylint: ${RUN_ID} ==="
    (cd "$RUN_DIR" && "${REPO_ROOT}/.venv/bin/python3" "${REPO_ROOT}/Verification/pylint_verification.py")
    PYLINT_SCORE=$(grep -oP '(?<=rated at )\d+\.\d+' "${RUN_DIR}/pylint-report.txt" 2>/dev/null || echo "")
    echo ""

    echo "=== SonarQube: ${RUN_ID} ==="
    SONAR_CSV_DATA=""
    if SONAR_OUT=$("${REPO_ROOT}/.venv/bin/python3" "${REPO_ROOT}/Verification/sonar_verification.py" "$RUN_DIR" 2>&1); then
        echo "$SONAR_OUT"
        SONAR_CSV_DATA=$(echo "$SONAR_OUT" | grep "^SONAR_CSV:" | cut -d: -f2 || true)
    else
        echo "$SONAR_OUT"
        echo "  SonarQube skipped (not running or error)"
    fi
    echo ""

    CSV_ROW="${RUN_ID},${INPUT},${OUTPUT},${CACHE_READ},${CACHE_CREATE},${TOKENS_SUM},${PYLINT_SCORE},${SONAR_CSV_DATA}"
    if [[ -f "$CSV_FILE" ]]; then
        echo "$CSV_ROW" >> "$CSV_FILE"
        echo "  CSV: zapisano -> $(basename "$CSV_FILE")"
    else
        echo "  WARN: plik CSV nie istnieje: $CSV_FILE"
        echo "  CSV row: $CSV_ROW"
    fi

    echo "Exit code: ${EXIT_CODE}"
    echo ""

done