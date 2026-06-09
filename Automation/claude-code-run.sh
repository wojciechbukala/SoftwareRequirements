#!/usr/bin/env bash

# OPTIONS:
#   -r      path to REQ
#   -n      number of runs per specification
#   -m      model (default claude-sonnet)


set -euo pipefail

# Set defaults
REQ_PATH=""
RUNS=3
MODEL="claude-sonnet-4-6"

PROMPT="You are an expert software engineer. Read the requirements specification at REQUIREMENTS.md and implement the system in the current directory. Do not ask clarifying questions. Provide a summary of the work done in SUMMARY.md. Begin SUMMARY.md with a single fenced code block containing only the run command (no surrounding text or headings)."

DOCKER_IMAGE="experiment-claude-code:latest"

# Directories
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKERFILE="${REPO_ROOT}/Automation/Dockerfile.claude"
RUNS_DIR="${REPO_ROOT}/Runs"


# Arguments parsing
die() { echo "Error: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        -r) REQ_PATH="$2"; shift 2 ;;
        -n) RUNS="$2";     shift 2 ;;
        -m) MODEL="$2";    shift 2 ;;
        *)  die "Unknown option: $1" ;;
    esac
done

# Input validation
[[ -n "$REQ_PATH" ]]                || die "-r (REQ path) is required"
[[ -f "${REPO_ROOT}/${REQ_PATH}" ]] || die "REQ file not found: ${REPO_ROOT}/${REQ_PATH}"

command -v docker &>/dev/null || die "Docker not found"
command -v jq     &>/dev/null || die "jq not found — install with: apt-get install jq"
docker info &>/dev/null       || die "Docker daemon is not running"

ensure_sonarqube() {
    local url="${SONAR_URL:-http://localhost:9015}"
    local port="${url##*:}"; port="${port%%/*}"
    if curl -sf "${url}/api/system/status" -o /dev/null 2>/dev/null; then
        return 0
    fi
    echo "SonarQube nie odpowiada na porcie ${port} — próba uruchomienia kontenera..."
    local container
    container=$(docker ps -aq | while read -r id; do
        if docker inspect "$id" --format '{{range $p, $b := .HostConfig.PortBindings}}{{range $b}}{{.HostPort}} {{end}}{{end}}' 2>/dev/null | grep -qw "$port"; then
            docker inspect "$id" --format '{{.Name}}' | sed 's|^/||'
            break
        fi
    done | head -1)
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

# Build docker image
if ! docker image inspect "$DOCKER_IMAGE" &>/dev/null; then
    echo "Building Docker image..."
    docker build -f "$DOCKERFILE" -t "$DOCKER_IMAGE" "$REPO_ROOT"
    echo "Image built."
fi


# Run experiments
# Extract project name from parent dir (part after " - ") and REQ id from filename (part before first "-")
_REQ_DIR="$(dirname "$REQ_PATH")"
_REQ_BASENAME="$(basename "$REQ_PATH" .md)"
PROJECT="${_REQ_DIR##*-}"
REQ_ID="${_REQ_BASENAME%%-*}"
REQ_LABEL="${PROJECT}-${REQ_ID}"

# Derive short model label: claude-sonnet-4-6 → Claude-Sonnet
_MODEL_TIER=$(echo "$MODEL" | sed 's/claude-\([a-z]*\).*/\1/')
MODEL_LABEL="Claude-${_MODEL_TIER^}"

mkdir -p "$RUNS_DIR"

TOTAL_INPUT=0
TOTAL_OUTPUT=0
TOTAL_CACHE_READ=0
TOTAL_CACHE_CREATE=0
TOTAL_COST="0"

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
    if [[ "$REQ_ID" == "REQ3" ]]; then
        cp -r "${REPO_ROOT}/${_REQ_DIR}/Diagrams" "${RUN_DIR}/Diagrams"
    fi

    echo "=== Run ${i}/${RUNS}: ${RUN_ID} ==="

    EXIT_CODE=0
    docker run \
        --rm \
        --user "$(id -u):$(id -g)" \
        -e HOME=/home/researcher \
        -v "${HOME}/.claude:/home/researcher/.claude" \
        -v "${HOME}/.claude.json:/home/researcher/.claude.json" \
        -v "${RUN_DIR}:/workspace" \
        -w /workspace \
        "$DOCKER_IMAGE" \
        claude \
            --model "${MODEL}" \
            --permission-mode bypassPermissions \
            --output-format json \
            -p "${PROMPT}" \
        > "${RUN_DIR}/result.json" \
        2> >(tee "${RUN_DIR}/session.log" >&2) || EXIT_CODE=$?

    INPUT=$(jq -r       '.usage.input_tokens                // 0' "${RUN_DIR}/result.json" 2>/dev/null || echo 0)
    OUTPUT=$(jq -r      '.usage.output_tokens               // 0' "${RUN_DIR}/result.json" 2>/dev/null || echo 0)
    CACHE_READ=$(jq -r  '.usage.cache_read_input_tokens     // 0' "${RUN_DIR}/result.json" 2>/dev/null || echo 0)
    CACHE_CREATE=$(jq -r '.usage.cache_creation_input_tokens // 0' "${RUN_DIR}/result.json" 2>/dev/null || echo 0)
    COST=$(jq -r        '.cost_usd                          // 0' "${RUN_DIR}/result.json" 2>/dev/null || echo 0)

    printf "  Tokens — input: %s  output: %s  cache_read: %s  cache_create: %s  cost: \$%s\n" \
        "$INPUT" "$OUTPUT" "$CACHE_READ" "$CACHE_CREATE" "$COST"

    TOKENS_SUM=$(( INPUT + OUTPUT + CACHE_READ + CACHE_CREATE ))
    CSV_FILE="${REPO_ROOT}/Results/${PROJECT}-static.csv"

    TOTAL_INPUT=$(( TOTAL_INPUT + INPUT ))
    TOTAL_OUTPUT=$(( TOTAL_OUTPUT + OUTPUT ))
    TOTAL_CACHE_READ=$(( TOTAL_CACHE_READ + CACHE_READ ))
    TOTAL_CACHE_CREATE=$(( TOTAL_CACHE_CREATE + CACHE_CREATE ))
    TOTAL_COST=$(awk "BEGIN { printf \"%.6f\", $TOTAL_COST + $COST }")

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