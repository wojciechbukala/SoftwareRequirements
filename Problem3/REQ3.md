# Introduction

## Purpose
This file consists complete requirements specification for Fleet Route program. This means that for AI agent or developer working on a code this is the priority document and rules defined here should be considered always before other sources.

FleetRouter is a program that helps with the management of courier company logistics. It support sdaily route planning. The main goals of the program are:
- **G1** - FleetRouter shall assign every package to a vehicle, and produce order of the route for each vehicle in the way that every package is delivered.
- **G2** - If package can't be delivered program should mark it as undeliverable with a specified reason.
- **G3** - FleetRouter shall minimise total distance driven across the entire fleet (a sum of distances of vehicles); in case of a tie minimise total route duration.

## Scope
The principal function of the FleetRouter program is to produce the best possible daily plan for courier company. Comanies in the spedtion industry can benefit from it to have more efficient routes in in consequences less costs, time-efficient delivery and emission reduction. Application is algorithmic focused, presentation and usability side is a lower priority for the stakeholders. The phenomenas in the ecosystem can be defined as:
### World Phenomenas
- **WP1** - Packages with the specified weight, volume and desired delivery location.
- **WP2** - Vehicles with specified volume capacity and origin depot.
- **WP3** - Drivers - employees with limited working time
- **WP4** - Locations connected by distances and trip times
- **WP5** - Time windows for package deliveries
- **WP6** - Package priorities set by the comapny

### Shared phenomenas:
Interactions controlled by the world:
- **SP1** - Data about packages
- **SP2** - Data about vehicles
- **SP3** - Data about locations
- **SP4** - Data about distances and travel times
, and interactions controlled by the machine:
- **SP5** - Produced routes
- **SP6** - Undeliverable packages with reason
- **SP7** - Routes stats

## Product overview

### Product perspective
Product overview can be described using a domain class diagram as a conceptual model of entities and relations between them in the FleetRoute. The diagram does not determine the class for implementation.

Domain class diagram transformed to Mermaid.js form:
classDiagram
    class Location {
        +location_id
        +name
    }

    class Distance {
        +origin_id
        +destination_id
        +distance
        +travel_time
    }

    class Vehicle {
        +vehicle_id
        +weight_capacity
        +volume_capacity
        +depot_location_id
    }

    class Package {
        +package_id
        +destination_id
        +weight
        +volume
        +tw_open
        +tw_close
        +priority
    }

    class Stops {
        +route_id
        +vehicle_id
        +location_id
        +delivered_id
        +position_in_order
        +arrival_time
        +departure_time
    }

    class RouteSummary {
        +route_id
        +total_distance
        +total_time
        +packages_delivered
        +undeliverable
    }

    class Undeliverable {
        +package_id
        +reason
    }

    %% Relacje
    Location "0..*" -- "1..*" Distance : origin of
    Location "0..*" -- "1..*" Distance : destination of
    Location "1" -- "1..*" Vehicle : has depot
    Location "1" -- "0..*" Package : desired destination
    Location "1" -- "0..*" Stops : takes place at
    Vehicle "1" -- "0..*" Stops : delivered by
    Package "1" -- "0..1" Stops : delivered package
    Package "1" -- "0..1" Undeliverable : can be
    RouteSummary "1" -- "0..*" Stops : is element of

### Product functions

Package state machine:
stateDiagram-v2
    [*] --> Unassigned

    Unassigned --> Assigned : Fits constraints
    Unassigned --> Undeliverable : No vehicle fits

    Assigned --> Delivered : Route executed
    Delivered --> [*]

    state Undeliverable {
        direction TB
        Reason --> CAPACITY_WEIGHT
        CAPACITY_WEIGHT --> CAPACITY_VOLUME
        CAPACITY_VOLUME --> TIME_WINDOW
        TIME_WINDOW --> NO_VEHICLE
        NO_VEHICLE --> MAX_DRIVER_TIME
    }

    Undeliverable --> [*]

Route state diagram:
stateDiagram-v2
    [*] --> Empty
    
    Empty --> BuildingRoute : Add stop
    
    state "Building route" as BuildingRoute
    BuildingRoute --> BuildingRoute : Add stop
    BuildingRoute --> Validated : Validate constraints
    
    Validated --> [*]


### User characteristics
The only user of program are employees of the courier company. They are qualified staff with understanding of the process. We call them Fleet Operator (also the only actor for use cases).

### Limitations
Constraints



## Definitions
- Courier company - every company that can make profit out of the system, and needs daily routes scheduling with package assignments. Real-world examples: DHL, FedEx, UPS.
- Route
- Package
- Undeliverable
- Depot
- Vehicle
- Stop

# Requirements

## Function

**Functional requirements for FleetRouter problem are listed below.**

### FR-01 - Read input data
The system shall read input data including:
- Package data from *packages.csv*, including package ID, weight in kg, volume in m3, opening of time window, closing of time window, time of service in minutes, and priority of package. 
- Vehicle data from *vehicles.csv*, including vehicle ID, maximum weight capacity in kg, maximum volume cpacity in m3, and depot location ID.
- Locations data from *locations.csv*, including location ID and name.
- Distances data from *distances.csv*, including origin location ID, destination location ID, distance in km, and travel time in minutes. 
The system shall treat all four inputs files as mandatory; if any file is missing or unreadable, the system shall terminate and report the missing file.

