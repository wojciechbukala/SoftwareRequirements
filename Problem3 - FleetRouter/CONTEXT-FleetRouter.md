## Problem - FleetRouter
A courier company operates a fleet of vehicles delivering packages to customers within a single working day. Every vehicle departs from a central depot at the start of the day and must return before the depot closes. Packages are known in advance: each has a weight, a volume, a delivery address, and a time window during which the delivery must occur. The distance and travel time between every pair of locations are known. The program must assign packages to vehicles and determine the visit order for each vehicle such that every package is delivered (or explicitly reported as undeliverable with a reason), no vehicle exceeds its weight or volume capacity at any point on its route, no driver exceeds the maximum working time for the day, and every delivery occurs within the packages’s time window. The program must produce across all vehicles.

## Input data
- *packages.csv* - [package_id, destination_id, weight_kg, volume_m3, tw_open, tw_close, service_min, priority]
- *vehicles.csv*  - [vehicle_id, max_weight_kg, max_volume_m3, depot_location_id]
- *locations.csv* - [location_id, name]
- *distances.csv* - [from_location_id, to_location_id, distance_km, travel_time_min]

## Output data
- *stops_order.csv* - [route_id, vehicle_id, stop_position_in_order, location_id, delivered_id, arrival_time, departure_time]
- *undeliverable.csv* - [package_id, reason]
- *summary.csv* - [vehicle_id, total_distance_km, total_time_min, packages_delivered]