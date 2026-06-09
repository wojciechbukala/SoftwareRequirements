#!/usr/bin/env python3
"""
Evaluates FleetRouter output CSV files against the expected behaviour derived
from the scenario inputs.

Usage:
    python verify_run_fleetrouter.py <run_folder>

Example:
    python verify_run_fleetrouter.py /home/wojciech/SoftwareRequirements/Runs/run-28-04-2026-FleetRouter-REQ2-Claude-1

The script looks for output folders inside the run folder:
    <run_folder>/output-FleetRouter-ScenarioA
    <run_folder>/output-FleetRouter-ScenarioB
    <run_folder>/output-FleetRouter-ScenarioC

And compares them against the reference scenario inputs located at:
    <repo_root>/Verification/FleetRouter-ScenarioA
    <repo_root>/Verification/FleetRouter-ScenarioB
    <repo_root>/Verification/FleetRouter-ScenarioC

Test points (14):
    Scenario A (happy path + routing):
      1  - Three output files exist with correct headers and formats
      10 - Routes start/end at depot, stop numbering from 1
      11 - Correct arrival/waiting/departure computation anchored at 08:00
      12 - summary.csv has a row for every vehicle; stops_order grouped per vehicle
    Scenario B (validation + undeliverable classification):
      2  - Unknown destination_id excluded
      3  - Invalid time window → TIME_WINDOW
      4  - Missing distance entry → UNREACHABLE
      5  - Over weight → CAPACITY_WEIGHT
      6  - Over volume → CAPACITY_VOLUME
      7  - Exceeding 8 h driver time → MAX_DRIVER_TIME
      8  - No vehicle available → NO_VEHICLE
      9  - Exactly one reason per undeliverable package; package set completeness
    Scenario C (optimisation + priority):
      13 - Minimise total distance (primary), then total duration (secondary)
      14 - Priority package assigned before non-priority when capacity forces a choice
"""

import csv
import re
import sys
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
VERIFICATION_DIR = REPO_ROOT / "Verification"

SCENARIOS = ["ScenarioA", "ScenarioB", "ScenarioC"]

EXPECTED_HEADERS = {
    "stops_order.csv": [
        "route_id", "vehicle_id", "stop_position_in_order",
        "location_id", "delivery_package_id", "arrival_time", "departure_time",
    ],
    "undeliverable.csv": ["package_id", "reason"],
    "summary.csv": [
        "vehicle_id", "total_distance_km", "total_time_min", "packages_delivered",
    ],
}

# Some implementations use "delivered_id" instead of "delivery_package_id"
STOPS_ORDER_PKG_COL_ALIASES = {"delivery_package_id", "delivered_id"}

VALID_REASONS = {
    "CAPACITY_WEIGHT", "CAPACITY_VOLUME", "TIME_WINDOW",
    "MAX_DRIVER_TIME", "NO_VEHICLE", "UNREACHABLE",
}

DEPOT_START_TIME = "08:00"
MAX_DRIVER_MINUTES = 480  # 8 hours

HH_MM_RE = re.compile(r"^\d{1,2}:\d{2}$")

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


def hhmm_to_minutes(val: str) -> int | None:
    """Parse HH:MM string to total minutes since midnight.  Returns None on failure."""
    val = val.strip()
    m = HH_MM_RE.match(val)
    if not m:
        return None
    parts = val.split(":")
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        return None


def minutes_to_hhmm(mins: int) -> str:
    h = mins // 60
    m = mins % 60
    return f"{h:02d}:{m:02d}"


def to_float(value: str) -> float | None:
    try:
        return float(value.strip())
    except (ValueError, AttributeError):
        return None


def to_int(value: str) -> int | None:
    try:
        return int(value.strip())
    except (ValueError, AttributeError):
        # Also try float -> int for values like "105.0"
        try:
            f = float(value.strip())
            if f == int(f):
                return int(f)
        except (ValueError, AttributeError):
            pass
        return None


