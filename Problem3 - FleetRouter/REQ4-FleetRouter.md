# 1. Purpose
This file consists of complete requirements specifications for the Fleet Route program. This means that for an AI agent or developer working on a code, this is the priority document, and rules defined here should always be considered before other sources.

FleetRouter is a program that helps with the management of courier company logistics. It supports daily route planning. The main goals of the program are:
- **G-01** - FleetRouter shall assign every package to a vehicle and produce an order of the route for each vehicle in the way that every package is delivered.
- **G-02** - If a package can't be delivered program should mark it as undeliverable with a specified reason.
- **G-03** - FleetRouter shall minimize total distance driven across the entire fleet (a sum of distances of vehicles); in case of a tie, minimize total route duration.

The principal function of the FleetRouter program is to produce the best possible daily plan for a courier company. Companies in the spedition industry can benefit from it to have more efficient routes, and in consequence, less costs, time-efficient delivery, and emission reduction. The application is algorithmically focused, presentation and usability side are lower priorities for the stakeholders.

# 2. Alloy model
(signatures, facts, predicates, assertions)

# 3. Operational envelope

# 3.1. I/O operations

# 3.2. Non-functional requirements
The program shall be able to run on the reference machine with at least specification of:
- CPU: 4-core, 2 GHz base clock
- RAM: 8 GB
- Storage: SSD
- OS: Windows 10 64-bit or Linux 64-bit

The system shall support input datasets containing up to 500 packages and 50 vehicles in a single planning run with a maxiumum of 200 distinct locations and 40,000 entries in *distances.csv* (200x200).

# 3.3. Verification approach

# 4. Appendices

## 4.1. Domain assumptions
- **DA-01** - All four input CSV files are provided by the operator before each planning run and reflect the actual state of the fleet and package list for that day.
- **DA-02** - Distance and travel time values provided in input reflect real-world road conditions at the time of planning. Distance entries are not assumed to be symmetric.
- **DA-03** - Package weights and volumes are non-negative.
- **DA-04** — Planning-day start time. All vehicles are assumed to depart from their assigned depot at 08:00 on the planning day. This value is a fixed constant of the planning run and is not provided through input files. All time-window, travel-time, and driver-time computations in FR-03 and FR-04 are anchored to this departure time. 