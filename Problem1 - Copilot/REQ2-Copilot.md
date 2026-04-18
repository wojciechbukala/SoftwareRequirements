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
- **SP4** - State transition records, structured data recording internal transitions, feature decisions, and issued commands.
- **SP5** - Actuator commands, electronic instructions sent to specific actuators.
- **SP6** - Attentiveness prompts, small steering wheel movements initiated by the system to verify driver presence.
- **SP7** - System alarms.

## 1.3. Product overview

### 1.3.1. Product perspective
The Copilot program operates in an environment composed of sensors, a driver, and vehicle actuators, and its behavior is organized around a few conceptual entities.

The program consumes two kinds of inputs from its environment. A sensor event is a single reading produced by one of the on-board sensors, and a driver event is a single interaction orginating from the driver.

In response to these inputs, the program maintains its own runtime context with its currently operating mode, the time of the most recent attentiveness prompt, and whether a driver response is currently being awaited - and produces three kinds of outputs. A state transition record of changes of the operating mode. An actuator command is an instruction sent to one of the vehicle's actuators. Lastly, a feature decision is the outcome of evaluating one autonomous feature for a given input.

The above is a conceptual description of the program's environment and internal data and is not intended to prescribe a class structure for implementation.

### 1.3.2. Product functions
At the highest level, Copilot provides five main functions.
- **Autonomous mode management** - Copilot maintains an operating mode that determines how it reacts to incoming events. It can be either disengaged or engaged. The driver controls transitions between these two modes, and the program may additionally enter transient safety-oriented modes in reaction to conditions described below. 
- **Emergency braking** - Copilot continuously monitors Lidar readings and, when an obstacle is detected at a crucial distance, issues a braking command to the vehicle's braking system. This safety function takes precedence over every other function and is active at all times.
- **Driver attentiveness monitoring** - While in engaged mode, Copilot periodically verifies that the driver remains attentive by prompting them for a confirming steering wheel action. If the driver reacts appropriately within the allotted window, autonomous operation continues.
- **Driver override** - at any moment, a sufficient force applied by the driver to the steering wheel is interpreted as an intent to take manual control.

### 1.3.3. User characteristics
The users of the Copilot simulation software are primarliy Automotive Software Engineers - Qualified technical staff who use the simulation to verify the correctness of autonomous algorithms.

### 1.3.4. Limitations
- **L-01** - Offline Simulation - The system operates as a software simulation. It does not interface with real vehicle hardware.
- **L-02** - Data Format - All communication between the environment and the system is strictly limited to the provided CSV file formats.
- **L-03** - Single-Machine Execution - The system must run on a single workstation without the need for network connectivity.

## 1.4. Definitions
- Lidar - A remote sensing method that uses light in the form of a pulsed laser to measure ranges to the objects.
- Actuator - A component of a machine that is responsible for moving and controlling a mechanism or system.
- Attentiveness Check - A safety procedure where the system prompts the driver to confirm they are monitoring the road by applying a small force to the steering wheel.
- Emergency Braking - A safety feature that automatically applies the brakes to prevent a collision when an obstacle is detected at a critical distance.

# 2. References
The only reference is CONTEXT-Copilot.md file with the task description, in the form as received from stakeholders.

# 3. Requirements

## 3.1. Functions - Functional Requirements
Functional requirements for Copilot are listed below. 

### FR-01 - System State and Mode Transitions
Copilot shall maintain one of the following states at all times: Disengaged, Engaged, AwaitingResponse, and Alarming. The starting state is Disengaged. A state transition is an actual change of state; events that keep the system in the same state shall not be recorded in *state_log.csv*.

### FR-02 - Autonomous Driving Logic and Priority
When in Engaged mode, the system shall process every sensor event and produce a feature decision for each applicable autonomous feature: lane keeping, cruise control, and emergency braking. Emergency braking should be evaluated first, before any other feature.

Always, a Lidar sensor reading with a distance value strictly less than 5 meters must trigger an emergency braking decision. When emergency braking is triggered, the Copilot shall send a braking command to the Braking System actuator and should abandon processing lane keeping or cruise control for that cycle.

For camera sensor readings, a lane keeping correction value and cruise control adjustment shall be computed and provided to the actuator.

The system shall record every feature decision to *feature_decision.csv* and every actuator command issued to *commands_log.csv*.

When in Disengaged mode, data shall be logged but without further actions on actuator commands or feature decisions.

### FR-03 - Attentiveness Monitoring and Alarm
When in Engaged mode, the system shall issue an attentiveness prompt every 120 seconds by issuing a small steering wheel movement command to the steering wheel actuator and transitioning to the AwaitingResponse state.

In AwaitingResponse state, system must wait up to 5 seconds for a valid driver response. A valid response is assumed to be wheel force of 3N or less within the 5-second window. When valid response registered system shall transition back to engaged state and reset the 120-second prompt timer. A steering wheel force event with a value strictly greater than 3N and strictly less than 10N shall be ignored, and the system shall continue waiting for a valid response. If no valid response is received within 5 seconds, the system shall transition to the Alarming state and emit a continuous alarm command to the alarm actuator. The system escapes the Alarming state na transitions to Engaged state if a steering wheel force event with a value of 3N or less is received.

