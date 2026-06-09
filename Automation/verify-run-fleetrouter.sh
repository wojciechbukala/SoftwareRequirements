#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CSV_PATH="$REPO_ROOT/Results/FleetRouter-functional.csv"

usage() {
    echo "Usage: $0 <run_folder>"
    echo "       $0 --all"
    exit 1
}

already_in_csv() {
    local run_name="$1"
    [[ -f "$CSV_PATH" ]] && grep -q "^${run_name}," "$CSV_PATH"
}

outputs_exist() {
    local folder="$1"
    [[ -d "$folder/output-FleetRouter-ScenarioA" ]] && \
    [[ -d "$folder/output-FleetRouter-ScenarioB" ]] && \
    [[ -d "$folder/output-FleetRouter-ScenarioC" ]]
}

process_run() {
    local run_folder="$1"
    local run_name
    run_name="$(basename "$run_folder")"

    if already_in_csv "$run_name"; then
        echo "Skipping $run_name (already in CSV)"
        return
    fi

    echo ""
    echo "========================================"
    echo "Processing: $run_name"
    echo "========================================"

    if outputs_exist "$run_folder"; then
        echo "=== Output folders already exist, skipping run step ==="
    else
        echo "=== Running project ==="
        python3 "$REPO_ROOT/Verification/run_projects.py" "$run_folder"
    fi

    echo ""
    echo "=== Verifying output ==="
    python3 "$REPO_ROOT/Verification/verify_run_fleetrouter.py" "$run_folder" || true
}

[[ $# -ne 1 ]] && usage

if [[ "$1" == "--all" ]]; then
    for folder in "$REPO_ROOT"/Runs/FleetRouter*; do
        [[ -d "$folder" ]] || continue
        process_run "$folder"
    done
else
    process_run "$1"
fi
