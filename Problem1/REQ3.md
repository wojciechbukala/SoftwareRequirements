# Introduction

## Purpose
This file consists complete requirements specification for the Copilot driver-assistance system. The main golas of the system are:

- **G1** - Copilot shall process periodic sensor data and driver events to determine the vehicle autonomous state and maintain safe driving conditions.
- **G2** - The system shall prioritize safety-critical decisions, specifically emergency braking based on real-time environmental perceptions (Lidar and camera data).
- **G3** - Copilot shall monitor driver attentiveness through periodic checks and ensure immediate disengagement or alarm triggering if the driver's respons is inadequate or manual override is detected.

## Scope
The Copilot program is a simulation of an onboard computer for advanced driver assistance. It focuses on the logic of autonomous operations (lane keeping, cruise control, emergency braking) without direct hardware integration, operation as an offline tool.

### World Phenomenas
- **WP1** - Obstacles and road conditions measured by Lidar and lane markings captured by camera.
- **WP2** - Driver interactions such as the physical force applied on the steering wheel and manual operations of control buttons.
- **WP3** - Vehicle dynamics as mechanical movemanet of the car, its speed, and its position within a lane.
- **WP4** - Mechanical systems (Braking System, Steering Motor) that receive electronic signals to perform physical actions.

### Shared phenomenas:
Interactions controlled by the world:

- **SP1** - Sensor log, periodic digital readings from cameras and Lidar sensors provided in a CSV format.
- **SP2** - Driver events, signals form the driver.
- **SP3** - Steering force, numeric values representing the force applied by the driver to the steering wheel.

, and interactions controlled by the machine:
- **SP5** - State transition records, structured data recording internal transitions, feature decision, and issued commands.
- **SP6** - Actuator commands, electronic instructions sent to specific actuators.
- **SP7** - Attentiveness prompts, small steering wheel movements initiated by the system to verify driver presence.
- **SP8** - System alarms.

## Product overview

### Product perspective
Product overview can be described using a domain class diagram as a conceptual model of entities and relations between them in the Copilot. The diagram does not determine the class for implementation.

[CLASS DIAGRAM]

### Product functions

[STATE MACHINES]

### User characteristics
The users of the Copilot simulation software are primarly Automotive Software Engineers - Qualified technical staff who use the simulation to verify the correctness of autonoumous algorithms. 

### Limitations
- **L-01** - Offline Simulation - The system opearates as a software simulation. It does not interface with real vehicle hardware.
- **L-02** - Data Format - All communication between the environment and the system is strictly limited to the provided CSV file formats.
- **L-03** - Single-Machine Execution - The system must run on a single workstation without the need for network connectivity.

## Definitions
- Lidar - A remote sensing method that uses light in the form of a pulsed laser to measure ranges to the objects.
- Actuator - A component of a machine that is responsible for moving and controlling a mechanism  or system.
- Attentiveness Check - A safety procedure where the system prompts the driver to confirm thay are monitoring the road by applying a small force to the steering wheel.
- Emergency Braking - A safety feature that automatically applies the brakes to prevent a collision when as obstacle is detected at a critical distance.

# Requirements

## Functions
Functional requirements for Copilot are listed below. 

### FR-01 - System State and Mode Transitions

### FR-02 - Autonomous Driving Logic and Priority

### FR-03 - Attentiveness Monitoring and Alarm

### FR-04 - Driver Override

### FR-05 - Data Ingestion and Command Output

## Performance requirements
- Latency: The system shall process each sensor reading and driver event within 50 milliseconds.

## Usability requirements and Interface requirements
The system shall provide a simple, text-based Command Line Interface. The CLI shall provide clear, real-time status updates to the standard output. The paths to input and output files shall be configurable via command-line arguments, eliminating the need for hardcode file paths.

## Design constraints
3.4

## Software system attributes
3.5

# Verification

# Appendices

## Assumptions and dependencies

## Acronyms and abbreviations

## State diagrams
