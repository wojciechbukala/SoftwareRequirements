#!/usr/bin/env python3
"""
Usage: python sonar_verification.py <run_dir>

Env: SONAR_URL   (default: http://localhost:9015)
     SONAR_TOKEN (optional — auto-generated with admin/admin if not set)

Last output line: SONAR_CSV:<sec_low>,<sec_med>,<sec_high>,<sec_sum>,<rel_low>,...,<maint_sum>
"""

import os, subprocess, sys, time
from pathlib import Path
import requests

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


def wait(auth, key, timeout=180):
    for _ in range(timeout // 3):
        try:
            s = get("/api/ce/component", auth, component=key).get("current", {}).get("status", "")
            if s == "SUCCESS": return True
            if s in ("FAILED", "CANCELED"): return False
        except requests.HTTPError:
            pass
        time.sleep(3)
    return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: sonar_verification.py <run_dir>")

    run_dir = str(Path(sys.argv[1]).resolve())
    key     = Path(run_dir).name
    token   = ensure_token()
    auth    = (token, "")

    subprocess.run([
        "docker", "run", "--rm", "--network", "host",
        "-v", f"{run_dir}:/usr/src",
        "sonarsource/sonar-scanner-cli",
        f"-Dsonar.projectKey={key}",
        "-Dsonar.sources=.", "-Dsonar.python.version=3",
        f"-Dsonar.host.url={URL}", "-Dsonar.scm.disabled=true",
        f"-Dsonar.token={token}",
    ], check=True)

    if not wait(auth, key):
        sys.exit("ERROR: analysis failed")

    parts = []
    for label, type_ in [("Security","VULNERABILITY"),("Reliability","BUG"),("Maintainability","CODE_SMELL")]:
        low  = count(auth, key, type_, ["MINOR", "INFO"])
        med  = count(auth, key, type_, ["MAJOR"])
        high = count(auth, key, type_, ["BLOCKER", "CRITICAL"])
        print(f"  {label:18s}  Low={low}  Med={med}  High={high}  Sum={low+med+high}")
        parts += [low, med, high, low + med + high]

    print("SONAR_CSV:" + ",".join(str(x) for x in parts))
