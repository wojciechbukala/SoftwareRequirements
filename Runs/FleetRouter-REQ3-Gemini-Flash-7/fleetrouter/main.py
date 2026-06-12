import argparse
import os
import sys
import csv
from datetime import datetime, time, timedelta
from typing import List, Dict, Tuple, Set, Optional

from fleetrouter.models import (
    Package, Vehicle, Location, Distance, Stop, Route,
    DEPOT_DEPARTURE_TIME, MAX_DRIVER_WORKING_TIME, TIME_FORMAT
)
from fleetrouter.utils import (
    read_packages_csv, read_vehicles_csv, read_locations_csv,
    read_distances_csv, check_file_exists, parse_time_str,
    time_to_total_minutes, total_minutes_to_time, DistanceGraph
)

class UndeliverableReason:
    CAPACITY_WEIGHT = "CAPACITY_WEIGHT"
    CAPACITY_VOLUME = "CAPACITY_VOLUME"
    TIME_WINDOW = "TIME_WINDOW"
    MAX_DRIVER_TIME = "MAX_DRIVER_TIME"
    NO_VEHICLE = "NO_VEHICLE"
    UNREACHABLE = "UNREACHABLE"
    INVALID_INPUT = "INVALID_INPUT" # For packages with invalid priority or time windows

@dataclass
class UndeliverablePackage:
    package_id: str
    reason: str

def validate_initial_data(
    packages: List[Package],
    vehicles: List[Vehicle],
    locations: Dict[str, Location],
    all_undeliverable_packages: List[UndeliverablePackage]
) -> Tuple[List[Package], List[Vehicle]]:
    """
    Performs initial data validation as per FR-02.
    - Verifies location IDs for packages and vehicles.
    - Verifies package time windows.
    Returns filtered packages and vehicles.
    """
    valid_location_ids = set(locations.keys())
    
    # Validate packages
    processed_packages = []
    for pkg in packages:
        is_valid = True
        
        # Check destination_id
        if pkg.destination_id not in valid_location_ids:
            all_undeliverable_packages.append(UndeliverablePackage(pkg.id, UndeliverableReason.INVALID_INPUT))
            print(f"Warning: Package {pkg.id} references unknown location ID {pkg.destination_id}. Excluded from processing.", file=sys.stderr)
            is_valid = False
        
        # Check time window
        if pkg.tw_open >= pkg.tw_close:
            all_undeliverable_packages.append(UndeliverablePackage(pkg.id, UndeliverableReason.TIME_WINDOW))
            print(f"Warning: Package {pkg.id} has invalid time window ({pkg.tw_open}-{pkg.tw_close}). Excluded from processing.", file=sys.stderr)
            is_valid = False
        
        # Check priority value
        if pkg.priority not in [0, 1]:
            all_undeliverable_packages.append(UndeliverablePackage(pkg.id, UndeliverableReason.INVALID_INPUT))
            print(f"Warning: Package {pkg.id} has invalid priority value ({pkg.priority}). Excluded from processing.", file=sys.stderr)
            is_valid = False

        if is_valid:
            processed_packages.append(pkg)

    # Validate vehicles
    processed_vehicles = []
    for vehicle in vehicles:
        if vehicle.depot_location_id not in valid_location_ids:
            # Note: The requirement FR-02 does not explicitly state to add invalid vehicles
            # to undeliverable.csv, but rather "reported and excluded from processing".
            # For consistency, we'll treat it similarly to a package.
            print(f"Warning: Vehicle {vehicle.id} references unknown depot location ID {vehicle.depot_location_id}. Excluded from processing.", file=sys.stderr)
            # We don't add vehicles to undeliverable_packages as it's for packages.
        else:
            processed_vehicles.append(vehicle)

    return processed_packages, processed_vehicles


