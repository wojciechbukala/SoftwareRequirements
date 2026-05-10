#!/usr/bin/env python3
"""
Evaluates Copilot output CSV files against the expected behaviour derived
from the scenario inputs.

Usage:
    python evaluate_outputs.py <run_folder>

Example:
    python evaluate_outputs.py /home/wojciech/SoftwareRequirements/Runs/run-27-04-2026-Copilot-REQ2-Claude-2

The script looks for output folders inside the run folder:
    <run_folder>/output-Copilot-ScenarioA
    <run_folder>/output-Copilot-ScenarioB
    <run_folder>/output-Copilot-ScenarioC

And compares them against the reference scenario inputs located at:
    <repo_root>/Verification/Copilot-ScenarioA
    <repo_root>/Verification/Copilot-ScenarioB
    <repo_root>/Verification/Copilot-ScenarioC
"""

import csv
import sys
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

# The script lives in Verification/, so repo root is one level up
REPO_ROOT = Path(__file__).parent.parent
VERIFICATION_DIR = REPO_ROOT / "Verification"

SCENARIOS = ["ScenarioA", "ScenarioB", "ScenarioC"]

# Expected column names for each output file
EXPECTED_HEADERS = {
    "state_log.csv":        ["timestamp", "previous_state", "current_state", "trigger_event"],
    "commands_log.csv":     ["timestamp", "actuator_id", "values"],
    "feature_decision.csv": ["timestamp", "feature", "decision"],
}

VALID_STATES = {"ENGAGED", "DISENGAGED", "AWAITINGRESPONSE", "ALARMING"}

# Accepted feature names — programs may use various casings/separators,
# so we normalise everything to lowercase+no_separator before comparing.
# e.g. "LaneKeeping", "lane_keeping", "Lane Keeping" all map to "lanekeeping"
VALID_FEATURES_NORM = {"emergencybraking", "lanekeeping", "cruisecontrol"}

ATTENTIVENESS_INTERVAL = 120.0
RESPONSE_WINDOW        = 5.0

# ── Helpers ───────────────────────────────────────────────────────────────────

def read_csv(path: Path) -> list[dict]:
    """Read a CSV file, strip BOM and whitespace from all keys and values."""
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            clean = {k.strip(): v.strip() for k, v in row.items() if k is not None}
            rows.append(clean)
        return rows

def normalize_feature(feature: str) -> str:
    """Normalize feature name for comparison, ignoring case and separators.
    e.g. LaneKeeping / lane_keeping / lane keeping all become lanekeeping."""
    return feature.lower().replace("_", "").replace(" ", "").replace("-", "")

def to_float(value: str) -> float | None:
    """Try to parse a string as float. Return None on failure."""
    try:
        return float(value.strip())
    except (ValueError, AttributeError):
        return None

def near(a: float, b: float, tol: float = 0.5) -> bool:
    """Return True if two timestamps are within tol seconds of each other."""
    return abs(a - b) <= tol

def ok(msg: str):
    print(f"  ✓  {msg}")

def fail(msg: str, detail: str = ""):
    print(f"  ✗  {msg}")
    if detail:
        print(f"       → {detail}")

# ── Golden oracle ─────────────────────────────────────────────────────────────

