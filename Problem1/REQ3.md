# Introduction

## Purpose
This file consists of the complete requirements specification for the Copilot driver-assistance system. The main goals of the system are:

- **G1** - Copilot shall process periodic sensor data and driver events to determine the vehicle's autonomous state and maintain safe driving conditions.
- **G2** - The system shall prioritize safety-critical decisions, specifically emergency braking based on real-time environmental perceptions (Lidar and camera data).
- **G3** - Copilot shall monitor driver attentiveness through periodic checks and ensure immediate disengagement or alarm triggering if the driver's response is inadequate or manual override is detected.

## Scope
The Copilot program is a simulation of an onboard computer for advanced driver assistance. It focuses on the logic of autonomous operations (lane keeping, cruise control, emergency braking) without direct hardware integration, operating as an offline tool.

### World Phenomenas
- **WP1** - Obstacles and road conditions measured by Lidar and lane markings captured by camera.
- **WP2** - Driver interactions such as the physical force applied on the steering wheel and manual operations of control buttons.
- **WP3** - Vehicle dynamics as mechanical movement of the car, its speed, and its position within a lane.
- **WP4** - Mechanical systems (Braking System, Steering Motor) that receive electronic signals to perform physical actions.

### Shared phenomenas:
**Interactions controlled by the world**:

- **SP1** - Sensor log, periodic digital readings from cameras and Lidar sensors provided in a CSV format.
- **SP2** - Driver events, signals from the driver.
- **SP3** - Steering force, numeric values representing the force applied by the driver to the steering wheel.

**Interactions controlled by the machine**:
- **SP5** - State transition records, structured data recording internal transitions, feature decisions, and issued commands.
- **SP6** - Actuator commands, electronic instructions sent to specific actuators.
- **SP7** - Attentiveness prompts, small steering wheel movements initiated by the system to verify driver presence.
- **SP8** - System alarms.

## Product overview

### Product perspective
Product overview can be described using a domain class diagram as a conceptual model of entities and relations between them in Copilot. The diagram does not determine the class for implementation.

    classDiagram
        class SensorEvent {
            +timestamp
            +sensor_id
            +sensor_type
            +data_value
            +unit
        }
        class DriverEvent {
            +timestamp
            +event_type
            +value
        }
        class CopilotSystem {
            +mode
            +last_prompt_time
            +awaiting_response
        }
        class StateTransition {
            +timestamp
            +previous_state
            +current_state
            +trigger_event
        }
        class ActuatorCommand {
            +timestamp
            +actuator_id
            +values
        }
        class FeatureDecision {
            +timestamp
            +feature
            +decision
        }
        class AttentivenessCheck {
            +prompt_time
            +deadline
            +status
        }
    
        SensorEvent "1..*" --> "1" CopilotSystem : triggers processing cycle
        DriverEvent "0..*" --> "1" CopilotSystem : triggers event
        CopilotSystem "1" --> "0..*" StateTransition : records
        CopilotSystem "1" --> "0..*" ActuatorCommand : issues
        CopilotSystem "1" --> "0..*" FeatureDecision : produces
        CopilotSystem "1" --> "0..1" AttentivenessCheck : manages

### Product functions

    stateDiagram-v2
        [*] --> Disengaged
    
        Disengaged --> Engaged : driver engaged
    
        Engaged --> Disengaged : driver disengaged
        Engaged --> Disengaged : steering force > 10 N
        Engaged --> AwaitingResponse : attentiveness prompt issued
    
        AwaitingResponse --> Engaged : steering force <= 3 N [within 5s]
        AwaitingResponse --> AwaitingResponse : 3 N < steering force < 10 N [ignored]
        AwaitingResponse --> Disengaged : steering force > 10 N
        AwaitingResponse --> Alarming : no valid response for 5s
    
        Alarming --> Engaged : steering force <= 3 N
        Alarming --> Disengaged : steering force > 10 N
    
        Engaged --> [*] : car turned off
        AwaitingResponse --> [*] : car turned off
        Alarming --> [*] : car turned off
        Disengaged --> [*] : car turned off

### User characteristics
The users of the Copilot simulation software are primarly Automotive Software Engineers - Qualified technical staff who use the simulation to verify the correctness of autonomous algorithms. 

### Limitations
- **L-01** - Offline Simulation - The system operates as a software simulation. It does not interface with real vehicle hardware.
- **L-02** - Data Format - All communication between the environment and the system is strictly limited to the provided CSV file formats.
- **L-03** - Single-Machine Execution - The system must run on a single workstation without the need for network connectivity.

## Definitions
- Lidar - A remote sensing method that uses light in the form of a pulsed laser to measure ranges to the objects.
- Actuator - A component of a machine that is responsible for moving and controlling a mechanism or system.
- Attentiveness Check - A safety procedure where the system prompts the driver to confirm thry are monitoring the road by applying a small force to the steering wheel.
- Emergency Braking - A safety feature that automatically applies the brakes to prevent a collision when an obstacle is detected at a critical distance.

