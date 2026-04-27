"""Command-line interface for the Copilot ADAS simulator."""
import argparse
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CliArgs:
    input: Path
    output: Path


def parse_args() -> CliArgs:
    """Parse and validate command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="copilot",
        description=(
            "Copilot ADAS Simulator — processes sensor and driver-event logs "
            "and writes autonomous-driving decision outputs."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  python main.py --input ./data/input --output ./data/output"
        ),
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        metavar="<dir>",
        help="Directory containing sensor_log.csv and driver_events.csv",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        metavar="<dir>",
        help="Directory where state_log.csv, commands_log.csv and feature_decision.csv are written",
    )
    ns = parser.parse_args()
    return CliArgs(input=ns.input, output=ns.output)
