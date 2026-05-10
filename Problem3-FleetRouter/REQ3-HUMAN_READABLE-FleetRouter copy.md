# 1. Introduction

## 1.1. Purpose
This file consists of complete requirements specifications for the Fleet Route program. This means that for an AI agent or developer working on a code, this is the priority document, and rules defined here should always be considered before other sources.

FleetRouter is a program that helps with the management of courier company logistics. It supports daily route planning. The main goals of the program are:
- **G-01** - FleetRouter shall assign every package to a vehicle and produce an order of the route for each vehicle in the way that every package is delivered.
- **G-02** - If a package can't be delivered program should mark it as undeliverable with a specified reason.
- **G-03** - FleetRouter shall minimize total distance driven across the entire fleet (a sum of distances of vehicles); in case of a tie, minimize total route duration.

## 1.2. Scope
The principal function of the FleetRouter program is to produce the best possible daily plan for a courier company. Companies in the spedition industry can benefit from it to have more efficient routes, and in consequence, less costs, time-efficient delivery, and emission reduction. The application is algorithmically focused, presentation and usability side are lower priorities for the stakeholders. The phenomena in the ecosystem can be defined as:
### 1.2.1. World Phenomenas
- **WP-01** - Packages with the specified weight, volume, and desired delivery location.
- **WP-02** - Vehicles with specified volume capacity and origin depot.
- **WP-03** - Drivers - employees with limited working time
- **WP-04** - Locations connected by distances and trip times
- **WP-05** - Time windows for package deliveries
- **WP-06** - Package priorities set by the comapny

### 1.2.2. Shared phenomenas
**Interactions controlled by the world:**
- **SP-01** - Data about packages
- **SP-02** - Data about vehicles
- **SP-03** - Data about locations
- **SP-04** - Data about distances and travel times

**And interactions controlled by the machine:**
- **SP-05** - Produced routes
- **SP-06** - Undeliverable packages with reason
- **SP-07** - Routes stats

## 1.3. Product overview

### 1.3.1. Product perspective
Product overview can be described using a domain class diagram as a conceptual model of entities and relations between them in the FleetRoute. The diagram does not determine the classes for implementation.

Domain class diagram transformed to Mermaid.js form:

![Domain Class Diagram](/Problem3%20-%20FleetRouter/Diagrams/P3_DCD.drawio.png)

### 1.3.2. Product functions
The core processing logic of FleetRouter is captured by two state machines. The firs one models the lifecycle of a single package. The second one models the lifecycle of a route being constructed for a given vehicle.

Package state machine:

![Package state machine](/Problem3%20-%20FleetRouter/Diagrams/P3_SM1.drawio.png)

Route state diagram:

![Route state machine](/Problem3%20-%20FleetRouter/Diagrams/P3_SM2.drawio.png)


### 1.3.3. User characteristics
The only user of the program are employees of the courier company. They are qualified staff with an understanding of the process. We call them Fleet Operator, or simply a user.


### 1.3.4. Limitations
- **L-01** - Offline Simulation - The system operates as a software simulation. It does not interface with real vehicle hardware.
- **L-02** - Data Format - All communication between the environment and the system is strictly limited to the provided CSV file formats.
- **L-03** - Single-Machine Execution - The system must run on a single workstation without the need for network connectivity.


## 1.4. Definitions
- Courier company - every company that can make a profit out of the system and needs daily route scheduling with package assignments. Real-world examples: DHL, FedEx, UPS.
- Route - A sequence of stops that some vehicle has to complete in order to deliver some packages.
- Package - An item with a specified weight and volume that is supposed to be delivered to some location (stop)
- Undeliverable - Package that cannot be delivered on a specific date without disrupting some constraints.
- Depot - A logistic center of a courier company, the place of start and finish for vehicles.
- Vehicle - A car operated by a company with a specified weight and volume load.
- Stop - A place of delivery of some package.
- Waiting time - At a given stop on a route, the idle interval during which a vehicle has already arrived at the stop's location but cannot begin service because the destination package's time window has not yet opened.

# 2. References
The only reference is CONTEXT-FleetRouter.md file with the task description, in the form as received from stakeholders.

# 3. Requirements

## 3.1. Function - Functional Requirements

