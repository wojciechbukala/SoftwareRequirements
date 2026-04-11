# 1. Introduction

## 1.1. Purpose
This file consists of the complete requirements specification for the Copilot driver-assistance system. The main goals of the system are:

- **G1** - Copilot shall process periodic sensor data and driver events to determine the vehicle's autonomous state and maintain safe driving conditions.
- **G2** - The system shall prioritize safety-critical decisions, specifically emergency braking based on real-time environmental perceptions (Lidar and camera data).
- **G3** - Copilot shall monitor driver attentiveness through periodic checks and ensure immediate disengagement or alarm triggering if the driver's response is inadequate or manual override is detected.

## 1.2. Scope
The Copilot program is a simulation of an onboard computer for advanced driver assistance. It focuses on the logic of autonomous operations (lane keeping, cruise control, emergency braking) without direct hardware integration, operating as an offline tool.

### 1.2.1. World Phenomenas
- **WP1** - Obstacles and road conditions measured by Lidar and lane markings captured by camera.
- **WP2** - Driver interactions such as the physical force applied on the steering wheel and manual operations of control buttons.
- **WP3** - Vehicle dynamics as mechanical movement of the car, its speed, and its position within a lane.
- **WP4** - Mechanical systems (Braking System, Steering Motor) that receive electronic signals to perform physical actions.

### 1.2.2. Shared phenomenas:
**Interactions controlled by the world**:

- **SP1** - Sensor log, periodic digital readings from cameras and Lidar sensors provided in a CSV format.
- **SP2** - Driver events, signals from the driver.
- **SP3** - Steering force, numeric values representing the force applied by the driver to the steering wheel.

**Interactions controlled by the machine**:
- **SP5** - State transition records, structured data recording internal transitions, feature decisions, and issued commands.
- **SP6** - Actuator commands, electronic instructions sent to specific actuators.
- **SP7** - Attentiveness prompts, small steering wheel movements initiated by the system to verify driver presence.
- **SP8** - System alarms.

## 1.3. Product overview

### 1.3.1. Product perspective
The domain of the Copilot program with neccessary dependencies and relations is presented below using dmain class diagram. It is a conceptual model of the syastem in a given environment and it does not determine the class for implementation.

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

### 1.3.2. Product functions
The core behaviour of the Copilot system is governed by a state machine with four states: Disengaged, Engaged, AwaitingResponse, and Alarming. The state machine is presented below. 

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

### 1.3.3. User characteristics
The users of the Copilot simulation software are primarly Automotive Software Engineers - Qualified technical staff who use the simulation to verify the correctness of autonomous algorithms.

### 1.3.4. Limitations
- **L-01** - Offline Simulation - The system operates as a software simulation. It does not interface with real vehicle hardware.
- **L-02** - Data Format - All communication between the environment and the system is strictly limited to the provided CSV file formats.
- **L-03** - Single-Machine Execution - The system must run on a single workstation without the need for network connectivity.

## 1.3.5. Definitions
- Lidar - A remote sensing method that uses light in the form of a pulsed laser to measure ranges to the objects.
- Actuator - A component of a machine that is responsible for moving and controlling a mechanism or system.
- Attentiveness Check - A safety procedure where the system prompts the driver to confirm thry are monitoring the road by applying a small force to the steering wheel.
- Emergency Braking - A safety feature that automatically applies the brakes to prevent a collision when an obstacle is detected at a critical distance.

# 2. Requirements

## 2.1. Functions - Functional Requirements
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

## 2.2. Functions - Processing Flows

### PF-01 - Sensor event
The processing logic applied to each sensor event depends on the sensor type and the current system state. The diagram below specifies th evaluation order of autonomous features and the resulting writes to output files for a single sensor processing cycle.

    flowchart TD
    A([sensor event received]) --> B[log raw event]
    B --> C{system state == Engaged?}
    C -- No --> Z([end cycle])
    C -- Yes --> D{sensor_type == Lidar?}

    D -- Yes --> E{data_value < 5 m?}
    E -- Yes --> F[decide: emergency_braking = BRAKE]
    F --> G[issue command to BrakingSystem actuator]
    G --> H[write to feature_decision.csv\nwrite to commands_log.csv]
    H --> Z

    E -- No --> I[decide: emergency_braking = NO_BRAKE]
    I --> J[write to feature_decision.csv]
    J --> Z

    D -- No --> K{sensor_type == Camera?}
    K -- Yes --> L[compute lane keeping correction]
    L --> M[compute cruise control adjustment]
    M --> N[issue commands to SteeringMotor\nand SpeedActuator]
    N --> O[write to feature_decision.csv x2\nwrite to commands_log.csv x2]
    O --> Z

    K -- No --> Z