# Requirements

## Functions
Functional requirements for Copilot are listed below. 

### FR-01 - System State and Mode Transitions
Copilot shall maintain one of the following states at all times: Disengaged, Engaged, AwaitingResponse, and Alarming. The starting state is Disengaged.

### FR-02 - Autonomous Driving Logic and Priority
When in Engaged mode, the system shall process every sensor event and produce a feature decision for each applicable autonomous feature: lane keeping, cruise control, and emergency braking. Emergency braking should be evaluated first, before any other feature.

Always, a Lidar sensor reading with a distance value strictly less than 5 meters must trigger an emergency braking decision. When emergency braking is triggered, the Copilot shall send a braking command to the Braking System actuator and should abandon processing lane keeping or cruise control for that cycle.

For camera sensor readings, a lane keeping correction value and cruise control adjustment shall be computed and provided to the actuator.

The system shall record every feature decision to *feature_decision.csv* and every actuator command issued to *commands_log.csv*.

When in Disengaged mode, data shall be logged but without further actions on actuator commands or feature decisions.

### FR-03 - Attentiveness Monitoring and Alarm
When in Engaged mode, the system shall issue an attentiveness prompt every 120 seconds by issuing a small steering wheel movement command to the steering wheel actuator and transitioning to the AwaitingResponse state.

In Awaitingresponse state, system must wait up to 5 seconds for a valid driver response. A valid response is assumed to be wheel force of 3N or less within the 5-second window. When valid response registered system shall transition back to engaged state and reset the 120-second prompt timer. A steering wheel force event with a value strictly greater than 3N and strictly less than 10N shall be ignored, and the system shall continue waiting for a valid response. If no valid response is received within 5 seconds, the system shall transition to the Alarming state and emit a continuous alarm command to the alarm actuator. The system escapes the Alarming state na transitions to Engaged state if a steering wheel force event with a value of 3N or less is received.

Every state transition produced by the attentiveness monitoring mechanism shall be recorded to *state_log.csv*.

### FR-04 - Driver Override
A steering wheel force event with a value strictly greater than 10N shall cause immediate transition to Disengaged mode regardless of the current system state. 

### FR-05 - Data Ingestion and Command Output
Copilot shall read sensor events from *sensor_log.csv* and driver events from *driver_events.csv* as the sole sources of input. All events from both files should be processed in ascending timestamp order.

## Performance requirements
- Latency: The system shall process each sensor reading and driver event within 50 milliseconds.
- Resources: Copilot shall be executable on a reference machine meeting at least the following specification:
1) CPU: 2-core, 1.5 GHz base clock
2) RAM: 4 GB
3) Storage: HDD

## Usability requirements and Interface requirements
The system shall provide a simple, text-based Command Line Interface. The CLI shall provide clear, real-time status updates to the standard output. The paths to input and output files shall be configurable via command-line arguments, eliminating the need for hardcodeed file paths.

## Design constraints
The system shall clearly separate the perception layer, the decision logic, and the actuator control layer. The source code must adhere to clean code principles.

All input and output files shall use CSV format with a coma as the field separator and UTF-8 encoding. The first row of every file shall be a header row containing column names as specified below.
**inputs**
- *sensor_log.csv*: timestamp, sensor_id, sensor_type, data_value, unit.
- *driver_events.csv*: timestamp, event_type, value.
**outputs**
- *state_log.csv*: timestamp, previous_state, current_state, trigger_event.
- *comands_log.csv*: timestamp, actuator_id, values.
- *feature_decision.csv*: timestamp, feature, decision.

## Software system attributes

### Security
The system is designed to operate strictly offline on a single machine. No network-based data transmission is permitted. 

### Maintainbility
The system shall be designed to support automated unit testing. Moreover, the source code must include comprehensive inline documentation.

### Portability
The system must be capable of running on any POSIX-compliant operating system and Windows. The software shall not require any specialized hardware (e.g., GPU acceleration) or external database engines to function.

# Verification
The Copilot system shall be verified through a combination of automated testing, log inspection, and simulation walkthroughs to ensure all functional and non-functional requirements are met.

A suite of automated test cases shall be developed to verify the core logic of the system, specifically the state machine transitions (Engaged/Disengaged) and the priority handling of Emergency Braking over other commands.

# Appendices

## Assumptions and dependencies

### Domain assumptions
- **DA-01** - It is assumed that the input CSV files are well-formed and follow the predefined schema.
- **DA-02** - The system assumes that at any given time, at least one Lidar sensor and one camera sensor provide valid readings to allow for safe autonomous operation logic.
- **DA-03** - The simulation assumes that the vehicle's physical actuators respond instantly and perfectly to the electronic commands issued by the Copilot system.

## Acronyms and abbreviations
- CLI - Command Line Interface
- FR - Functional Requirement
- Lidar - Light Detection and Rangiing
- N - Newton
- POSIX - Portable Operating System Interface
- UC - Use case
