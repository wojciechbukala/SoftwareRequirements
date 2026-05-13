#!/usr/bin/env python3
"""FleetRouter - daily route planning for courier fleets."""
import sys
from csv_io import (
    read_locations, read_distances, read_packages, read_vehicles,
    write_stops_order, write_undeliverable, write_summary, _route_distance,
)
from solver import solve
from models import UndeliverableEntry


def main():
    locations = read_locations("locations.csv")
    distance_km, travel_min = read_distances("distances.csv")
    packages, skipped_ids = read_packages("packages.csv")
    vehicles = read_vehicles("vehicles.csv")

    invalid_entries = [UndeliverableEntry(pkg_id, "INVALID_INPUT") for pkg_id in skipped_ids]

    routes, undeliverable = solve(packages, vehicles, distance_km, travel_min)

    write_stops_order("stops_order.csv", routes)
    write_undeliverable("undeliverable.csv", undeliverable + invalid_entries)
    write_summary("summary.csv", routes, distance_km)


if __name__ == "__main__":
    main()