### FR-01 - Read input data
The system shall read the four mandatory CSV files (*packages.csv*, *vehicles.csv*, *locations.csv*, *distances.csv*) whose contents realize the domain model in Section 1.3.1. If any file is missing or unreadable, the system shall terminate and report the missing file.

### FR-02 Input data validation
The system shall:
- Verify that every location ID referenced in *packages.csv* and *vehicles.csv* exists in *locations.csv*; any package or vehicle referencing an unknown location ID shall be reported and excluded from processing. 
- Verify that each package's time window closing time is strictly greater than its opening time; any package violating this condition shall be recorded in *undeliverable.csv* with reason code TIME_WINDOW.
- Verify that a distance entry exists in *distances.csv* for every ordered pair of location IDs required to construct a route. If a required pair is missing, the system shall report the gap and treat that connection as unreachable. A package whose assignment would require traversing an unreachable connection — either to reach its destination from any feasible predecessor or to return to the depot — shall be recorded in undeliverable.csv with reason code UNREACHABLE.

### FR-03 Assigning packages to vehicles
Regarding the proccess of assigning packages to vehicles, the system shall:
- Attempt to assign every package to exactly one vehicle. Priority packages should be assigned before non-priority packages when vehicle capacity forces a choice. 
- Not assign a package to a vehicle if cumulative weight or volume would exceed the limit for a given vehicle, such package shall be reported in *undeliverable.csv* with reason code CAPACITY_WEIGHT or CAPACITY_VOLUME.
- Not assign a package to a vehicle if the earliest feasible delivery time for that package on that vehicle exceeds the package's time window closing time; a package should be recorded in *undeliverable.csv* with code TIME_WINDOW.
- Not assign a package if adding that package would cause the vehicle's total route duration (travel time + waiting time + service time at every stop) to exceed 8 hours; such package shall be recorded in *undeliverable.csv* with a code MAX_DRIVER_TIME.

If a package cannot be assigned to any available vehicle after all other constraints have been evaluated, mark such a package in *undeliverable.csv* with a code NO_VEHICLE.

### FR-04 Routing
Considering routing, the system shall:
- Construct a daily route for every vehicle starting and ending in the assigned depot location.
- Assign a stop order to each stop in a route, starting at 1 for the first stop after the depot.
- Compute the arrival time at each stop as the departure time of the previous stop plus the travel time between the two locations.
- Compute the waiting time at each stop as a difference between the package's time window opening time and the computed arrival time.
- Compute the departure time at each stop as the arrival or window opening plus the package's service duration.
- Ensure that each vehicle makes exactly one trip per day.

### FR-05 Optimization
In case of optimisation, the system shall:
- Minimize the total distance driven across all vehicle routes among all constraint-satisfying solutions.
- Use total route duration as a secondary optimization criterion.

### FR-06 Output generation
The system shall:
- Write one row to *stops_order.csv* for each stop in each route. Columns should consist of (*names in file*): route ID (*route_id*), vehicle ID (*vehicle_id*), position of the stop in sequence for a given route (*stop_position_in_order*), ID of the location of the stop (*location_id*), ID of delivered package (*delivery_package_id*), arrival time  (*arrival_time*), departure time (*departure_time*). Group and sort stops for each vehicle
- Write one row to *summary.csv* for each vehicle. Columns should consist of (*names in file*): vehicle ID (*vehicle_id*), total driven distance in kilometers (*total_distance_km*), total driven time in minutes (*total_time_min*), number of delivered packages (*packages_delivered*). Every vehicle defined in *vehicles.csv* should be included.
- Write one row to *undeliverable.csv* for each package that cannot be assigned to any route. Columns should consist of (*names in file*): package ID (*package_id*), code of the reason (*reason*). Available reason codes consists of: CAPACITY_WEIGHT, CAPACITY_VOLUME, TIME_WINDOW, MAX_DRIVER_TIME, NO_VEHICLE, UNREACHABLE. Exactly one reason code for each undeliverable package.

## 3.2. Function - Use Cases

### UC-01 - Run daily route planning
UC-01 represents the sole interaction between the Fleet Operator and the system. As the operator starts planing, the system operates autonomously without further user input — reading, planning, and writing results as a single uninterrupted batch process. The sequence diagram below illustrates the complete message flow between the operator, the system, and the file system.

