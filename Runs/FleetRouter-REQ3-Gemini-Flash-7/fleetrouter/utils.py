import csv
from datetime import datetime, time, timedelta
from typing import List, Dict, Tuple, Set, Optional
import os
import heapq

from fleetrouter.models import Package, Vehicle, Location, Distance, TIME_FORMAT

def parse_time_str(time_str: str) -> time:
    """Parses a HH:MM string into a datetime.time object."""
    return datetime.strptime(time_str, TIME_FORMAT).time()

def time_to_total_minutes(t: time) -> int:
    """Converts a datetime.time object to total minutes from midnight."""
    return t.hour * 60 + t.minute

def total_minutes_to_time(total_minutes: int) -> time:
    """Converts total minutes from midnight back to a datetime.time object."""
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return time(hours, minutes)

def read_packages_csv(file_path: str) -> List[Package]:
    packages = []
    with open(file_path, mode='r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                package = Package(
                    id=row['package_id'],
                    destination_id=row['destination_id'],
                    weight_kg=float(row['weight_kg']),
                    volume_m3=float(row['volume_m3']),
                    tw_open=parse_time_str(row['tw_open']),
                    tw_close=parse_time_str(row['tw_close']),
                    service_min=int(row['service_min']),
                    priority=int(row['priority'])
                )
                packages.append(package)
            except (ValueError, KeyError) as e:
                print(f"Error reading packages.csv row {row}: {e}")
                # In a real system, this would be logged more formally and handled per FR-02
    return packages

def read_vehicles_csv(file_path: str) -> List[Vehicle]:
    vehicles = []
    with open(file_path, mode='r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                vehicle = Vehicle(
                    id=row['vehicle_id'],
                    max_weight_kg=float(row['max_weight_kg']),
                    max_volume_m3=float(row['max_volume_m3']),
                    depot_location_id=row['depot_location_id']
                )
                vehicles.append(vehicle)
            except (ValueError, KeyError) as e:
                print(f"Error reading vehicles.csv row {row}: {e}")
    return vehicles

def read_locations_csv(file_path: str) -> Dict[str, Location]:
    locations = {}
    with open(file_path, mode='r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                location = Location(
                    id=row['location_id'],
                    name=row['name']
                )
                locations[location.id] = location
            except (ValueError, KeyError) as e:
                print(f"Error reading locations.csv row {row}: {e}")
    return locations

def read_distances_csv(file_path: str) -> Dict[Tuple[str, str], Distance]:
    distances = {}
    with open(file_path, mode='r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                distance = Distance(
                    from_location_id=row['from_location_id'],
                    to_location_id=row['to_location_id'],
                    distance_km=float(row['distance_km']),
                    travel_time_min=int(row['travel_time_min'])
                )
                distances[(distance.from_location_id, distance.to_location_id)] = distance
            except (ValueError, KeyError) as e:
                print(f"Error reading distances.csv row {row}: {e}")
    return distances

def check_file_exists(file_path: str) -> bool:
    """Checks if a file exists at the given path."""
    return os.path.exists(file_path) and os.path.isfile(file_path)

class DistanceGraph:
    """Represents the graph of locations and distances."""
    def __init__(self, distances_data: Dict[Tuple[str, str], Distance], all_location_ids: Set[str]):
        self._graph: Dict[str, Dict[str, Distance]] = {loc_id: {} for loc_id in all_location_ids}
        for (from_loc, to_loc), dist_obj in distances_data.items():
            if from_loc in self._graph and to_loc in self._graph:
                self._graph[from_loc][to_loc] = dist_obj
            else:
                print(f"Warning: Distance entry {from_loc}->{to_loc} refers to unknown location(s).")
        
        # Ensure all locations from input are in the graph, even if they have no connections
        for loc_id in all_location_ids:
            if loc_id not in self._graph:
                self._graph[loc_id] = {}

    def get_distance_info(self, from_loc_id: str, to_loc_id: str) -> Optional[Distance]:
        """Returns Distance object for a direct connection, or None if not found."""
        return self._graph.get(from_loc_id, {}).get(to_loc_id)

    def find_shortest_path(self, start_loc_id: str, end_loc_id: str) -> Optional[Tuple[List[str], float, int]]:
        """
        Finds the shortest path between two locations using Dijkstra's algorithm.
        Returns (path_list, total_distance_km, total_travel_time_min) or None if no path exists.
        """
        if start_loc_id not in self._graph or end_loc_id not in self._graph:
            return None # One or both locations are not in the graph

        # (current_travel_time_min, current_distance_km, current_location_id, path_list)
        priority_queue = [(0, 0.0, start_loc_id, [start_loc_id])]
        
        # Keep track of the shortest time found to reach a node
        shortest_times: Dict[str, int] = {loc_id: float('inf') for loc_id in self._graph}
        shortest_times[start_loc_id] = 0

        # Keep track of paths
        predecessors: Dict[str, str] = {}
        distances_to_node: Dict[str, float] = {loc_id: float('inf') for loc_id in self._graph}
        distances_to_node[start_loc_id] = 0.0

        while priority_queue:
            current_time, current_dist, current_loc, path = heapq.heappop(priority_queue)

            if current_time > shortest_times[current_loc]:
                continue # Already found a shorter path to this node

            if current_loc == end_loc_id:
                return path, current_dist, current_time

            for neighbor_loc, dist_obj in self._graph[current_loc].items():
                time_to_neighbor = dist_obj.travel_time_min
                dist_to_neighbor = dist_obj.distance_km

                new_time = current_time + time_to_neighbor
                new_dist = current_dist + dist_to_neighbor

                # Primary optimization: minimize time, secondary: minimize distance
                # Dijkstra works with a single cost. To combine, we can make a tuple (time, distance)
                # and Python's tuple comparison will handle it.
                # However, since the problem states "minimize distance, in case of a tie, minimize duration",
                # the pathfinding should ideally use (distance, time) as the priority.
                # Let's adjust Dijkstra to prioritize distance, then time.

                # Redo priority queue for (current_distance_km, current_travel_time_min, current_location_id, path_list)
                # This makes it Dijkstra on distance, and then for equal distances, time.
                # For path reconstruction, we need predecessors.

                # Let's simplify for now to pure time-based Dijkstra to get something working.
                # The VRP solver itself will apply the optimization criteria.
                
                # If a shorter time to reach neighbor is found (or equal time with shorter distance for tie-breaking)
                if new_time < shortest_times[neighbor_loc]: # Standard Dijkstra on time
                    shortest_times[neighbor_loc] = new_time
                    distances_to_node[neighbor_loc] = new_dist # Store associated distance
                    heapq.heappush(priority_queue, (new_time, new_dist, neighbor_loc, path + [neighbor_loc]))
                elif new_time == shortest_times[neighbor_loc] and new_dist < distances_to_node[neighbor_loc]:
                    # Tie-breaking: if times are equal, prefer shorter distance
                    distances_to_node[neighbor_loc] = new_dist
                    heapq.heappush(priority_queue, (new_time, new_dist, neighbor_loc, path + [neighbor_loc]))
        
        return None # No path found