Every state transition produced by the attentiveness monitoring mechanism shall be recorded to *state_log.csv*.

### FR-04 - Driver Override
A steering wheel force event with a value strictly greater than 10N shall cause immediate transition to Disengaged mode regardless of the current system state. 

### FR-05 - Data Ingestion and Command Output
Copilot shall read sensor events from *sensor_log.csv* and driver events from *driver_events.csv* as the sole sources of input. All events from both files should be processed in ascending timestamp order.

## 3.2. Functions - Processing Flows

### PF-01 - Sensor event
This processing flow specifies, for a single incoming sensor event, the order in which Copilot evaluates autonomous features, the conditions under which each feature produces a decision, and the resulting writes to output files.

Every sensor event is first recorded by the program as received. If the event originates from a Lidar sensor, the program evaluates emergency braking before considering any other feature and does so regardless of the current operating mode. When the reported distance is strictly less than 5 meters, the program decides on emergency braking, writes a corresponding feature decision to *feature_decision.csv*, issues a braking command to the Braking System actuator, and records that command in *commands_log.csv*. Otherwise, when the reported distance is 5 meters or greater, the program records a non-braking decision.

If the event originates from a sensor other than Lidar, the program only takes further action when it is currently in engaged mode. A camera sensor event causes the program to compute a lane keeping correction and a cruise control adjustment, to issue the resulting commands to the Steering Motor actuator and the speed actuator, to record both commands in commands_log.csv, and to record the two corresponding feature decisions in feature_decision.csv.

### PF-02 - Loop execution flow
On program start, Copilot reads all events from sensor_log.csv and all events from driver_events.csv and merges them into a single event stream ordered by ascending timestamp. The program then iterates over this stream in order, dispatching each event to the appropriate handler: sensor events are handled according to PF-01, and driver events are handled according to the rules specified in FR-01, FR-03, and FR-04. When the stream is exhausted, the program flushes all output files and terminates.

## 3.3. Performance requirements
The program shall be able to run on the reference machine with at least specification of:
- CPU: 4-core, 1.60 GHz base clock
- RAM: 16 GB
- Storage: SSD
- OS: Linux 64-bit

Considering latency, the system shall process each sensor reading and driver event within 50 milliseconds.

## 3.4. Usability requirements and Interface requirements
Copilot operates exclusively through a command-line interface. The paths to input and output files shall be configurable via command-line arguments, eliminating the need for hardcoded file paths. The command syntax shall follow the form: *copilot --input <\dir> --output <\dir>*, where both argument are mandatory. 

The CLI shall provide clear, real-time status updates to the standard output. The paths to input and output files shall be configurable via command-line arguments, eliminating the need for hardcoded file paths.

## 3.5. Design constraints
The system shall clearly separate the perception layer, the decision logic, and the actuator control layer. The source code must adhere to clean code principles.

All input and output files shall use CSV format with a comma as the field separator and UTF-8 encoding. The first row of every file shall be a header row containing column names as specified below.
**inputs**
- *sensor_log.csv*: timestamp, sensor_id, sensor_type, data_value, unit.
- *driver_events.csv*: timestamp, event_type, value.
Allowed values for *driver_events.csv*:
1) ENGAGE
2) DISENGAGE
3) STEERING_FORCE

**outputs**
- *state_log.csv*: timestamp, previous_state, current_state, trigger_event.
- *commands_log.csv*: timestamp, actuator_id, values.
- *feature_decision.csv*: timestamp, feature, decision.

## 3.6. Software system attributes

### Security
The system is designed to operate strictly offline on a single machine. No network-based data transmission is permitted. 

### Maintainbility
The system shall be designed to support automated unit testing. Moreover, the source code must include comprehensive inline documentation.

### Portability
The system must be capable of running on any POSIX-compliant operating system and Windows. The software shall not require any specialized hardware (e.g., GPU acceleration) or external database engines to function.

# 4. Verification
Verification of the Copilot system shall be performed by the evaluator through black_box assessment of program outputs against provided input files. No specific testing framework or automated test suite is prescribed. The delivered software shall be submitted to an authorized evaluator responsible for all testing and verification activities.

Each functional requirement shall be considered satisfied if the contents of the output files are consistent with the behaviour specified in Section 2.1. Verification of non-functional requirements shall be performed by manual measurement on the reference machine defined in Section 2.3.

# 5. Appendices

## 5.1. Assumptions and dependencies

### Domain assumptions
- **DA-01** - It is assumed that the input CSV files are well-formed and follow the predefined schema.
- **DA-02** - The system assumes that at any given time, at least one Lidar sensor and one camera sensor provide valid readings to allow for safe autonomous operation logic.
- **DA-03** - The simulation assumes that the vehicle's physical actuators respond instantly and perfectly to the electronic commands issued by the Copilot system.

## 5.2. Acronyms and abbreviations
- G - Goal
- WP - World Phenomena
- SP - Shared phenomena
- L - Limitations
- FR - Functional Requirement
- PF - Processing Flow
- DA - Domain Assumption

- CSV - Comma-Separated Values
- CLI - Command Line Interface
- RAM - Random Access Memory
- N - Newton
- POSIX - Portable Operating System Interface