def simulate(scenario_dir: Path) -> dict:
    """
    Replay the Copilot state machine on the scenario inputs and return
    the expected outputs that can be checked deterministically:

      state_transitions    – list of (ts, prev_state, cur_state, trigger)
      eb_decisions         – list of (ts, "BRAKE" or "NO_BRAKE") for every Lidar event
      brake_command_ts     – timestamps where a brake command must appear in commands_log
      camera_engaged_ts    – camera event timestamps while Engaged (decisions must exist)
      camera_disengaged_ts – camera event timestamps while Disengaged (no commands allowed)
    """
    # Load and merge both input files into one chronological stream
    sensor_rows = read_csv(scenario_dir / "sensor_log.csv")
    driver_rows = read_csv(scenario_dir / "driver_events.csv")

    stream = []
    for r in sensor_rows:
        stream.append({"ts": float(r["timestamp"]), "kind": "sensor", **r})
    for r in driver_rows:
        stream.append({"ts": float(r["timestamp"]), "kind": "driver", **r})
    stream.sort(key=lambda r: r["ts"])

    # Simulate the state machine
    state = "DISENGAGED"
    last_engage_ts: float | None = None   # when we last entered Engaged
    awaiting_since: float | None = None   # when AwaitingResponse started

    state_transitions    = []
    eb_decisions         = []
    brake_command_ts     = []
    camera_engaged_ts    = []
    camera_disengaged_ts = []

    def transition(ts, new_state, trigger):
        nonlocal state
        if state != new_state:
            state_transitions.append((ts, state, new_state, trigger))
            state = new_state

    for event in stream:
        ts = event["ts"]

        # Check if attentiveness prompt is due (every 120 s while Engaged).
        # The prompt fires at exactly last_engage_ts + 120, NOT at the
        # timestamp of the event that happens to be processed next - this
        # is essential to test whether the implementation correctly resets
        # the timer after a valid response.
        if state == "ENGAGED" and last_engage_ts is not None:
            if ts - last_engage_ts >= ATTENTIVENESS_INTERVAL:
                prompt_ts = last_engage_ts + ATTENTIVENESS_INTERVAL
                transition(prompt_ts, "AWAITINGRESPONSE", "ATTENTIVENESS_PROMPT")
                awaiting_since = prompt_ts
                last_engage_ts = prompt_ts  # next prompt 120 s from now

        # Check if the 5-second response window expired (-> Alarming)
        if state == "AWAITINGRESPONSE" and awaiting_since is not None:
            if ts - awaiting_since > RESPONSE_WINDOW:
                timeout_ts = awaiting_since + RESPONSE_WINDOW
                transition(timeout_ts, "ALARMING", "TIMEOUT")
                awaiting_since = None

        # Process the event itself
        if event["kind"] == "driver":
            etype = event["event_type"].strip()
            force_str = event.get("value", "").strip()
            force = float(force_str) if force_str else None

            if etype == "ENGAGE":
                if state == "DISENGAGED":
                    transition(ts, "ENGAGED", "ENGAGE")
                    last_engage_ts = ts

            elif etype == "DISENGAGE":
                if state != "DISENGAGED":
                    transition(ts, "DISENGAGED", "DISENGAGE")
                    last_engage_ts = None
                    awaiting_since = None

            elif etype == "STEERING_FORCE" and force is not None:
                if force > 10.0:
                    # Hard override — disengage from any state
                    if state != "DISENGAGED":
                        transition(ts, "DISENGAGED", "FORCE_OVERRIDE")
                        last_engage_ts = None
                        awaiting_since = None
                elif state == "AWAITINGRESPONSE":
                    if force <= 3.0:
                        # Valid attentiveness response
                        transition(ts, "ENGAGED", "VALID_RESPONSE")
                        last_engage_ts = ts  # restart the 120-s timer
                        awaiting_since = None
                    # 3 < force <= 10 while AwaitingResponse -> ignored

        else:  # sensor event
            stype = event["sensor_type"].strip()
            value = float(event["data_value"])

            if stype == "Lidar":
                if value < 5.0:
                    eb_decisions.append((ts, "BRAKE"))
                    brake_command_ts.append(ts)
                else:
                    eb_decisions.append((ts, "NO_BRAKE"))

            elif stype == "Camera":
                if state in ("ENGAGED", "AWAITINGRESPONSE"):
                    camera_engaged_ts.append(ts)
                else:
                    camera_disengaged_ts.append(ts)

    return {
        "state_transitions":    state_transitions,
        "eb_decisions":         eb_decisions,
        "brake_command_ts":     brake_command_ts,
        "camera_engaged_ts":    camera_engaged_ts,
        "camera_disengaged_ts": camera_disengaged_ts,
    }

# ── Level 2: Structural checks ────────────────────────────────────────────────