def near_float(a: float, b: float, tol: float = 0.01) -> bool:
    return abs(a - b) <= tol


def ok(msg: str):
    print(f"  ✓  {msg}")


def fail(msg: str, detail: str = ""):
    print(f"  ✗  {msg}")
    if detail:
        print(f"       → {detail}")


def normalize_header(cols: list[str]) -> list[str]:
    return [c.strip().lower() for c in cols]


def find_pkg_col(headers: list[str]) -> str | None:
    """Find the package ID column in stops_order.csv, tolerating aliases."""
    for h in headers:
        if h.strip().lower() in {a.lower() for a in STOPS_ORDER_PKG_COL_ALIASES}:
            return h.strip()
    return None


# ── Load scenario input data ─────────────────────────────────────────────────


def load_distances(scenario_dir: Path) -> dict[tuple[str, str], tuple[float, int]]:
    """Return {(from, to): (distance_km, travel_time_min)}."""
    rows = read_csv(scenario_dir / "distances.csv")
    d = {}
    for r in rows:
        fr = r["from_location_id"]
        to = r["to_location_id"]
        dist = float(r["distance_km"])
        ttime = int(float(r["travel_time_min"]))
        d[(fr, to)] = (dist, ttime)
    return d


def load_packages(scenario_dir: Path) -> list[dict]:
    return read_csv(scenario_dir / "packages.csv")


def load_vehicles(scenario_dir: Path) -> list[dict]:
    return read_csv(scenario_dir / "vehicles.csv")


def load_locations(scenario_dir: Path) -> set[str]:
    rows = read_csv(scenario_dir / "locations.csv")
    return {r["location_id"] for r in rows}


# ── Structure checks (Level 2) ────────────────────────────────────────────────


def check_structure(output_dir: Path) -> int:
    """Verify file existence, headers, non-empty data, format constraints.
    Returns number of failures."""
    failures = 0
    print("\n  [Structure checks]")

    for fname, expected_cols in EXPECTED_HEADERS.items():
        fpath = output_dir / fname

        # ── File existence ──
        if not fpath.exists():
            fail(f"{fname} exists", "File not found")
            failures += 1
            continue
        ok(f"{fname} exists")

        rows = read_csv(fpath)

        # ── Non-empty ──
        # undeliverable.csv may legitimately be empty (header only) when all packages are delivered
        if not rows:
            if fname == "undeliverable.csv":
                ok(f"{fname} exists (empty — all packages delivered)")
                continue
            else:
                fail(f"{fname} has data rows", "File exists but contains no data rows")
                failures += 1
                continue
        ok(f"{fname} has data rows ({len(rows)})")

        # ── Header ──
        actual_cols = normalize_header(list(rows[0].keys()))

        # For stops_order.csv tolerate delivered_id / delivery_package_id
        if fname == "stops_order.csv":
            expected_norm = [c.lower() for c in expected_cols]
            match = True
            for ec in expected_norm:
                if ec in actual_cols:
                    continue
                # Check alias
                if ec == "delivery_package_id" and any(
                    a in {al.lower() for al in STOPS_ORDER_PKG_COL_ALIASES}
                    for a in actual_cols
                ):
                    continue
                match = False
                break
            if match and len(actual_cols) >= len(expected_norm):
                ok(f"{fname} header correct")
            else:
                fail(f"{fname} header", f"expected {expected_cols}, got {list(rows[0].keys())}")
                failures += 1
        else:
            expected_norm = [c.lower() for c in expected_cols]
            if actual_cols == expected_norm:
                ok(f"{fname} header correct")
            else:
                fail(f"{fname} header", f"expected {expected_cols}, got {list(rows[0].keys())}")
                failures += 1

        # ── No fully-empty rows ──
        empty = [i + 2 for i, r in enumerate(rows) if all(v.strip() == "" for v in r.values())]
        if empty:
            fail(f"{fname} no empty rows", f"empty at lines: {empty}")
            failures += 1
        else:
            ok(f"{fname} no empty rows")

        # ── Format-specific checks ──
        if fname == "stops_order.csv":
            # arrival_time and departure_time must be HH:MM
            bad_time = []
            for i, r in enumerate(rows):
                for col in ("arrival_time", "departure_time"):
                    val = r.get(col, "")
                    if val and not HH_MM_RE.match(val.strip()):
                        bad_time.append((i + 2, col, val))
            if bad_time:
                fail(f"{fname} time format HH:MM", f"bad values: {bad_time[:5]}")
                failures += 1
            else:
                ok(f"{fname} time format HH:MM")

        if fname == "summary.csv":
            # total_distance_km should have ≤2 decimal places
            bad_dist = []
            for i, r in enumerate(rows):
                val = r.get("total_distance_km", "")
                f_val = to_float(val)
                if f_val is None:
                    bad_dist.append((i + 2, val))
                elif "." in val and len(val.split(".")[1]) > 2:
                    bad_dist.append((i + 2, val))
            if bad_dist:
                fail(f"{fname} distance format (≤2 d.p.)", f"bad values: {bad_dist[:5]}")
                failures += 1
            else:
                ok(f"{fname} distance format (≤2 d.p.)")

            # total_time_min should be integer
            bad_tmin = []
            for i, r in enumerate(rows):
                val = r.get("total_time_min", "")
                if to_int(val) is None:
                    bad_tmin.append((i + 2, val))
            if bad_tmin:
                fail(f"{fname} total_time_min is integer", f"bad values: {bad_tmin[:5]}")
                failures += 1
            else:
                ok(f"{fname} total_time_min is integer")

        if fname == "undeliverable.csv":
            # reason must be a valid code
            bad_reason = []
            for i, r in enumerate(rows):
                reason = r.get("reason", "").strip().upper()
                if reason not in VALID_REASONS:
                    bad_reason.append((i + 2, r.get("reason", "")))
            if bad_reason:
                fail(f"{fname} valid reason codes", f"unknown: {bad_reason[:5]}")
                failures += 1
            else:
                ok(f"{fname} valid reason codes")

    return failures


