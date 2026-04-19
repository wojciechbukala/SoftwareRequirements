#!/usr/bin/env bash

# OPTIONS:
#   -r      path to REQ
#   -n      number of runs per specification
#   -m      model (default claude-sonet)


set -euo pipefail

# Set defaults
REQ_PATH=""
RUNS=3
MODEL="claude-sonnet-4-6"

PROMPT="You are an expert software engineer. Read the requirements specification at REQUIREMENTS.md and implement the system in the current directory. Do not ask clarifying questions. Provide a summary of the work done in SUMMARY.md"

DOCKER_IMAGE="experiment-claude-code:latest"

# Directories
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKERFILE="${REPO_ROOT}/Automation/Dockerfile.experiment"
RUNS_DIR="${REPO_ROOT}/Runs"
DATE_TAG="$(date '+%d-%m-%Y')"


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
docker info &>/dev/null       || die "Docker daemon is not running"

# Build docker image
if ! docker image inspect "$DOCKER_IMAGE" &>/dev/null; then
    echo "Building Docker image..."
    docker build -f "$DOCKERFILE" -t "$DOCKER_IMAGE" "$REPO_ROOT"
    echo "Image built."
fi


# Run experiments
REQ_LABEL="${REQ_PATH%.md}"
REQ_LABEL="${REQ_LABEL//\//-}"

mkdir -p "$RUNS_DIR"

for ((i = 1; i <= RUNS; i++)); do
    RUN_ID="run-${DATE_TAG}-${REQ_LABEL}-${i}"
    RUN_DIR="${RUNS_DIR}/${RUN_ID}"

    mkdir -p "$RUN_DIR"
    cp "${REPO_ROOT}/${REQ_PATH}" "${RUN_DIR}/REQUIREMENTS.md"

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
            -p "${PROMPT}" \
        2>&1 | tee "${RUN_DIR}/session.log"; EXIT_CODE=${PIPESTATUS[0]}

    echo "Exit code: ${EXIT_CODE}"
    echo ""
done