### PF-02 - Loop execution flow
Copilot reads events from two independent input files which are merged into a single chronological stream before processing begins. The diagram below shows the program execution flow startup to termination, including the merging of input surces and the sequential dispatching of events.

    flowchart TD
    A([program start]) --> B[read sensor_log.csv]
    A --> C[read driver_events.csv]
    B --> D[merge into single event stream\nsorted by timestamp ascending]
    C --> D
    D --> E{next event in stream?}
    E -- No --> F[flush all output buffers]
    F --> G([program end])
    E -- Yes --> H{event type?}
    H -- sensor event --> I[run sensor processing cycle]
    H -- driver event --> J[run driver event processing]
    I --> E
    J --> E


## 2.3. Performance requirements
The program shall be able to run on the reference machine with at least specification of:
- CPU: 4-core, 1.60 GHz base clock
- RAM: 16 GB
- Storage: SSD
- OS: Linux 64-bit

Considering latency, the system shall process each sensor reading and driver event wothin 50 milliseconds.

## 2.4. Usability requirements and Interface requirements
Copilot operates exclusively through a command-line interface. The paths to input and output files shall be configurable via command-line arguments, eliminating the need for hardcodeed file paths. The command syntax shall follow the form: *copilot --input <\dir> --output <\dir>*, where both argument are mandatory. 

The CLI shall provide clear, real-time status updates to the standard output. The paths to input and output files shall be configurable via command-line arguments, eliminating the need for hardcodeed file paths.

## 2.5. Design constraints
The system shall clearly separate the perception layer, the decision logic, and the actuator control layer. The source code must adhere to clean code principles.

All input and output files shall use CSV format with a coma as the field separator and UTF-8 encoding. The first row of every file shall be a header row containing column names as specified below.
**inputs**
- *sensor_log.csv*: timestamp, sensor_id, sensor_type, data_value, unit.
- *driver_events.csv*: timestamp, event_type, value.
**outputs**
- *state_log.csv*: timestamp, previous_state, current_state, trigger_event.
- *comands_log.csv*: timestamp, actuator_id, values.
- *feature_decision.csv*: timestamp, feature, decision.

## 2.6. Software system attributes

### Security
The system is designed to operate strictly offline on a single machine. No network-based data transmission is permitted. 

### Maintainbility
The system shall be designed to support automated unit testing. Moreover, the source code must include comprehensive inline documentation.

### Portability
The system must be capable of running on any POSIX-compliant operating system and Windows. The software shall not require any specialized hardware (e.g., GPU acceleration) or external database engines to function.

# 3. Verification
Verification of the Copilot system shall be performed by the evaluator through black_box assessment of program outputs against provided input files. No specific testing framework or automated test suite is prescribed. The delivered software shall be submitted to an authorized evaluator responsible for all testing and verification activities.

Each functional requirement shall be considered satisfied if the contents of the output files are consistent with the behaviour specified in Section 2.1. Verification of non-functional requirements shall be performed by manual measurement on the reference machine defined in Section 2.3.

# 4. Appendices

## 4.1. Assumptions and dependencies

### Domain assumptions
- **DA-01** - It is assumed that the input CSV files are well-formed and follow the predefined schema.
- **DA-02** - The system assumes that at any given time, at least one Lidar sensor and one camera sensor provide valid readings to allow for safe autonomous operation logic.
- **DA-03** - The simulation assumes that the vehicle's physical actuators respond instantly and perfectly to the electronic commands issued by the Copilot system.

## 4.2. Acronyms and abbreviations
- G - Goal
- WP - World Phenomena
- SP - Shared phenomena
- L - Limitations
- FR - Functional Requirement
- PF - Processing Flow
- DA - Domain Assumption

- CSV - Comma-Separated Values
- CLI - Command Line Interface
- RAM - Random Acess Memory
- N - Newton
- POSIX - Portable Operating System Interface