# ── Scenario A checks ─────────────────────────────────────────────────────────


def check_scenario_a(output_dir: Path, scenario_dir: Path) -> int:
    """Points 1, 10, 11, 12."""
    failures = 0
    print("\n  [Scenario A – Logic checks]")

    distances = load_distances(scenario_dir)
    packages = load_packages(scenario_dir)
    vehicles = load_vehicles(scenario_dir)
    pkg_map = {p["package_id"]: p for p in packages}
    veh_map = {v["vehicle_id"]: v for v in vehicles}

    # Load outputs
    stops_path = output_dir / "stops_order.csv"
    summary_path = output_dir / "summary.csv"
    undeliv_path = output_dir / "undeliverable.csv"

    if not stops_path.exists() or not summary_path.exists():
        fail("required output files present for logic checks", "stops_order.csv or summary.csv missing")
        return 1

    stops_rows = read_csv(stops_path)
    summary_rows = read_csv(summary_path)
    undeliv_rows = read_csv(undeliv_path) if undeliv_path.exists() else []

    pkg_col = find_pkg_col(list(stops_rows[0].keys())) if stops_rows else None

    # ── Point 12: summary.csv has a row for every vehicle ──
    summary_vehicles = {r.get("vehicle_id", "").strip() for r in summary_rows}
    input_vehicles = {v["vehicle_id"] for v in vehicles}
    if input_vehicles <= summary_vehicles:
        ok("Point 12: summary.csv contains all vehicles from input")
    else:
        missing = input_vehicles - summary_vehicles
        fail("Point 12: summary.csv contains all vehicles", f"missing: {missing}")
        failures += 1

    # ── Point 10: routes start/end at depot, numbering from 1 ──
    # Group stops by vehicle
    vehicle_stops: dict[str, list[dict]] = {}
    for r in stops_rows:
        vid = r.get("vehicle_id", "").strip()
        vehicle_stops.setdefault(vid, []).append(r)

    point10_ok = True
    for vid, stops in vehicle_stops.items():
        depot = veh_map.get(vid, {}).get("depot_location_id", "")
        # Sort by stop_position
        try:
            stops_sorted = sorted(stops, key=lambda s: int(s.get("stop_position_in_order", "0")))
        except ValueError:
            stops_sorted = stops

        # Check numbering starts at 1
        positions = [to_int(s.get("stop_position_in_order", "")) for s in stops_sorted]
        if positions and positions[0] != 1:
            fail(f"Point 10: vehicle {vid} stop numbering starts at 1", f"first position: {positions[0]}")
            failures += 1
            point10_ok = False

        # Check consecutive numbering
        if positions and all(p is not None for p in positions):
            expected_positions = list(range(1, len(positions) + 1))
            if positions != expected_positions:
                fail(f"Point 10: vehicle {vid} consecutive stop numbering",
                     f"got {positions}, expected {expected_positions}")
                failures += 1
                point10_ok = False

    if point10_ok:
        ok("Point 10: stop numbering starts at 1 and is consecutive for all vehicles")

    # ── Point 11: arrival/waiting/departure computation ──
    point11_ok = True
    for vid, stops in vehicle_stops.items():
        depot = veh_map.get(vid, {}).get("depot_location_id", "")
        try:
            stops_sorted = sorted(stops, key=lambda s: int(s.get("stop_position_in_order", "0")))
        except ValueError:
            stops_sorted = stops

        current_time = hhmm_to_minutes(DEPOT_START_TIME)  # 480 = 08:00
        prev_loc = depot

        for s in stops_sorted:
            loc = s.get("location_id", "").strip()
            arr_str = s.get("arrival_time", "").strip()
            dep_str = s.get("departure_time", "").strip()
            arr_min = hhmm_to_minutes(arr_str)
            dep_min = hhmm_to_minutes(dep_str)

            if arr_min is None or dep_min is None:
                # Already caught by structure checks
                continue

            # Expected arrival = prev departure + travel time
            key = (prev_loc, loc)
            if key not in distances:
                fail(f"Point 11: distance entry for {prev_loc}→{loc}", "missing in input")
                failures += 1
                point11_ok = False
                break

            _, travel = distances[key]
            expected_arr = current_time + travel

            if arr_min != expected_arr:
                fail(f"Point 11: vehicle {vid} arrival at {loc}",
                     f"expected {minutes_to_hhmm(expected_arr)}, got {arr_str}")
                failures += 1
                point11_ok = False

            # Determine package for this stop to get tw_open and service_min
            pkg_id_val = s.get(pkg_col, "") if pkg_col else ""
            pkg_id_val = pkg_id_val.strip()
            pkg = pkg_map.get(pkg_id_val)

            if pkg:
                tw_open = hhmm_to_minutes(pkg["tw_open"])
                service = int(pkg["service_min"])

                # If arrival before tw_open, must wait
                effective_start = max(arr_min, tw_open) if tw_open is not None else arr_min
                expected_dep = effective_start + service

                if dep_min != expected_dep:
                    fail(f"Point 11: vehicle {vid} departure from {loc}",
                         f"expected {minutes_to_hhmm(expected_dep)}, got {dep_str}")
                    failures += 1
                    point11_ok = False

                current_time = dep_min
            else:
                current_time = dep_min

            prev_loc = loc

    if point11_ok:
        ok("Point 11: arrival/waiting/departure computations correct (anchored at 08:00)")

    # ── Point 12 continued: stops grouped per vehicle ──
    # Check that stops_order rows are grouped by vehicle (all stops for a vehicle contiguous)
    seen_vehicles = []
    prev_vid = None
    grouped_ok = True
    for r in stops_rows:
        vid = r.get("vehicle_id", "").strip()
        if vid != prev_vid:
            if vid in seen_vehicles:
                fail("Point 12: stops_order grouped by vehicle",
                     f"vehicle {vid} appears in non-contiguous blocks")
                failures += 1
                grouped_ok = False
                break
            seen_vehicles.append(vid)
            prev_vid = vid
    if grouped_ok:
        ok("Point 12: stops_order rows grouped per vehicle")

    # ── Point 1: all packages accounted for ──
    delivered_ids = set()
    for r in stops_rows:
        pid = r.get(pkg_col, "").strip() if pkg_col else ""
        if pid:
            delivered_ids.add(pid)
    undeliv_ids = {r.get("package_id", "").strip() for r in undeliv_rows}
    input_ids = {p["package_id"] for p in packages}

    accounted = delivered_ids | undeliv_ids
    if accounted == input_ids:
        ok("Point 1: every input package is either delivered or in undeliverable")
    else:
        missing_pkgs = input_ids - accounted
        extra_pkgs = accounted - input_ids
        detail = ""
        if missing_pkgs:
            detail += f"missing: {missing_pkgs} "
        if extra_pkgs:
            detail += f"extra: {extra_pkgs}"
        fail("Point 1: package set completeness", detail)
        failures += 1

    return failures