def check_structure(output_dir: Path) -> int:
    """Check file existence, headers, empty rows, and column types. Returns number of failures."""
    failures = 0
    print("\n  [Level 2 - Structure]")

    for fname, expected_cols in EXPECTED_HEADERS.items():
        fpath = output_dir / fname

        if not fpath.exists():
            fail(f"{fname} exists", "File not found")
            failures += 1
            continue
        ok(f"{fname} exists")

        rows = read_csv(fpath)

        # Fail explicitly if file has no data rows — an empty file scores
        # better than a file with bad data, which would be misleading.
        if not rows:
            fail(f"{fname} has data rows", "File exists but contains no data rows")
            failures += 1
            continue
        ok(f"{fname} has data rows ({len(rows)})")

        # Header
        actual_cols = [c.strip().lower() for c in rows[0].keys()]
        expected_norm = [c.lower() for c in expected_cols]
        if actual_cols == expected_norm:
            ok(f"{fname} header correct")
        else:
            fail(f"{fname} header", f"expected {expected_cols}, got {list(rows[0].keys())}")
            failures += 1
            continue  # further checks would use wrong column names

        # No fully-empty rows
        empty = [i + 2 for i, r in enumerate(rows) if all(v.strip() == "" for v in r.values())]
        if empty:
            fail(f"{fname} no empty rows", f"empty at lines: {empty}")
            failures += 1
        else:
            ok(f"{fname} no empty rows")

        # timestamp is a float
        bad_ts = [i + 2 for i, r in enumerate(rows) if to_float(r.get("timestamp", "")) is None]
        if bad_ts:
            fail(f"{fname} timestamp is numeric", f"bad values at lines: {bad_ts}")
            failures += 1
        else:
            ok(f"{fname} timestamp is numeric")

        # File-specific type checks
        if fname == "state_log.csv":
            bad = [i + 2 for i, r in enumerate(rows)
                   if r.get("previous_state", "").strip().upper() not in VALID_STATES
                   or r.get("current_state",  "").strip().upper() not in VALID_STATES]
            if bad:
                fail("state_log states are valid enum values", f"lines: {bad}")
                failures += 1
            else:
                ok("state_log states are valid enum values")

        if fname == "feature_decision.csv":
            bad = [i + 2 for i, r in enumerate(rows)
                   if normalize_feature(r.get("feature", "")) not in VALID_FEATURES_NORM]
            if bad:
                bad_vals = [rows[i - 2].get("feature", "") for i in bad]
                fail("feature_decision feature column is valid",
                     f"unknown values {bad_vals} at lines: {bad}")
                failures += 1
            else:
                ok("feature_decision feature column is valid")

    return failures

# ── Level 1: Logic checks ─────────────────────────────────────────────────────

