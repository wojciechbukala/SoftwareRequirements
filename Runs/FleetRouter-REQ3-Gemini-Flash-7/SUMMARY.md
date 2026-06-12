```
python -m fleetrouter.main --input <input_dir> --output <output_dir>
```

# Solution Summary

This agent has successfully implemented the Fleet Router system based on the `REQUIREMENTS.md` specification. The solution includes:

*   **Data Models**: Defined using `dataclasses` for clear representation of `Package`, `Vehicle`, `Location`, `Distance`, `Stop`, and `Route` entities.
*   **Data Loading and Validation**: Robust functions for reading CSV input files (`packages.csv`, `vehicles.csv`, `locations.csv`, `distances.csv`) and performing initial data validation. This includes checks for missing files, unknown location IDs, invalid time windows, and incorrect priority values. Invalid data is reported to `stderr` and excluded from processing, with reasons recorded for undeliverable packages.
*   **Distance Graph and Shortest Path**: A `DistanceGraph` class was implemented to efficiently manage location connectivity and compute shortest paths (based on travel time, then distance for tie-breaking) using Dijkstra's algorithm.
*   **VRP Solver (Greedy Heuristic)**: The core logic is encapsulated within a `VRPSolver` class, employing a greedy insertion heuristic to assign packages to vehicles and build routes.
    *   **Package Prioritization**: Packages are assigned prioritizing those with higher priority, then by ID for deterministic behavior.
    *   **Feasibility Checks**: During route construction, the system verifies vehicle capacity (weight and volume), package time windows, and total driver working time (8 hours).
    *   **Optimization Criteria**: The greedy algorithm evaluates potential package insertions to minimize the increase in total route distance, with total route duration as a secondary optimization criterion.
    *   **Unreachability Handling**: Packages whose destination is unreachable or that cannot be returned to the depot are marked as undeliverable.
*   **Output Generation**: The system produces three output CSV files (`stops_order.csv`, `summary.csv`, `undeliverable.csv`) in the specified format, providing detailed route information, vehicle summaries, and a comprehensive list of undeliverable packages with their reasons.
*   **Command-Line Interface (CLI)**: The program supports the required CLI arguments (`--input` and `--output`) and provides clear output to `stdout` and `stderr` including a final summary line.

The implementation adheres to the spirit of the requirements, focusing on a functional and algorithmically-driven solution for daily fleet routing.