# ── Scenario B checks ─────────────────────────────────────────────────────────


def check_scenario_b(output_dir: Path, scenario_dir: Path) -> int:
    """Points 2, 3, 4, 5, 6, 7, 8, 9."""
    failures = 0
    print("\n  [Scenario B – Logic checks]")

    packages = load_packages(scenario_dir)
    locations = load_locations(scenario_dir)
    vehicles = load_vehicles(scenario_dir)
    distances = load_distances(scenario_dir)

    undeliv_path = output_dir / "undeliverable.csv"
    stops_path = output_dir / "stops_order.csv"

    undeliv_rows = read_csv(undeliv_path) if undeliv_path.exists() else []
    stops_rows = read_csv(stops_path) if stops_path.exists() else []

    # Build lookup: package_id -> reason
    undeliv_map: dict[str, str] = {}
    for r in undeliv_rows:
        pid = r.get("package_id", "").strip()
        reason = r.get("reason", "").strip().upper()
        undeliv_map[pid] = reason

    # Delivered package IDs
    delivered_ids = set()
    if stops_rows:
        pkg_col = find_pkg_col(list(stops_rows[0].keys()))
        for r in stops_rows:
            pid = r.get(pkg_col, "").strip() if pkg_col else ""
            if pid:
                delivered_ids.add(pid)

    # ── Expected classifications based on our scenario design ──
    # P_BADLOC  → excluded (L5 not in locations.csv) — should NOT appear anywhere
    # P_BADTW   → TIME_WINDOW
    # P_UNREACH → UNREACHABLE
    # P_WEIGHT  → CAPACITY_WEIGHT
    # P_VOLUME  → CAPACITY_VOLUME
    # P_MAXTIME → MAX_DRIVER_TIME
    # P_NOVEH   → NO_VEHICLE
    # P_OK      → delivered

    expected_undeliv = {
        "P_BADTW":   "TIME_WINDOW",
        "P_UNREACH": "UNREACHABLE",
        "P_WEIGHT":  "CAPACITY_WEIGHT",
        "P_VOLUME":  "CAPACITY_VOLUME",
        "P_MAXTIME": "MAX_DRIVER_TIME",
        "P_NOVEH":   "NO_VEHICLE",
    }

    # ── Point 2: P_BADLOC excluded from processing ──
    # P_BADLOC should NOT be in stops_order or undeliverable
    # (it references L5 which doesn't exist in locations.csv)
    # However some implementations may record it in undeliverable — we accept that too,
    # but it must NOT be delivered.
    if "P_BADLOC" in delivered_ids:
        fail("Point 2: P_BADLOC (unknown location) excluded from delivery",
             "found in delivered packages")
        failures += 1
    else:
        ok("Point 2: P_BADLOC (unknown location) not delivered")

    # ── Points 3–8: correct reason codes ──
    point_map = {
        "P_BADTW":   (3,  "TIME_WINDOW"),
        "P_UNREACH": (4,  "UNREACHABLE"),
        "P_WEIGHT":  (5,  "CAPACITY_WEIGHT"),
        "P_VOLUME":  (6,  "CAPACITY_VOLUME"),
        "P_MAXTIME": (7,  "MAX_DRIVER_TIME"),
        "P_NOVEH":   (8,  "NO_VEHICLE"),
    }

    for pkg_id, (point_num, expected_reason) in point_map.items():
        actual_reason = undeliv_map.get(pkg_id)
        if actual_reason is None:
            # Check if it was delivered (wrong)
            if pkg_id in delivered_ids:
                fail(f"Point {point_num}: {pkg_id} → {expected_reason}",
                     "package was delivered instead of being undeliverable")
            else:
                fail(f"Point {point_num}: {pkg_id} → {expected_reason}",
                     "package not found in undeliverable.csv")
            failures += 1
        elif actual_reason == expected_reason:
            ok(f"Point {point_num}: {pkg_id} → {expected_reason}")
        else:
            fail(f"Point {point_num}: {pkg_id} → {expected_reason}",
                 f"got reason: {actual_reason}")
            failures += 1

    # ── Point 8 (continued): P_OK should be delivered ──
    if "P_OK" in delivered_ids:
        ok("Point 8 (complement): P_OK is delivered")
    elif "P_OK" in undeliv_map:
        fail("Point 8 (complement): P_OK should be delivered",
             f"found in undeliverable with reason: {undeliv_map['P_OK']}")
        failures += 1
    else:
        fail("Point 8 (complement): P_OK should be delivered",
             "not found in any output")
        failures += 1

    # ── Point 9: exactly one reason per undeliverable; no duplicates ──
    pid_counts: dict[str, int] = {}
    for r in undeliv_rows:
        pid = r.get("package_id", "").strip()
        pid_counts[pid] = pid_counts.get(pid, 0) + 1

    duplicates = {pid: cnt for pid, cnt in pid_counts.items() if cnt > 1}
    if duplicates:
        fail("Point 9: no duplicate package_id in undeliverable.csv",
             f"duplicates: {duplicates}")
        failures += 1
    else:
        ok("Point 9: each package appears at most once in undeliverable.csv")

    # Check no package is both delivered and undeliverable
    both = delivered_ids & set(undeliv_map.keys())
    if both:
        fail("Point 9: no package both delivered and undeliverable",
             f"found in both: {both}")
        failures += 1
    else:
        ok("Point 9: no package in both delivered and undeliverable sets")

    return failures


