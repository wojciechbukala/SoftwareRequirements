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

### Product functions
- Produce schedule - 
- Produce summary - 

### User characteristics
The only user of program are employees of the courier company. They are qualified staff with understanding of the process...

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

## Functions
Functional requirements

###

## Performance requirements

System scalibility and user load

Aggregate Data Processing and Availability

## Usability requirements
Dodaj - napisz jedno zdanie o prostym interfejsie terminalowym zgodnym z POSIX

## Interface requirements
składnię wywołania, flagi, format wejścia/wyjścia, kody wyjścia (exit codes)

## Logical database requirements
Dodaj - jeśli potrzebne w tym problemie

## Design constraints
3.4

## Software system attributes
3.5

# Verification

# Appendices

## Assumptions and dependencies

## Acronyms and abbreviations

## State diagrams
