"""
Runs the generated program against ScenarioA/B/C for a given run folder.

Usage:
    python run_projects.py <run_folder>
    python run_projects.py Runs/run-05-05-2026-Copilot-REQ2-Gemini-1

The run command is extracted from the first fenced code block in SUMMARY.md.
Placeholders like <input_directory> and <output_directory> are substituted
with the actual scenario path and a per-scenario output directory inside the run folder.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
VERIFICATION_DIR = REPO_ROOT / "Verification"
SCENARIO_SUFFIXES = ["ScenarioA", "ScenarioB", "ScenarioC"]


def extract_run_command(summary_path: Path) -> str | None:
    content = summary_path.read_text()
    match = re.search(r"```[a-z]*\n(.*?)\n```", content, re.DOTALL)
    if not match:
        return None
    block = match.group(1).strip()
    # Take only the first non-empty line (the actual command)
    for line in block.splitlines():
        line = line.strip()
        if line:
            return line
    return None


def find_scenarios(project_name: str) -> list[Path]:
    return [
        VERIFICATION_DIR / f"{project_name}-{suffix}"
        for suffix in SCENARIO_SUFFIXES
        if (VERIFICATION_DIR / f"{project_name}-{suffix}").exists()
    ]


def resolve_command(command: str, run_dir: Path) -> str:
    """Resolve paths in the command so that scripts in run_dir are found locally."""
    tokens = command.split()
    if not tokens:
        return command

    first = tokens[0]

    # Bare executable (no path separator, not a Python interpreter)
    if "/" not in first and not first.startswith("python"):
        if (run_dir / first).exists():
            return "./" + command
        return command

    # Python interpreter — check if the next argument is an absolute path
    # whose basename exists in run_dir (e.g. python3 /workspace/fleetrouter)
    if first.startswith("python") and len(tokens) >= 2:
        second = tokens[1]
        if second.startswith("/"):
            candidate = run_dir / Path(second).name
            if candidate.exists():
                tokens[1] = "./" + Path(second).name
                return " ".join(tokens)

    return command


def substitute_placeholders(command: str, input_dir: Path, output_dir: Path) -> str:
    # Context-aware: replace any <placeholder> that follows --input / --output
    cmd = re.sub(r"(--input\s+)<[^>]+>", rf"\1{input_dir}", command)
    cmd = re.sub(r"(--output\s+)<[^>]+>", rf"\1{output_dir}", cmd)
    # Fallback: placeholder names that embed "input" / "output"
    cmd = re.sub(r"<input[_-]?dir(?:ectory)?>", str(input_dir), cmd, flags=re.IGNORECASE)
    cmd = re.sub(r"<output[_-]?dir(?:ectory)?>", str(output_dir), cmd, flags=re.IGNORECASE)
    # Normalize `python` → `python3` when `python` binary is absent
    cmd = re.sub(r"(?<!\w)python(?!3)(?!\w)", "python3", cmd)
    return cmd


def parse_project_name(run_dir_name: str) -> str | None:
    # New format: PROJECT-REQx-Model-N  (e.g. Copilot-REQ1-Claude-1)
    # Old format: run-DD-MM-YYYY-PROJECT-REQx-Model-N
    m = re.match(r"^(?:run-\d{2}-\d{2}-\d{4}-)?([^-]+)-REQ\d+", run_dir_name)
    return m.group(1) if m else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify a run against ScenarioA/B/C inputs."
    )
    parser.add_argument(
        "run_folder",
        help="Path to the run folder (absolute or relative to repo root)",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_folder)
    if not run_dir.is_absolute():
        run_dir = REPO_ROOT / run_dir
    run_dir = run_dir.resolve()

    if not run_dir.exists():
        print(f"Error: run folder not found: {run_dir}", file=sys.stderr)
        sys.exit(1)

    summary = run_dir / "SUMMARY.md"
    if not summary.exists():
        print(f"Error: SUMMARY.md not found in {run_dir}", file=sys.stderr)
        sys.exit(1)

    command_template = extract_run_command(summary)
    if not command_template:
        print(
            "Error: no fenced code block found at the top of SUMMARY.md.\n"
            "Make sure the run was generated with the updated prompt.",
            file=sys.stderr,
        )
        sys.exit(1)

    project_name = parse_project_name(run_dir.name)
    if not project_name:
        print(
            f"Error: cannot determine project name from folder '{run_dir.name}'",
            file=sys.stderr,
        )
        sys.exit(1)

    scenarios = find_scenarios(project_name)
    if not scenarios:
        print(
            f"Error: no scenarios found for project '{project_name}' in {VERIFICATION_DIR}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Run:      {run_dir.name}")
    print(f"Project:  {project_name}")
    print(f"Command:  {command_template}")
    print(f"Scenarios: {[s.name for s in scenarios]}")
    print()

    results: dict[str, bool] = {}

    for scenario in scenarios:
        output_dir = run_dir / f"output-{scenario.name}"
        output_dir.mkdir(exist_ok=True)

        cmd = resolve_command(command_template, run_dir)
        cmd = substitute_placeholders(cmd, scenario, output_dir)

        print(f"{'='*60}")
        print(f"Scenario: {scenario.name}")
        print(f"Input:    {scenario}")
        print(f"Output:   {output_dir}")
        print(f"Command:  {cmd}")
        print()

        result = subprocess.run(cmd, shell=True, cwd=run_dir)

        ok = result.returncode == 0
        results[scenario.name] = ok
        print()
        print(f"Exit code: {result.returncode}  →  {'OK' if ok else 'FAILED'}")
        print()

    print(f"{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    all_ok = True
    for name, ok in results.items():
        status = "OK    " if ok else "FAILED"
        print(f"  {status}  {name}")
        if not ok:
            all_ok = False

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