# ── Scenario C checks ─────────────────────────────────────────────────────────


def check_scenario_c(output_dir: Path, scenario_dir: Path) -> int:
    """Points 13, 14."""
    failures = 0
    print("\n  [Scenario C – Logic checks]")

    packages = load_packages(scenario_dir)
    vehicles = load_vehicles(scenario_dir)
    distances = load_distances(scenario_dir)

    stops_path = output_dir / "stops_order.csv"
    summary_path = output_dir / "summary.csv"
    undeliv_path = output_dir / "undeliverable.csv"

    stops_rows = read_csv(stops_path) if stops_path.exists() else []
    summary_rows = read_csv(summary_path) if summary_path.exists() else []
    undeliv_rows = read_csv(undeliv_path) if undeliv_path.exists() else []

    delivered_ids = set()
    if stops_rows:
        pkg_col = find_pkg_col(list(stops_rows[0].keys()))
        for r in stops_rows:
            pid = r.get(pkg_col, "").strip() if pkg_col else ""
            if pid:
                delivered_ids.add(pid)

    undeliv_ids = {r.get("package_id", "").strip() for r in undeliv_rows}

    # ── Point 14: priority package assigned, non-priority dropped ──
    # P_PRI (priority=1, 20kg) + P_NOPRI (priority=0, 20kg) cannot both fit in V1 (30kg)
    # P_PRI must be assigned; P_NOPRI must be undeliverable
    if "P_PRI" in delivered_ids:
        ok("Point 14: priority package P_PRI is delivered")
    else:
        fail("Point 14: priority package P_PRI should be delivered",
             "not found in delivered packages")
        failures += 1

    if "P_NOPRI" in undeliv_ids:
        ok("Point 14: non-priority P_NOPRI is undeliverable (correct)")
    elif "P_NOPRI" in delivered_ids:
        # Both delivered? Check if capacity is violated
        fail("Point 14: P_NOPRI should be undeliverable",
             "package was delivered (capacity should prevent both)")
        failures += 1
    else:
        fail("Point 14: P_NOPRI should be in undeliverable.csv",
             "not found in any output")
        failures += 1

    # P_SMALL should be delivered alongside P_PRI (20+8=28 ≤ 30 kg, 2.5+1.0=3.5 ≤ 4.0 m³)
    if "P_SMALL" in delivered_ids:
        ok("Point 14: P_SMALL delivered alongside P_PRI")
    else:
        fail("Point 14: P_SMALL should be delivered",
             "not found in delivered packages")
        failures += 1

    # ── Point 13: optimisation – minimise distance, then duration ──
    # With P_PRI (→L1) and P_SMALL (→L3), two orderings:
    #   L0→L1→L3→L0: 10.00 + 8.00 + 22.00 = 40.00 km,  time: 97 min (travel only)
    #     detailed: dep 08:00 → L1 arr 08:20, dep 08:35 → L3 arr 08:50, dep 09:00 → L0 arr 09:44
    #     total_time = 104 min
    #   L0→L3→L1→L0: 20.00 + 9.00 + 11.00 = 40.00 km,  time:
    #     dep 08:00 → L3 arr 08:40, dep 08:50 → L1 arr 08:50+18=09:08, dep 09:23 → L0 arr 09:45
    #     total_time = 105 min
    # Both have 40.00 km distance → tie-break on duration: 104 < 105 → first route wins
    #
    # Expected optimal: L0→L1→L3→L0, distance=40.00, time=104 min

    expected_distance = 40.00
    expected_time_best = 104  # L0→L1→L3→L0

    if summary_rows:
        v1_summary = None
        for r in summary_rows:
            if r.get("vehicle_id", "").strip() == "V1":
                v1_summary = r
                break

        if v1_summary:
            actual_dist = to_float(v1_summary.get("total_distance_km", ""))
            actual_time = to_int(v1_summary.get("total_time_min", ""))

            # Check distance optimality
            if actual_dist is not None and near_float(actual_dist, expected_distance):
                ok(f"Point 13: V1 total distance = {actual_dist:.2f} km (optimal: {expected_distance:.2f})")
            elif actual_dist is not None:
                # Distance should at most be the worse option
                fail(f"Point 13: V1 total distance optimal",
                     f"expected ≈{expected_distance:.2f}, got {actual_dist:.2f}")
                failures += 1
            else:
                fail("Point 13: V1 total_distance_km is numeric", "could not parse")
                failures += 1

            # Check tie-breaking on duration
            if actual_time is not None and actual_time == expected_time_best:
                ok(f"Point 13: V1 total time = {actual_time} min (tie-break optimal: {expected_time_best})")
            elif actual_time is not None:
                # Accept if distance is correct but time is slightly off (other valid route)
                if actual_dist is not None and near_float(actual_dist, expected_distance):
                    fail(f"Point 13: tie-break on duration",
                         f"expected {expected_time_best} min, got {actual_time} min")
                    failures += 1
                else:
                    fail(f"Point 13: V1 total_time_min",
                         f"expected {expected_time_best}, got {actual_time}")
                    failures += 1
            else:
                fail("Point 13: V1 total_time_min is numeric", "could not parse")
                failures += 1

            # Verify route order: should be L1 then L3
            v1_stops = [r for r in stops_rows if r.get("vehicle_id", "").strip() == "V1"]
            if v1_stops:
                try:
                    v1_sorted = sorted(v1_stops, key=lambda s: int(s.get("stop_position_in_order", "0")))
                    locs = [s.get("location_id", "").strip() for s in v1_sorted]
                    if locs == ["L1", "L3"]:
                        ok("Point 13: V1 route order L1→L3 (distance-optimal with best tie-break)")
                    elif locs == ["L3", "L1"]:
                        fail("Point 13: V1 route order",
                             "got L3→L1 (same distance but worse duration tie-break)")
                        failures += 1
                    else:
                        fail("Point 13: V1 route order", f"expected [L1, L3], got {locs}")
                        failures += 1
                except ValueError:
                    fail("Point 13: V1 stop positions parseable", "could not sort by position")
                    failures += 1
        else:
            fail("Point 13: V1 found in summary.csv", "vehicle V1 not found")
            failures += 1
    else:
        fail("Point 13: summary.csv has data", "empty or missing")
        failures += 1

    return failures