class VRPSolver:
    def __init__(self, packages: List[Package], vehicles: List[Vehicle], 
                 locations: Dict[str, Location], distances_data: Dict[Tuple[str, str], Distance],
                 all_undeliverable_packages: List[UndeliverablePackage]):
        self.packages = packages
        self.vehicles = vehicles
        self.locations = locations
        self.all_undeliverable_packages = all_undeliverable_packages

        all_location_ids = set(locations.keys())
        for pkg in packages:
            all_location_ids.add(pkg.destination_id)
        for veh in vehicles:
            all_location_ids.add(veh.depot_location_id)

        self.distance_graph = DistanceGraph(distances_data, all_location_ids)
        self.routes: Dict[str, Route] = {vehicle.id: Route(vehicle_id=vehicle.id) for vehicle in vehicles}
        self.assigned_packages: Set[str] = set()
        
        # Cache for shortest paths to avoid recomputing
        self.shortest_path_cache: Dict[Tuple[str, str], Tuple[List[str], float, int]] = {}
        # Packages sorted by priority (1 first), then ID for deterministic behavior.
        # This will be consumed by the greedy algorithm.
        self.unassigned_packages = sorted(self.packages, key=lambda p: (p.priority, p.id), reverse=True)


    def _get_shortest_path(self, from_loc_id: str, to_loc_id: str) -> Optional[Tuple[List[str], float, int]]:
        if (from_loc_id, to_loc_id) in self.shortest_path_cache:
            return self.shortest_path_cache[(from_loc_id, to_loc_id)]
        
        path_info = self.distance_graph.find_shortest_path(from_loc_id, to_loc_id)
        if path_info:
            self.shortest_path_cache[(from_loc_id, to_loc_id)] = path_info
        return path_info

    def _calculate_route_metrics(self, vehicle: Vehicle, stops_sequence: List[Tuple[Location, Package]]) -> Optional[Tuple[float, int, List[Stop], float, float]]:
        """
        Calculates the total distance, total time, and detailed stops for a given sequence of locations/packages.
        Also returns current_weight and current_volume for capacity checks.
        Returns (total_distance_km, total_time_min, list_of_stop_objects, current_weight, current_volume) or None if infeasible/unreachable.
        """
        current_distance_km = 0.0
        current_time_min_total = 0 # This will track cumulative time considering travel, wait, service
        current_location_id = vehicle.depot_location_id
        
        # All vehicles depart at 08:00
        current_departure_time_minutes = time_to_total_minutes(DEPOT_DEPARTURE_TIME)

        calculated_stops: List[Stop] = []
        current_weight = 0.0
        current_volume = 0.0

        for i, (stop_location, package_to_deliver) in enumerate(stops_sequence):
            path_info = self._get_shortest_path(current_location_id, stop_location.id)
            if not path_info:
                # If any segment is unreachable, the route is infeasible
                # print(f"Debug: Unreachable path {current_location_id} -> {stop_location.id}")
                self.all_undeliverable_packages.append(UndeliverablePackage(package_to_deliver.id, UndeliverableReason.UNREACHABLE))
                return None

            path_list, travel_dist, travel_time = path_info
            
            current_distance_km += travel_dist
            
            arrival_time_min = current_departure_time_minutes + travel_time
            
            # Waiting time if arrival is before package's time window open
            package_tw_open_min = time_to_total_minutes(package_to_deliver.tw_open)
            waiting_time_min = max(0, package_tw_open_min - arrival_time_min)
            
            arrival_time_min_actual = arrival_time_min + waiting_time_min
            departure_time_min = arrival_time_min_actual + package_to_deliver.service_min

            # Check package time window closing time
            package_tw_close_min = time_to_total_minutes(package_to_deliver.tw_close)
            if departure_time_min > package_tw_close_min:
                # print(f"Debug: Package {package_to_deliver.id} exceeds time window at {stop_location.id}")
                self.all_undeliverable_packages.append(UndeliverablePackage(package_to_deliver.id, UndeliverableReason.TIME_WINDOW))
                return None # Infeasible due to time window

            # Check driver max working time
            # Max working time is 8 hours (480 minutes) from 08:00
            if (departure_time_min - time_to_total_minutes(DEPOT_DEPARTURE_TIME)) > MAX_DRIVER_WORKING_TIME.total_seconds() / 60:
                # print(f"Debug: Package {package_to_deliver.id} exceeds driver working time at {stop_location.id}")
                self.all_undeliverable_packages.append(UndeliverablePackage(package_to_deliver.id, UndeliverableReason.MAX_DRIVER_TIME))
                return None # Infeasible due to max driver time
            
            current_weight += package_to_deliver.weight_kg
            current_volume += package_to_deliver.volume_m3

            # Create a Stop object
            calculated_stops.append(Stop(
                route_id=vehicle.id, # Route ID is vehicle ID
                vehicle_id=vehicle.id,
                stop_position_in_order=i + 1, # 1-based index after depot
                location_id=stop_location.id,
                delivery_package_id=package_to_deliver.id,
                arrival_time=total_minutes_to_time(arrival_time_min_actual),
                departure_time=total_minutes_to_time(departure_time_min)
            ))
            current_location_id = stop_location.id
            current_departure_time_minutes = departure_time_min
            current_time_min_total = current_departure_time_minutes - time_to_total_minutes(DEPOT_DEPARTURE_TIME) # Accumulate time relative to start

        # Finally, return to depot calculation
        path_to_depot_info = self._get_shortest_path(current_location_id, vehicle.depot_location_id)
        if not path_to_depot_info:
            # print(f"Debug: Cannot return to depot from {current_location_id} for vehicle {vehicle.id}")
            # If the vehicle has packages, these packages become undeliverable due to unreachable return path
            for stop in calculated_stops:
                self.all_undeliverable_packages.append(UndeliverablePackage(stop.delivery_package_id, UndeliverableReason.UNREACHABLE))
            return None # Cannot return to depot
        
        depot_path_list, depot_travel_dist, depot_travel_time = depot_path_info
        final_distance_km = current_distance_km + depot_travel_dist
        final_total_route_time_min = (current_departure_time_minutes - time_to_total_minutes(DEPOT_DEPARTURE_TIME)) + depot_travel_time
        
        # Final check for driver max working time including return to depot
        if final_total_route_time_min > MAX_DRIVER_WORKING_TIME.total_seconds() / 60:
            # print(f"Debug: Route exceeds total driver working time including return to depot for vehicle {vehicle.id}")
            # If the vehicle has packages, these packages become undeliverable due to max driver time
            for stop in calculated_stops:
                self.all_undeliverable_packages.append(UndeliverablePackage(stop.delivery_package_id, UndeliverableReason.MAX_DRIVER_TIME))
            return None # Infeasible due to max driver time (whole route)

        return final_distance_km, final_total_route_time_min, calculated_stops, current_weight, current_volume

    def solve(self) -> Dict[str, Route]:
        """
        Main VRP solver method using a greedy approach.
        Assigns packages to vehicles and constructs routes.
        """
        # Sort packages by priority (1 first), then by ID for deterministic behavior
        # This is already done in __init__ for self.unassigned_packages
        
        # Initialize routes with depot starts (empty stops list initially)
        for vehicle in self.vehicles:
            self.routes[vehicle.id] = Route(vehicle_id=vehicle.id)

        # Greedy assignment loop
        while self.unassigned_packages:
            best_package_for_this_iteration = None
            best_vehicle_for_package = None
            best_insertion_index = -1
            best_route_distance = float('inf')
            best_route_time = float('inf')
            best_calculated_stops: List[Stop] = []

            # Find the best package and vehicle to assign it to
            # Iterate through a copy to allow modification of self.unassigned_packages
            packages_to_consider = list(self.unassigned_packages)
            for pkg_idx, package_to_assign in enumerate(packages_to_consider):
                for vehicle in self.vehicles:
                    # Current packages in the vehicle's route. These are already assigned packages.
                    current_route_packages_in_order = []
                    for stop in self.routes[vehicle.id].stops:
                        # Find the actual package object for this stop
                        found_pkg = next((p for p in self.packages if p.id == stop.delivery_package_id), None)
                        if found_pkg:
                            current_route_packages_in_order.append(found_pkg)
                    
                    # Try inserting package at all possible positions in the route
                    # A route with N stops has N+1 possible insertion points.
                    # E.g., for stops [A, B], insertion points are [P, A, B], [A, P, B], [A, B, P]
                    for insert_pos in range(len(current_route_packages_in_order) + 1):
                        temp_route_packages_sequence = (
                            current_route_packages_in_order[:insert_pos] +
                            [package_to_assign] +
                            current_route_packages_in_order[insert_pos:]
                        )
                        
                        # Convert to (Location, Package) tuples for _calculate_route_metrics
                        stops_sequence_for_metrics = [(self.locations[p.destination_id], p) for p in temp_route_packages_sequence]

                        metrics = self._calculate_route_metrics(vehicle, stops_sequence_for_metrics)

                        if metrics:
                            new_distance, new_time, calculated_stops, new_weight, new_volume = metrics

                            # Capacity check after calculating metrics (could have done before, but _calculate_route_metrics gives us values)
                            if new_weight > vehicle.max_weight_kg:
                                # This package is undeliverable by this vehicle due to weight.
                                # No need to add to all_undeliverable_packages here,
                                # as the package will be added with NO_VEHICLE if not assigned anywhere.
                                continue
                            if new_volume > vehicle.max_volume_m3:
                                # This package is undeliverable by this vehicle due to volume.
                                continue

                            # Compare with best found so far using optimization criteria
                            if new_distance < best_route_distance or 
                               (new_distance == best_route_distance and new_time < best_route_time):
                                best_route_distance = new_distance
                                best_route_time = new_time
                                best_package_for_this_iteration = package_to_assign
                                best_vehicle_for_package = vehicle
                                best_insertion_index = insert_pos
                                best_calculated_stops = calculated_stops
            
            if best_package_for_this_iteration:
                # Assign the package to the best found vehicle and update its route
                self.assigned_packages.add(best_package_for_this_iteration.id)
                self.unassigned_packages.remove(best_package_for_this_iteration)

                vehicle_id = best_vehicle_for_package.id
                self.routes[vehicle_id].total_distance_km = best_route_distance
                self.routes[vehicle_id].total_time_min = best_route_time
                self.routes[vehicle_id].stops = best_calculated_stops
                self.routes[vehicle_id].packages_delivered = len(best_calculated_stops) # One package per stop
                
                # Re-sort remaining packages for next iteration by priority
                self.unassigned_packages.sort(key=lambda p: (p.priority, p.id), reverse=True)

            else:
                # No more packages can be assigned to any vehicle without violating constraints
                break
        
        # Mark remaining unassigned packages as undeliverable
        for pkg in self.unassigned_packages:
            if pkg.id not in self.assigned_packages and pkg.id not in [up.package_id for up in self.all_undeliverable_packages]:
                self.all_undeliverable_packages.append(UndeliverablePackage(pkg.id, UndeliverableReason.NO_VEHICLE))

        return self.routes