![Seqence Diagram](/Problem3%20-%20FleetRouter/Diagrams/P3_SD1.drawio.png)

## 3.3. Performance requirements
The program shall be able to run on the reference machine with at least specification of:
- CPU: 4-core, 2 GHz base clock
- RAM: 8 GB
- Storage: SSD
- OS: Windows 10 64-bit or Linux 64-bit

The system shall support input datasets containing up to 500 packages and 50 vehicles in a single planning run with a maxiumum of 200 distinct locations and 40,000 entries in *distances.csv* (200x200).

## 3.4. Usability requirements and Interface requirements
FleetRouter operates exclusively through a command-line interface. The system must accept all required parameters in a single invocation command, requiring no interactive input during execution. The command syntax shall follow the form: *fleetrouter --input <\dir> --output <\dir>*, where both arguments are mandatory.

All progress and error messages written to standard output or standard error must be easy to read by humen user.

Upon completion, the system shall print a single summary line stating the number of packages processed, delivered, recorded as undeliverable.

## 3.5. Design constraints
All input and output files shall use the CSV format with a comma as the field separator and UTF-8 encoding. The first row of every file should be a header row containing column names as specified. 
**inputs**
- *packages.csv*: package_id, destination_id, weight_kg, volume_m3, tw_open, tw_close, service_min, priority
The priority column in packages.csv shall contain an integer value from the set {0, 1}, where 1 marks a priority package and 0 marks a non-priority package. No other values are permitted; any package with a value outside this set shall be reported and excluded from processing in the same way as other invalid input rows (see FR-02).

- *vehicles.csv*: vehicle_id, max_weight_kg, max_volume_m3, depot_location_id
- *locations.csv*: location_id, name
- *distances.csv*: from_location_id, to_location_id, distance_km, travel_time_min
**outputs**
- *stops_order.csv* - route_id, vehicle_id, stop_position_in_order, location_id, delivered_id, arrival_time, departure_time
- *undeliverable.csv* - package_id, reason
- *summary.csv* - vehicle_id, total_distance_km, total_time_min, packages_delivered

Time values in all input and output files must follow the format HH:MM, distance values in kilometers rounded to two decimal places, and duration values as integer minutes.

Additionally the source code must adhere to clean code principles.

## 3.6. Software system attributes

### Security
The system can hold data that are confidential from the business perespective of the courier company, therefore program should operate only offline with the usage of a single machine to ensure no data leaks.

### Maintainabiliy
The system should be implemented in a way that is easy to scale, maintain, and test. The code must remain readable, maintainable, and documented.

### Portability
The system should be accessible from most of the modern computers, with at least one specified in the Performance Requirements section.

# 4. Verification
Verification of the FleetRouter system shall be performed by the evaluator through black_box assessment of program outputs against provided input files. No specific testing framework or automated test suite is prescribed. The delivered software shall be submitted to an authorized evaluator responsible for all testing and verification activities.

Each functional requirement shall be considered satisfied if the contents of the output files are consistent with the behaviour specified in Section 2.1. Verification of non-functional requirements shall be performed by manual measurement on the reference machine defined in Section 2.3.

# 5. Appendices

## 5.1. Assumptions and dependencies

### Domain assumptions
- **DA-01** - All four input CSV files are provided by the operator before each planning run and reflect the actual state of the fleet and package list for that day.
- **DA-02** - Distance and travel time values provided in input reflect real-world road conditions at the time of planning. Distance entries are not assumed to be symmetric.
- **DA-03** - Package weights and volumes are non-negative.
- **DA-04** — Planning-day start time. All vehicles are assumed to depart from their assigned depot at 08:00 on the planning day. This value is a fixed constant of the planning run and is not provided through input files. All time-window, travel-time, and driver-time computations in FR-03 and FR-04 are anchored to this departure time. 

## 5.2. Acronyms and abbreviations
- G - Goal
- WP - World Phenomena
- SP - Shared phenomena
- L - Limitations
- FR - Functional Requirement
- UC - Use case
- DA - Domain Assumption

- CSV - Comma-Separated Values
- CLI - Command-Line Interface
- RAM - Random Access Memory