# ── CSV output ────────────────────────────────────────────────────────────────


def write_csv(run_dir: Path, scenario_results: dict) -> None:
    csv_path = REPO_ROOT / "Results" / "FleetRouter-functional.csv"
    header = ["Run", "ScenarioA", "ScenarioB", "ScenarioC", "Total failures"]
    total = sum(v for v in scenario_results.values() if isinstance(v, int))
    row = [run_dir.name]
    for s in SCENARIOS:
        f = scenario_results.get(s)
        row.append("" if f is None else f)
    row.append(total)

    write_header = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if write_header:
            writer.writerow(header)
        writer.writerow(row)
    print(f"\nSaved results to {csv_path}")


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    if len(sys.argv) != 2:
        print("Usage:   python verify_run_fleetrouter.py <run_folder>")
        print("Example: python verify_run_fleetrouter.py Runs/run-28-04-2026-FleetRouter-REQ2-Claude-1")
        sys.exit(1)

    run_dir = Path(sys.argv[1]).resolve()
    if not run_dir.exists():
        print(f"Error: run folder not found: {run_dir}")
        sys.exit(1)

    print(f"Run: {run_dir.name}")

    total_failures = 0
    scenarios_checked = 0
    scenario_results: dict = {}

    scenario_checkers = {
        "ScenarioA": check_scenario_a,
        "ScenarioB": check_scenario_b,
        "ScenarioC": check_scenario_c,
    }

    for scenario_name in SCENARIOS:
        output_dir = run_dir / f"output-FleetRouter-{scenario_name}"
        scenario_dir = VERIFICATION_DIR / f"FleetRouter-{scenario_name}"

        # Skip silently if both sides are missing
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

        struct_failures = check_structure(output_dir)
        logic_failures = scenario_checkers[scenario_name](output_dir, scenario_dir)
        failures = struct_failures + logic_failures

        print(f"\n  Result: {'PASS' if failures == 0 else f'FAIL  ({failures} check(s) failed)'}")
        total_failures += failures
        scenarios_checked += 1
        scenario_results[scenario_name] = failures

    print(f"\n{'=' * 60}")
    if scenarios_checked == 0:
        print("No scenarios found. Make sure output-FleetRouter-ScenarioX folders exist.")
    elif total_failures == 0:
        print(f"ALL CHECKS PASSED  ({scenarios_checked} scenario(s))")
    else:
        print(f"FAILED  ({total_failures} total failure(s) across {scenarios_checked} scenario(s))")
    print(f"{'=' * 60}")

    write_csv(run_dir, scenario_results)

    sys.exit(0 if total_failures == 0 else 1)


if __name__ == "__main__":
    main()