### RF-02 Input data validation
THe system shall:
- Verify every that every location ID referenced in *packages.csv* and *vehicles.csv* exists in *locations.csv*; any package or vehicle referencing an unknown location ID shall be reported and excluded from processing. 
- Verify that each package's time window closing time is strictly greater than its opening time; any package violating this condition shall be recorded in *undeliverable.csv* with reason code TIME_WINDOW.
- Verify that distance entry exists for every ordered pair of location IDs required to construct a route. If missing, the system should report gap and treat the connection as unreachable.

### RF-03 Assigning packages to vehicles
Regarding proccess of assigning packages to vehicles, the system shall:
- Attempt to assign every package to exactly one vehicle. Priority packages should be assigned before non-priority packages when vehicle capacity forces a choice. 
- Not assign a package to a vehicle if cumulative weight or volume would exceed the limit for a given vehicle, such package shall be reporded in *undeliverable.csv* with reason code CAPACITY_WEIGHT or CAPACITY_VOLUME.
- Not assign a package to a vehicle if the eraliest feasible delivery time for thet package on that vehicle exceeds the package's time window colsing time; a package should be recorded in *undeliverable.csv* with code TIME_WINDOW.
- Not assign a package if adding that package would cause the vehicle's total route duration (travel time + waiting time + service time at every stop) to exceed 8 hours; such package shall be recorded in *undeliverable.csv* with a code MAX_DRIVER_TIME.

If package cannot be assigned to any avaiable vehicle after all other constraints have been evaluated, mark such package in *undeliverable.csv* with a code NO_VEHICLE.

### RF-04 Routing
Considering routing, the system shall:
- Construct daily route for every vehicle strating and ending in assigned depot location.
- Assing a stop order to each stop in a route, starting at 1 for the first stop after the depot.
- Compute the arrival time at each stop as the departure time of previous stop plus the travel time between the two locations.
- Compute the waiting the waiting time at each stop as a difference between the package's time window opening time and the computed arrival time.
- Compute the departure time at each stop as the arrival or window opening, plus the pacakge's service duration.
- Ensure that each vehicle makes exactly one trip per day.

### RF-05 Optimization
In case of optimisation the system shall:
- Minimise the total distance driven across all vehicle routes among all constraint-satisfying solutions.
- Use total route duration as a secondary optimisation criterion.

### RF-06 Output generation
The system shall:
- Write one row to *stops_order.csv* for each stop in each route. Columns should consists of (*names in file*): route ID (*route_id*), vehicle ID (*vehicle_id*), position of the stop in sequence for a given route (*stop_position_in_order*), ID of the location of the stop (*location_id*), ID of delivered package (*delivery_package_id*), arrival time  (*arrival_time*), departure time (*departure_time*). Group and sort stops for each vehicle
- Write one row to *summary.csv* for each vehicle. Columns should consists of (*names in file*): vehicle ID (*vehicle_id*), total driven distance in kilometers (*total_distance_km*), total driven time in minutes (*total_time_min*), number of delivered packages (*packages_delivered*). Every vehicle defined in *vehicles.csv* should be included.
- Write one row to *undeliverable.csv* for each package that cannot be assigned to any route. Columns should consists of (*names in file*): package ID (*package_id*), code of the reason (*reason*). Available reason codes consists of: CAPACITY_WEIGHT, CAPACITY_VOLUME, TIME_WINDOW, MAX_DRIVER_TIME, NO_VEHICLE. Exactly one reason code for each undeliverable package.

**Functional requirements can be compleated by use the main use case of the program, when operator wants to generate the routes**

### UC-01 - Run daily route planning
| Actor | Fleet Operator |
| Entry condition | All foour input CSV files are provided |
| Event flow | 1. System reads and validates all input files 2. System assigns packages to vahicles respecting all constraints 3. System builds and optimises routes 4. System writes output files 5.  System reports completion with package counts. |
| Exit condition | All three output files have been written sucessfully |
| Exceptions | EX1. Input file missing - system terminates and reports which file is absent. |

[SEQUENCE DIAGRAM]


## Performance requirements
Program shall be able to run on the reference machine with at least specification of:
- CPU: 4-core, 2 GHz base clock
- RAM: 8 GB
- Storage:: SSD
- OS: Windows 10 64-bit or Linux 64-bit

The system shall support input datsets containing up to 500 packages and 50 vehicles in a single planning run with maxiumum of 200 distinct locations and 40 000 entries in *distnaces.csv* (200x200).

## Usability requirements and Interface requirements
FleetRouter shall be operated exclusively through a command-line interface. The system must accept all required parameters in a single invocation command, requiring no interactive input during execution. The command syntax shall follow the form: *fleetrouter --input <dir> --output <dir>*, where both arguments are mandatory.

All progress and error messages written to standard output or standard error must be easy to read by humen user.

Upon completion, the system shall print a single summary line stating the number of packages processed, delivered, recorded as undeliverable.

## Design constraints
3.4

## Software system attributes

### Security
The system can hold data that are confidential from the buisiness perespective of courier company, therefore program should operate only offline with the usage of single machine to ensure no data leaks.

### Maintainabiliy
The system should be implemented in a way that is easy to scale, maintain, and test. The code must reamin readable, maintainable, and documented.

### Portability
The system should be assessible from most of the modern komputers, with at technical specification of at least one specified in Performance Requirements section.

# Verification

# Appendices

## Assumptions and dependencies

## Requirements Mapping

## Acronyms and abbreviations

## State diagrams