def check_logic(output_dir: Path, golden: dict) -> int:
    """Check deterministic behavioural rules against the golden oracle. Returns number of failures."""
    failures = 0
    print("\n  [Level 1 - Logic]")

    def load(fname):
        p = output_dir / fname
        return read_csv(p) if p.exists() else []

    state_rows = load("state_log.csv")
    cmd_rows   = load("commands_log.csv")
    fd_rows    = load("feature_decision.csv")

    # Count how many expected logic checks there are in this scenario,
    # so that empty files get a failure for each one they skip rather than
    # silently passing by iterating over nothing.
    expected_trans = golden["state_transitions"]
    expected_eb    = golden["eb_decisions"]
    n_logic_checks = (
        3                              # monotonic timestamps (one per output file)
        + 1                            # cross-file consistency (1b)
        + 1                            # state row count (2)
        + 3                            # state sequence: exact + subsequence + no self-transitions (3a, 3b, 3c)
        + len(expected_eb)             # one EB decision check per Lidar event
        + len(golden["brake_command_ts"])
        + (len(golden["camera_disengaged_ts"]) or 1)  # at least the N/A check
        + len(golden["camera_engaged_ts"])
    )

    # If all output files are empty, fail every logic check at once and return.
    all_empty = not state_rows and not cmd_rows and not fd_rows
    if all_empty:
        fail(f"all output files are empty — skipping {n_logic_checks} logic check(s)",
             f"every logic check counts as a failure")
        return n_logic_checks

    # 1. Timestamps monotonically non-decreasing in every output file
    for fname, rows in [("state_log.csv", state_rows),
                         ("commands_log.csv", cmd_rows),
                         ("feature_decision.csv", fd_rows)]:
        ts_vals = [to_float(r.get("timestamp", "")) for r in rows]
        ts_vals = [v for v in ts_vals if v is not None]
        bad = [(ts_vals[i], ts_vals[i + 1])
               for i in range(len(ts_vals) - 1) if ts_vals[i] > ts_vals[i + 1]]
        if bad:
            fail(f"{fname} timestamps are monotonic", f"decreasing pairs: {bad[:3]}")
            failures += 1
        else:
            ok(f"{fname} timestamps are monotonic")

    # 1b. Cross-file consistency: implementations that process input files
    #     sequentially (e.g. all sensor events first, then all driver events)
    #     produce outputs whose per-file timestamps look monotonic, but the
    #     time ranges of the three files overlap implausibly. We check that
    #     the time intervals [min_ts, max_ts] of any two output files
    #     either fully overlap or are disjoint - one cannot strictly precede
    #     the other if both files should reflect the same merged stream.
    file_ranges = []
    for fname, rows in [("state_log.csv", state_rows),
                         ("commands_log.csv", cmd_rows),
                         ("feature_decision.csv", fd_rows)]:
        ts_vals = [to_float(r.get("timestamp", "")) for r in rows]
        ts_vals = [v for v in ts_vals if v is not None]
        if ts_vals:
            file_ranges.append((fname, min(ts_vals), max(ts_vals)))

    cross_violations = []
    for i in range(len(file_ranges)):
        for j in range(i + 1, len(file_ranges)):
            n1, lo1, hi1 = file_ranges[i]
            n2, lo2, hi2 = file_ranges[j]
            # Strict precedence: hi1 < lo2 means file i finishes before file j starts.
            # That's only acceptable if their timestamp ranges are genuinely disjoint
            # in the input stream - which is rare. Since merged inputs interleave,
            # output ranges should overlap.
            if hi1 < lo2 - 0.5:
                cross_violations.append(f"{n1} ends at {hi1} before {n2} starts at {lo2}")
            elif hi2 < lo1 - 0.5:
                cross_violations.append(f"{n2} ends at {hi2} before {n1} starts at {lo1}")
    if cross_violations:
        fail("output files reflect interleaved (merged) input streams",
             "; ".join(cross_violations[:3]))
        failures += 1
    else:
        ok("output files reflect interleaved (merged) input streams")

    # 2. State transition count
    n_exp = len(expected_trans)
    n_act = len(state_rows)
    if n_act == n_exp:
        ok(f"state_log row count: exact match ({n_exp} rows)")
    elif n_act > n_exp:
        # More rows than expected is not necessarily wrong — the program may
        # log extra intermediate transitions (e.g. attentiveness cycles).
        # We report it as informational rather than a hard failure here;
        # the subsequence check below decides if the core sequence is present.
        ok(f"state_log row count: {n_act} rows (expected {n_exp}, extra rows present — checked via subsequence)")
    else:
        exp_pairs = [(t[1], t[2]) for t in expected_trans]
        fail("state_log row count",
             f"expected {n_exp}, got {n_act} (too few). Expected transitions: {exp_pairs}")
        failures += 1

    # 3a. State transition exact sequence
    #     Pass only when the output matches the expected sequence exactly,
    #     including timestamps (within tolerance).
    # 3b. State transition subsequence
    #     Pass when the expected sequence appears as an ordered subsequence
    #     of the actual output (handles programs that log extra transitions),
    #     AND the timestamps of the matched expected transitions match
    #     the predicted timestamps within tolerance.
    #     Both 3a and 3b are reported separately.
    if state_rows:
        actual_pairs   = [(r.get("previous_state", "").strip().upper(),
                           r.get("current_state",  "").strip().upper()) for r in state_rows]
        actual_ts      = [to_float(r.get("timestamp", "")) for r in state_rows]
        expected_pairs = [(t[1].upper(), t[2].upper()) for t in expected_trans]
        expected_ts    = [t[0] for t in expected_trans]

        # 3a – exact match (states AND timestamps)
        if actual_pairs == expected_pairs and len(actual_ts) == len(expected_ts):
            mismatched = [(i, actual_ts[i], expected_ts[i])
                          for i in range(len(expected_ts))
                          if actual_ts[i] is None or not near(actual_ts[i], expected_ts[i])]
            if not mismatched:
                ok("state_log transition sequence: exact match")
            else:
                fail("state_log transition sequence: exact match",
                     f"timestamp mismatch (idx, actual, expected): {mismatched[:3]}")
                failures += 1
        else:
            fail("state_log transition sequence: exact match",
                 f"expected {expected_pairs}, got {actual_pairs}")
            failures += 1

        # 3b – subsequence check with timestamp verification.
        #      We greedily walk through actual_pairs looking for each expected
        #      pair in order, and when we find a match we also check its
        #      timestamp. This catches programs that emit the right state
        #      sequence but at wrong times (e.g. attentiveness prompt fired
        #      when an event happens to arrive instead of at last_engage+120).
        def find_subsequence_with_ts(exp_pairs, exp_ts, act_pairs, act_ts):
            """Return list of (idx_in_actual, expected_ts) for each matched expected pair,
            or None if subsequence not found."""
            matches = []
            j = 0
            for i, pair in enumerate(act_pairs):
                if j < len(exp_pairs) and pair == exp_pairs[j]:
                    matches.append((i, exp_ts[j]))
                    j += 1
            return matches if j == len(exp_pairs) else None

        matches = find_subsequence_with_ts(expected_pairs, expected_ts,
                                           actual_pairs, actual_ts)
        if matches is None:
            fail("state_log transition sequence: expected transitions present as subsequence",
                 f"expected {expected_pairs} not found as subsequence in {actual_pairs}")
            failures += 1
        else:
            ts_mismatches = [(idx, actual_ts[idx], exp_t)
                             for idx, exp_t in matches
                             if actual_ts[idx] is None or not near(actual_ts[idx], exp_t)]
            if not ts_mismatches:
                ok("state_log transition sequence: expected transitions present as subsequence")
            else:
                fail("state_log transition sequence: expected transitions present as subsequence (timestamps)",
                     f"timestamp mismatch (actual_idx, actual_ts, expected_ts): {ts_mismatches[:3]}")
                failures += 1

        # 3c – no self-transitions: spec says state_log records only actual
        #      changes of state, so previous_state must always differ from
        #      current_state. This catches implementations that log e.g.
        #      ENGAGE while already Engaged or DISENGAGE while already Disengaged.
        self_trans = [(i + 2, p, c) for i, (p, c) in enumerate(actual_pairs) if p == c]
        if self_trans:
            fail("state_log contains no self-transitions",
                 f"self-transitions at lines: {self_trans[:5]}")
            failures += 1
        else:
            ok("state_log contains no self-transitions")

    # 4. Emergency braking decisions (one per Lidar event, correct BRAKE/NO_BRAKE)
    expected_eb = golden["eb_decisions"]
    eb_rows = [r for r in fd_rows if normalize_feature(r.get("feature", "")) == "emergencybraking"]

    if len(eb_rows) == len(expected_eb):
        ok(f"emergency_braking decision count ({len(expected_eb)})")
    else:
        fail("emergency_braking decision count",
             f"expected {len(expected_eb)}, got {len(eb_rows)}")
        failures += 1

    for i, (exp_ts, exp_dec) in enumerate(expected_eb):
        label = f"EB decision #{i + 1} (t={exp_ts}): expected {exp_dec}"
        if i >= len(eb_rows):
            fail(label, "row missing")
            failures += 1
            continue
        row = eb_rows[i]
        actual_dec = row.get("decision", "").strip().upper()
        actual_ts  = to_float(row.get("timestamp", ""))
        if actual_dec == exp_dec.upper() and actual_ts is not None and near(actual_ts, exp_ts):
            ok(label)
        else:
            fail(label, f"got decision='{actual_dec}' at t={actual_ts}")
            failures += 1

    # 5. Every BRAKE decision must have a matching entry in commands_log
    cmd_ts_vals = [to_float(r.get("timestamp", "")) for r in cmd_rows]
    for exp_ts in golden["brake_command_ts"]:
        found = any(v is not None and near(v, exp_ts) for v in cmd_ts_vals)
        if found:
            ok(f"brake command present in commands_log at t={exp_ts}")
        else:
            fail(f"brake command present in commands_log at t={exp_ts}", "no matching row found")
            failures += 1

    # 6. No camera-derived commands while in Disengaged state
    dis_ts_list = golden["camera_disengaged_ts"]
    if dis_ts_list:
        violations = [
            exp_ts for exp_ts in dis_ts_list
            if any(v is not None and near(v, exp_ts) for v in cmd_ts_vals)
        ]
        if violations:
            fail("no commands issued for camera events while Disengaged",
                 f"found commands near t={violations}")
            failures += 1
        else:
            ok("no commands issued for camera events while Disengaged")
    else:
        ok("no commands issued for camera events while Disengaged (N/A)")

    # 7. Camera events while Engaged -> feature decisions must exist
    fd_ts_vals = [to_float(r.get("timestamp", "")) for r in fd_rows]
    for exp_ts in golden["camera_engaged_ts"]:
        found = any(v is not None and near(v, exp_ts) for v in fd_ts_vals)
        if found:
            ok(f"feature decisions exist for camera event at t={exp_ts}")
        else:
            fail(f"feature decisions exist for camera event at t={exp_ts}", "no matching row found")
            failures += 1

    return failures

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) != 2:
        print("Usage:   python evaluate_outputs.py <run_folder>")
        print("Example: python evaluate_outputs.py /home/wojciech/SoftwareRequirements/Runs/run-27-04-2026-Copilot-REQ2-Claude-2")
        sys.exit(1)

    run_dir = Path(sys.argv[1]).resolve()
    if not run_dir.exists():
        print(f"Error: run folder not found: {run_dir}")
        sys.exit(1)

    print(f"Run: {run_dir.name}")

    total_failures    = 0
    scenarios_checked = 0

    for scenario_name in SCENARIOS:
        output_dir   = run_dir / f"output-Copilot-{scenario_name}"
        scenario_dir = VERIFICATION_DIR / f"Copilot-{scenario_name}"

        # Skip silently if both sides are missing (scenario not applicable)
        if not output_dir.exists() and not scenario_dir.exists():
            continue

        print(f"\n{'─' * 60}")
        print(f"Scenario: {scenario_name}")

        if not scenario_dir.exists():
            print(f"  ERROR: reference inputs not found at {scenario_dir}")
            total_failures += 1
            continue

        if not output_dir.exists():
            print(f"  ERROR: output folder not found: {output_dir}")
            total_failures += 1
            continue

        golden   = simulate(scenario_dir)
        failures = check_structure(output_dir) + check_logic(output_dir, golden)

        print(f"\n  Result: {'PASS' if failures == 0 else f'FAIL  ({failures} check(s) failed)'}")
        total_failures    += failures
        scenarios_checked += 1

    print(f"\n{'=' * 60}")
    if scenarios_checked == 0:
        print("No scenarios found. Make sure output-Copilot-ScenarioX folders exist in the run folder.")
    elif total_failures == 0:
        print(f"ALL CHECKS PASSED  ({scenarios_checked} scenario(s))")
    else:
        print(f"FAILED  ({total_failures} total failure(s) across {scenarios_checked} scenario(s))")
    print(f"{'=' * 60}")

    sys.exit(0 if total_failures == 0 else 1)


if __name__ == "__main__":
    main()