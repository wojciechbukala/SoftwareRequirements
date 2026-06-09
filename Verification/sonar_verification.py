#!/usr/bin/env python3
"""
Usage: python sonar_verification.py <run_dir>

Env: SONAR_URL   (default: http://localhost:9015)
     SONAR_TOKEN (optional — auto-generated with admin/admin if not set)

Last output line: SONAR_CSV:<sec_low>,<sec_med>,<sec_high>,<sec_sum>,<rel_low>,...,<maint_sum>
"""

import os, re, subprocess, sys, time
from pathlib import Path
import requests

def find_package_exclusions(run_dir):
    """Return sonar.exclusions pattern for pip-installed package dirs (*.dist-info heuristic)."""
    root = Path(run_dir)
    pkg_dirs = set()
    for dist_info in root.rglob("*.dist-info"):
        if dist_info.is_dir():
            pkg_dirs.add(dist_info.parent.relative_to(root))
    return ",".join(f"{d}/**" for d in pkg_dirs) if pkg_dirs else None

URL = os.environ.get("SONAR_URL", "http://localhost:9015")


def get(path, auth, **params):
    r = requests.get(f"{URL}{path}", params=params, auth=auth, timeout=15)
    r.raise_for_status()
    return r.json()


def ensure_token():
    token = os.environ.get("SONAR_TOKEN")
    if token:
        return token
    admin = ("admin", "admin")
    name  = "sonar-verification"
    requests.post(f"{URL}/api/user_tokens/revoke", auth=admin, data={"name": name})
    r = requests.post(f"{URL}/api/user_tokens/generate", auth=admin, data={"name": name})
    r.raise_for_status()
    return r.json()["token"]


def count(auth, key, type_, severities):
    return get("/api/issues/search", auth,
               componentKeys=key, types=type_,
               severities=",".join(severities), resolved="false", ps=1)["total"]


def wait_for_task(auth, task_id, timeout=300):
    """Poll a specific CE task by ID until it reaches a terminal state."""
    for _ in range(timeout // 3):
        try:
            s = get("/api/ce/task", auth, id=task_id).get("task", {}).get("status", "")
            if s == "SUCCESS":
                return True
            if s in ("FAILED", "CANCELED"):
                print(f"  WARN: CE task {task_id} finished with status: {s}")
                return False
        except requests.HTTPError:
            pass
        time.sleep(3)
    print(f"  WARN: CE task {task_id} did not complete within {timeout}s timeout")
    return False


def wait_for_component(auth, key, timeout=300):
    """Poll the component's current CE task until it reaches a terminal state."""
    for _ in range(timeout // 3):
        try:
            data = get("/api/ce/component", auth, component=key)
            # Check queue first — task may still be pending/in-progress
            queue = data.get("queue", [])
            if queue:
                time.sleep(3)
                continue
            s = data.get("current", {}).get("status", "")
            if s == "SUCCESS":
                return True
            if s in ("FAILED", "CANCELED"):
                print(f"  WARN: CE task for component '{key}' finished with status: {s}")
                return False
            # s == "" means no task found yet — keep waiting
        except requests.HTTPError:
            pass
        time.sleep(3)
    print(f"  WARN: CE task for component '{key}' did not complete within {timeout}s timeout")
    return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: sonar_verification.py <run_dir>")

    run_dir = str(Path(sys.argv[1]).resolve())
    key     = Path(run_dir).name
    token   = ensure_token()
    auth    = (token, "")

    exclusions = find_package_exclusions(run_dir)
    sonar_cmd  = [
        "docker", "run", "--rm", "--network", "host",
        "-v", f"{run_dir}:/usr/src",
        "sonarsource/sonar-scanner-cli",
        f"-Dsonar.projectKey={key}",
        "-Dsonar.sources=.", "-Dsonar.python.version=3",
        f"-Dsonar.host.url={URL}", "-Dsonar.scm.disabled=true",
        f"-Dsonar.token={token}",
        "-Dsonar.javascript.exclusions=**/templates/**",
    ]
    if exclusions:
        sonar_cmd.append(f"-Dsonar.exclusions={exclusions}")

    result = subprocess.run(sonar_cmd, capture_output=True, text=True)
    # Print scanner output so it appears in logs
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)

    if result.returncode != 0:
        sys.exit(f"ERROR: SonarQube scanner failed (exit {result.returncode})")

    # Extract CE task ID from scanner output for precise polling
    scanner_output = result.stdout + result.stderr
    task_id_match = re.search(r'api/ce/task\?id=([a-f0-9-]+)', scanner_output)

    ce_ok = False
    if task_id_match:
        task_id = task_id_match.group(1)
        ce_ok = wait_for_task(auth, task_id)
    else:
        print("  WARN: could not extract CE task ID from scanner output, falling back to component polling")
        ce_ok = wait_for_component(auth, key)

    if not ce_ok:
        print("  WARN: CE task did not succeed — metrics may be from a previous run or incomplete")

    # Fetch metrics regardless of CE task status (data may still be present)
    try:
        parts = []
        for label, type_ in [("Security","VULNERABILITY"),("Reliability","BUG"),("Maintainability","CODE_SMELL")]:
            low  = count(auth, key, type_, ["MINOR", "INFO"])
            med  = count(auth, key, type_, ["MAJOR"])
            high = count(auth, key, type_, ["BLOCKER", "CRITICAL"])
            print(f"  {label:18s}  Low={low}  Med={med}  High={high}  Sum={low+med+high}")
            parts += [low, med, high, low + med + high]

        print("SONAR_CSV:" + ",".join(str(x) for x in parts))
    except Exception as e:
        sys.exit(f"ERROR: failed to fetch metrics from SonarQube: {e}")