def write_undeliverable_csv(output_dir: str, undeliverable_packages: List[UndeliverablePackage]):
    """Writes undeliverable packages to undeliverable.csv."""
    output_path = os.path.join(output_dir, "undeliverable.csv")
    with open(output_path, mode='w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['package_id', 'reason']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for pkg in undeliverable_packages:
            writer.writerow({'package_id': pkg.package_id, 'reason': pkg.reason})

def write_summary_csv(output_dir: str, routes: Dict[str, Route], all_vehicles: List[Vehicle]):
    """Writes route summaries to summary.csv."""
    output_path = os.path.join(output_dir, "summary.csv")
    with open(output_path, mode='w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['vehicle_id', 'total_distance_km', 'total_time_min', 'packages_delivered']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for vehicle in all_vehicles:
            route = routes.get(vehicle.id)
            if route:
                writer.writerow({
                    'vehicle_id': vehicle.id,
                    'total_distance_km': round(route.total_distance_km, 2),
                    'total_time_min': route.total_time_min,
                    'packages_delivered': route.packages_delivered
                })
            else:
                # If a vehicle has no route (e.g., no packages assigned), it should still appear in summary.
                writer.writerow({
                    'vehicle_id': vehicle.id,
                    'total_distance_km': 0.0,
                    'total_time_min': 0,
                    'packages_delivered': 0
                })

def write_stops_order_csv(output_dir: str, routes: Dict[str, Route]):
    """Writes detailed stop orders to stops_order.csv."""
    output_path = os.path.join(output_dir, "stops_order.csv")
    with open(output_path, mode='w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['route_id', 'vehicle_id', 'stop_position_in_order', 'location_id', 'delivered_id', 'arrival_time', 'departure_time']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        # Sort routes by vehicle_id for deterministic output
        sorted_routes = sorted(routes.values(), key=lambda r: r.vehicle_id)

        for route in sorted_routes:
            # Sort stops by stop_position_in_order
            sorted_stops = sorted(route.stops, key=lambda s: s.stop_position_in_order)
            for stop in sorted_stops:
                writer.writerow({
                    'route_id': stop.route_id,
                    'vehicle_id': stop.vehicle_id,
                    'stop_position_in_order': stop.stop_position_in_order,
                    'location_id': stop.location_id,
                    'delivered_id': stop.delivery_package_id,
                    'arrival_time': stop.arrival_time.strftime(TIME_FORMAT),
                    'departure_time': stop.departure_time.strftime(TIME_FORMAT)
                })


def main():
    parser = argparse.ArgumentParser(description="Fleet Router: Daily route planning for courier companies.")
    parser.add_argument('--input', type=str, required=True, help="Path to the input directory containing CSV files.")
    parser.add_argument('--output', type=str, required=True, help="Path to the output directory for results.")

    args = parser.parse_args()

    input_dir = args.input
    output_dir = args.output

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Check for mandatory input files (FR-01)
    required_files = {
        "packages.csv": os.path.join(input_dir, "packages.csv"),
        "vehicles.csv": os.path.join(input_dir, "vehicles.csv"),
        "locations.csv": os.path.join(input_dir, "locations.csv"),
        "distances.csv": os.path.join(input_dir, "distances.csv"),
    }

    for name, path in required_files.items():
        if not check_file_exists(path):
            print(f"Error: Missing mandatory input file: {name}", file=sys.stderr)
            sys.exit(1)

    # Load data
    all_undeliverable_packages: List[UndeliverablePackage] = []

    raw_packages = read_packages_csv(required_files["packages.csv"])
    original_packages_count = len(raw_packages) # Store original count
    vehicles = read_vehicles_csv(required_files["vehicles.csv"])
    locations = read_locations_csv(required_files["locations.csv"])
    distances = read_distances_csv(required_files["distances.csv"])

    print(f"Loaded {len(raw_packages)} packages, {len(vehicles)} vehicles, {len(locations)} locations, {len(distances)} distances.")

    # Initial Data Validation (FR-02)
    # The validate_initial_data function will now return the *valid* packages and vehicles
    # Note: `raw_packages` and `vehicles` passed to validate_initial_data are the original ones.
    # The function returns the *filtered* valid ones, maintaining the order (packages, vehicles).
    packages, vehicles = validate_initial_data(raw_packages, vehicles, locations, all_undeliverable_packages)
    
    # At this point, `packages` and `vehicles` only contain valid entries.
    # `all_undeliverable_packages` contains packages filtered out during initial validation.

    print(f"After initial validation: {len(packages)} valid packages, {len(vehicles)} valid vehicles.")
    print(f"{len(all_undeliverable_packages)} packages/entries marked as undeliverable during initial validation.")

    # Instantiate and run the VRP Solver
    solver = VRPSolver(packages, vehicles, locations, distances, all_undeliverable_packages)
    final_routes = solver.solve()
    
    # Output Generation (FR-06)
    write_undeliverable_csv(output_dir, all_undeliverable_packages)
    write_summary_csv(output_dir, final_routes, vehicles)
    write_stops_order_csv(output_dir, final_routes)

    # Final summary line
    delivered_count = 0
    for route in final_routes.values():
        delivered_count += route.packages_delivered

    # The problem asks for "number of packages processed, delivered, recorded as undeliverable."
    # Total processed is the initial number of packages in packages.csv.
    # Delivered is from the routes.
    # Undeliverable is the count in all_undeliverable_packages.

    print(f"Processed {original_packages_count} packages, delivered {delivered_count}, undeliverable {len(all_undeliverable_packages)}.")


if __name__ == "__main__":
    main()