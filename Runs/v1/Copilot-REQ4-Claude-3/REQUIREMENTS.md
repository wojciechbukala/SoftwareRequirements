# 1. Purpose
The Copilot program is a simulation of an onboard computer for advanced driver assistance. It focuses on the logic of autonomous operations (lane keeping, cruise control, emergency braking) without direct hardware integration, operating as an offline tool. The main goals of the system are:

- **G1** - Copilot shall process periodic sensor data and driver events to determine the vehicle's autonomous state and maintain safe driving conditions.
- **G2** - The system shall prioritize safety-critical decisions, specifically emergency braking based on real-time environmental perceptions (Lidar and camera data).
- **G3** - Copilot shall monitor driver attentiveness through periodic checks and ensure immediate disengagement or alarm triggering if the driver's response is inadequate or manual override is detected.

# 2. Alloy model
```
// Copilot - Alloy6 model

//---Enumerated domains---
enum State {Disengaged, Engaged, AwaitingResponse, Alarming}
enum SensorType {Lidar, Camera}
enum DriverEventType {ENGAGE, DISENGAGE, STEERING_FORCE}
enum FeatureDecisionKind {EmergencyBraking, LaneKeeping, CruiseControl}
enum DecisionValue {BRAKE, NO_BRAKE, ADJUST}

//---SIGNATURES---

abstract sig Actuator {}
one sig BrakingSystem extends Actuator {}
one sig SteeringMotor extends Actuator {}
one sig SpeedActuator extends Actuator {}
one sig AlarmActuator extends Actuator {}

//---Threshold constants---
fun LIDAR_DANGER: Int {5}
fun OVERRIDE_FORCE: Int {10}
fun VALID_RESPONSE_FORCE : Int {3}
fun PROMPT_INTERVAL: Int {120}
fun RESPONSE_WINDOW: Int {5}

// representation of one State log entry.
sig StateLogEntry {
    time: Int,
    previous: State,
    current: State
}

// representation of one Command log entry
sig Command {
    time: one Int,
    target: one Actuator
}

// representation of one FeatureDecision log entry
sig FeatureDecision {
    time: one Int,
    feature: one FeatureDecisionKind,
    value: one DecisionValue
}


abstract sig Event {
    time: one Int
}

sig SensorEvent extends Event {
    sensorType: one SensorType,
    dataValue:  one Int
}

sig DriverEvent extends Event {
    eventType: one DriverEventType,
    force:     lone Int
}

// Core system signature
var one sig SystemState {
    var currentState: one State,
    var currentTime: one Int,
    var lastPrompt: one Int,
    var awaitingSince: one Int,

    // output buffers
    var stateLog: set StateLogEntry,
    var commandsLog: set Command,
    var featureDecisionLog: set FeatureDecision,

    // events the machine has already processed
    var processedEvents: set Event
}

//---FACTS---

//Signature consistency

fact DecisionValuesConsistent {
    all fd: FeatureDecision {
        // emergency braking decides about BRAKE / NO_BRAKE
        fd.feature = EmergencyBraking implies fd.value in BRAKE + NO_BRAKE
        // lane keeping and cruise control produce an ADJUST value
        fd.feature in (LaneKeeping + CruiseControl) implies fd.value = ADJUST
    }
}

fact UniqueEventTimestamps {
    all disj e1, e2: Event | e1.time != e2.time
}

fact NonNegativeTimestamps {
    all s:  StateLogEntry | s.time  >= 0
    all c:  Command | c.time  >= 0
    all fd: FeatureDecision | fd.time >= 0
    all e:  Event | e.time  >= 0
}

fact OnlySteeringForceEventsHaveForce {
    all d: DriverEvent {
        d.eventType = STEERING_FORCE iff some d.force
    }
}

fact NonNegativeForce {
    all d: DriverEvent | some d.force implies d.force >= 0
}

fact NonEmptyEventStream {
    some Event
}

fact BothSensorKindsPresent {
    some SensorEvent implies {
        some se: SensorEvent | se.sensorType = Lidar
        some se: SensorEvent | se.sensorType = Camera
    }
}

fact NonNegativeSensorValue {
    all s: SensorEvent | s.dataValue >= 0
}

fact StateTransitionIsActual {
    all s: StateLogEntry | s.previous != s.current
}

fact NoOrphanRecords {
    all s:  StateLogEntry | eventually s  in SystemState.stateLog
    all c:  Command  | eventually c  in SystemState.commandsLog
    all fd: FeatureDecision | eventually fd in SystemState.featureDecisionLog
}

fact AllEventsEventuallyProcessed {
    all e: Event | eventually e in SystemState.processedEvents
}

//--- Getter functions (read-only helpers) ---
fun cs: State {SystemState.currentState}
fun now: Int {SystemState.currentTime}
fun sLog: set StateLogEntry {SystemState.stateLog}
fun cLog: set Command {SystemState.commandsLog}
fun fLog: set FeatureDecision {SystemState.featureDecisionLog}
fun done: set Event {SystemState.processedEvents}

// set of events not yet consumed
fun pending: set Event { Event - done }

// the next event to process (smallest-time pending event)
fun nextEvent: lone Event {
    {e: pending | all e2: pending - e | e.time < e2.time}
}

//---PREDICATES---

// initial settings of the system
pred init {
    cs = Disengaged
    now = 0
    SystemState.lastPrompt = 0
    SystemState.awaitingSince = 0
    no sLog
    no cLog
    no fLog
    no done
}

// advance the discrete clock by 1
pred tickTime {
    SystemState.currentTime' = plus[SystemState.currentTime, 1]
}

// mark event e as consumed
pred processEvent[e: Event] {
    SystemState.processedEvents' = SystemState.processedEvents + e
}

// append one state-log entry describing a transition
pred addStateLog[t: Int, from: State, to: State] {
    some entry: StateLogEntry {
        entry not in SystemState.stateLog
        entry.time     = t
        entry.previous = from
        entry.current  = to
        SystemState.stateLog' = SystemState.stateLog + entry
    }
}

// append one command record
pred emitCommand[t: Int, a: Actuator] {
    some c: Command {
        c not in SystemState.commandsLog
        c.time   = t
        c.target = a
        SystemState.commandsLog' = SystemState.commandsLog + c
    }
}

// append one feature-decision record
pred emitFeatureDecision[t: Int, f: FeatureDecisionKind, d: DecisionValue] {
    some fd: FeatureDecision {
        fd not in SystemState.featureDecisionLog
        fd.time    = t
        fd.feature = f
        fd.value   = d
        SystemState.featureDecisionLog' = SystemState.featureDecisionLog + fd
    }
}

//---EVENT HANDLERS---

pred handleEngageDriverEvent[e: Event] {
    processEvent[e]
    tickTime

    // Disengaged -> Engaged
    cs = Disengaged implies {
        SystemState.currentState' = Engaged
        SystemState.lastPrompt' = SystemState.currentTime'
        SystemState.awaitingSince' = SystemState.awaitingSince
        addStateLog[e.time, Disengaged, Engaged]
        SystemState.commandsLog' = SystemState.commandsLog
        SystemState.featureDecisionLog' = SystemState.featureDecisionLog
    }

    // Already not Disengaged -> no-op
    cs != Disengaged implies {
        SystemState.currentState' = SystemState.currentState
        SystemState.lastPrompt' = SystemState.lastPrompt
        SystemState.awaitingSince' = SystemState.awaitingSince
        SystemState.stateLog' = SystemState.stateLog
        SystemState.commandsLog' = SystemState.commandsLog
        SystemState.featureDecisionLog' = SystemState.featureDecisionLog
    }
}

pred handleDisengageDriverEvent[e: Event] {
    processEvent[e]
    tickTime

    // Any non-Disengaged state -> Disengaged
    cs != Disengaged implies {
        SystemState.currentState'       = Disengaged
        SystemState.lastPrompt'         = SystemState.lastPrompt
        SystemState.awaitingSince'      = SystemState.awaitingSince
        addStateLog[e.time, cs, Disengaged]
        SystemState.commandsLog'        = SystemState.commandsLog
        SystemState.featureDecisionLog' = SystemState.featureDecisionLog
    }

    // Already Disengaged -> no-op
    cs = Disengaged implies {
        SystemState.currentState' = SystemState.currentState
        SystemState.lastPrompt' = SystemState.lastPrompt
        SystemState.awaitingSince'  = SystemState.awaitingSince
        SystemState.stateLog' = SystemState.stateLog
        SystemState.commandsLog' = SystemState.commandsLog
        SystemState.featureDecisionLog' = SystemState.featureDecisionLog
    }
}

pred handleSteeringForceDriverEvent[e: Event] {
    processEvent[e]
    tickTime

    let f = e.force {

        // Override: force > 10N, any state -> Disengaged (FR-04)
        f > OVERRIDE_FORCE implies {
            cs != Disengaged implies {
                SystemState.currentState' = Disengaged
                addStateLog[e.time, cs, Disengaged]
            }
            cs = Disengaged implies {
                SystemState.currentState' = SystemState.currentState
                SystemState.stateLog' = SystemState.stateLog
            }
            SystemState.lastPrompt' = SystemState.lastPrompt
            SystemState.awaitingSince' = SystemState.awaitingSince
            SystemState.commandsLog' = SystemState.commandsLog
            SystemState.featureDecisionLog' = SystemState.featureDecisionLog
        }

        // Valid response while AwaitingResponse -> Engaged, reset prompt timer
        (f <= VALID_RESPONSE_FORCE and cs = AwaitingResponse) implies {
            SystemState.currentState' = Engaged
            SystemState.lastPrompt' = SystemState.currentTime'
            SystemState.awaitingSince' = SystemState.awaitingSince
            addStateLog[e.time, AwaitingResponse, Engaged]
            SystemState.commandsLog' = SystemState.commandsLog
            SystemState.featureDecisionLog' = SystemState.featureDecisionLog
        }

        // Alarm escape: low force while Alarming -> Engaged, reset prompt timer
        (f <= VALID_RESPONSE_FORCE and cs = Alarming) implies {
            SystemState.currentState' = Engaged
            SystemState.lastPrompt' = SystemState.currentTime'
            SystemState.awaitingSince' = SystemState.awaitingSince
            addStateLog[e.time, Alarming, Engaged]
            SystemState.commandsLog' = SystemState.commandsLog
            SystemState.featureDecisionLog' = SystemState.featureDecisionLog
        }

        // Ignored mid-range force while AwaitingResponse -> no-op, keep waiting
        (f > VALID_RESPONSE_FORCE and f <= OVERRIDE_FORCE and cs = AwaitingResponse) implies {
            SystemState.currentState' = SystemState.currentState
            SystemState.lastPrompt' = SystemState.lastPrompt
            SystemState.awaitingSince'  = SystemState.awaitingSince
            SystemState.stateLog' = SystemState.stateLog
            SystemState.commandsLog' = SystemState.commandsLog
            SystemState.featureDecisionLog' = SystemState.featureDecisionLog
        }

        // Other case (e.g. low force in Disengaged/Engaged) -> no-op
        (
            not (f > OVERRIDE_FORCE)
            and not (f <= VALID_RESPONSE_FORCE and cs = AwaitingResponse)
            and not (f <= VALID_RESPONSE_FORCE and cs = Alarming)
            and not (f > VALID_RESPONSE_FORCE and f <= OVERRIDE_FORCE and cs = AwaitingResponse)
        ) implies {
            SystemState.currentState' = SystemState.currentState
            SystemState.lastPrompt' = SystemState.lastPrompt
            SystemState.awaitingSince'  = SystemState.awaitingSince
            SystemState.stateLog'  = SystemState.stateLog
            SystemState.commandsLog' = SystemState.commandsLog
            SystemState.featureDecisionLog' = SystemState.featureDecisionLog
        }
    }
}

pred handleLidarSensorEvent[e: Event] {
    processEvent[e]
    tickTime

    SystemState.currentState' = SystemState.currentState
    SystemState.lastPrompt' = SystemState.lastPrompt
    SystemState.awaitingSince' = SystemState.awaitingSince
    SystemState.stateLog' = SystemState.stateLog

    e.dataValue < LIDAR_DANGER implies {
        emitFeatureDecision[e.time, EmergencyBraking, BRAKE]
        emitCommand[e.time, BrakingSystem]
    }
    e.dataValue >= LIDAR_DANGER implies {
        emitFeatureDecision[e.time, EmergencyBraking, NO_BRAKE]
        SystemState.commandsLog' = SystemState.commandsLog
    }
}

pred handleCameraSensorEvent[e: Event] {
    processEvent[e]
    tickTime
    SystemState.currentState' = SystemState.currentState
    SystemState.lastPrompt' = SystemState.lastPrompt
    SystemState.awaitingSince' = SystemState.awaitingSince
    SystemState.stateLog' = SystemState.stateLog

    cs = Engaged implies {
        // emit two feature decisions (LaneKeeping + CruiseControl)
        some fd1, fd2: FeatureDecision {
            fd1 != fd2
            fd1 not in SystemState.featureDecisionLog
            fd2 not in SystemState.featureDecisionLog
            fd1.time = e.time and fd1.feature = LaneKeeping   and fd1.value = ADJUST
            fd2.time = e.time and fd2.feature = CruiseControl and fd2.value = ADJUST
            SystemState.featureDecisionLog' = SystemState.featureDecisionLog + fd1 + fd2
        }
        // emit two commands (SteeringMotor + SpeedActuator)
        some c1, c2: Command {
            c1 != c2
            c1 not in SystemState.commandsLog
            c2 not in SystemState.commandsLog
            c1.time = e.time and c1.target = SteeringMotor
            c2.time = e.time and c2.target = SpeedActuator
            SystemState.commandsLog' = SystemState.commandsLog + c1 + c2
        }
    }
    cs != Engaged implies {
        SystemState.featureDecisionLog' = SystemState.featureDecisionLog
        SystemState.commandsLog' = SystemState.commandsLog
    }
}

//Step handler
pred step[e: Event] {
    // precondition: e is the next pending event
    e = nextEvent

    e in SensorEvent implies {
        (e.sensorType = Lidar)  implies handleLidarSensorEvent[e]
        (e.sensorType = Camera) implies handleCameraSensorEvent[e]
    }
    e in DriverEvent implies {
        (e.eventType = ENGAGE)         implies handleEngageDriverEvent[e]
        (e.eventType = DISENGAGE)      implies handleDisengageDriverEvent[e]
        (e.eventType = STEERING_FORCE) implies handleSteeringForceDriverEvent[e]
    }
}

//Internal step handler
pred internalStep {
    tickTime
    SystemState.processedEvents' = SystemState.processedEvents

    // prompt: Engaged long enough since last prompt -> AwaitingResponse
    (cs = Engaged
     and SystemState.currentTime >= plus[SystemState.lastPrompt, PROMPT_INTERVAL]) implies {
        SystemState.currentState'  = AwaitingResponse
        SystemState.awaitingSince' = SystemState.currentTime'
        SystemState.lastPrompt' = SystemState.lastPrompt
        addStateLog[SystemState.currentTime', Engaged, AwaitingResponse]
        emitCommand[SystemState.currentTime', SteeringMotor]
        SystemState.featureDecisionLog' = SystemState.featureDecisionLog
    }

    // response timeout: AwaitingResponse longer than window -> Alarming
    (cs = AwaitingResponse
     and SystemState.currentTime >= plus[SystemState.awaitingSince, RESPONSE_WINDOW]) implies {
        SystemState.currentState'  = Alarming
        SystemState.awaitingSince' = SystemState.awaitingSince
        SystemState.lastPrompt'    = SystemState.lastPrompt
        addStateLog[SystemState.currentTime', AwaitingResponse, Alarming]
        emitCommand[SystemState.currentTime', AlarmActuator]
        SystemState.featureDecisionLog' = SystemState.featureDecisionLog
    }

    // alarm tick: keep Alarming, emit one alarm command per tick
    (cs = Alarming) implies {
        SystemState.currentState'  = SystemState.currentState
        SystemState.awaitingSince' = SystemState.awaitingSince
        SystemState.lastPrompt' = SystemState.lastPrompt
        SystemState.stateLog' = SystemState.stateLog
        emitCommand[SystemState.currentTime', AlarmActuator]
        SystemState.featureDecisionLog' = SystemState.featureDecisionLog
    }

    // otherwise: pure stutter (but clock ticks — see anyStep + stutter for full stop)
    (
        not (cs = Engaged
             and SystemState.currentTime >= plus[SystemState.lastPrompt, PROMPT_INTERVAL])
        and not (cs = AwaitingResponse
             and SystemState.currentTime >= plus[SystemState.awaitingSince, RESPONSE_WINDOW])
        and not (cs = Alarming)
    ) implies {
        SystemState.currentState' = SystemState.currentState
        SystemState.awaitingSince'  = SystemState.awaitingSince
        SystemState.lastPrompt' = SystemState.lastPrompt
        SystemState.stateLog'  = SystemState.stateLog
        SystemState.commandsLog' = SystemState.commandsLog
        SystemState.featureDecisionLog' = SystemState.featureDecisionLog
    }
}

//---ANY STEP (used by the Trace fact in next step)---

pred anyStep {
    (some e: Event | step[e]) or internalStep
}

// always take some step
fact AlwaysStep {
	init
	always anyStep
}

// once event is processed it stays processed
fact OnceProcessedStaysProcessed {
	always SystemState.processedEvents in SystemState.processedEvents'
}

// time never goes backawards
fact MonotonicTime {
	always SystemState.currentTime' >= SystemState.currentTime
}

fact Termination {
	always ((no pending and cs != Alarming) implies {
		SystemState.currentState' = SystemState.currentState
    		SystemState.currentTime' = SystemState.currentTime
    		SystemState.lastPrompt' = SystemState.lastPrompt
    		SystemState.awaitingSince' = SystemState.awaitingSince
    		SystemState.stateLog' = SystemState.stateLog
    		SystemState.commandsLog' = SystemState.commandsLog
    		SystemState.featureDecisionLog' = SystemState.featureDecisionLog
    		SystemState.processedEvents' = SystemState.processedEvents
	})
}

//---ASERTIONS---
assert OverrideAlwaysDisengages {
	always (
		some e: DriverEvent {
			e = nextEvent
			e.eventType = STEERING_FORCE
			e.force > OVERRIDE_FORCE
		} implies after (cs = Disengaged)
	)
}

check OverrideAlwaysDisengages for 4 but 8 Int, 8 steps, 4 StateLogEntry, 6 Command, 6 FeatureDecision, 4 Event

assert BreakDecisionImpliesBrakeCommand {
	always (
		all fd: SystemState.featureDecisionLog {
			( fd.feature = EmergencyBraking and fd.value = BRAKE) implies
				some c: SystemState.commandsLog {
					c.time = fd.time
					c.target = BrakingSystem
				}
			}
		)
}

check BrakeDecisionImpliesBrakeCommand for 4 but 8 Int, 8 steps, 4 StateLogEntry, 6 Command, 6 FeatureDecision, 4 Event

assert AlarmingPrecededByAwaiting {
	always (
		all s: SystemState.stateLog {
			s.current = Alarming implies s.previous = AwaitingResponse
			}
		)
}

check AlarmingPrecededByAwaiting for 4 but 8 Int, 10 steps, 6 StateLogEntry, 8 Command, 6 FeatureDecision, 4 Event

assert DisengagedHasNoLaneKeepingDecisions {
	always (
		cs = Disengaged implies no fd: (SystemState.featureDecisonLog' - SystemState.featureDecisionLog) {
			fd.feature in (LandeKeeping + CruiseControl)
		}
	)
}

check DisengagedHasNoLaneKeepingDecisions for 4 but 8 Int, 8 steps, 4 StateLogEntry, 6 Command, 6 FeatureDecision, 4 Event

//---RUNS---

pred ScenarioEngageDisengage {
	some disj e1, e2: DriverEvent {
		e1.eventType = ENGAGE
		e2.eventType = DISENGAGE
		e1.time < e2.time
	}
	no SensorEvent
	eventually cs = Engaged
	eventually (cs = Engaged and after eventually cs = Disengaged)
}

run ScenarioHappyEngageDisengage for 3 but 8 Int, 6 steps,
3 StateLogEntry, 2 Command, 2 FeatureDecision, 2 Event,
2 DriverEvent, 0 SensorEvent

pred ScenarioEmergencyBraking {
	some disj de: DriverEvent, se1: SensorEvent, se2: SensorEvent {
		Event = de + se1 +se2
		de.eventType = ENGAGE
		se1.eventType = Camera and se1.dataValue = 7
		se2.eventType = Lidar and se2.dataValue = 3
		de.time < se1.time
		se1.time < se2.time
	}
	eventually (some fd: SystemState.featureDecisionLog | fd.feature = EmergencyBraking and fd.value = BRAKE)
	eventually (some c: SystemState.commandsLog | c.target = BrakingSystem)
}

run ScenarioEmergencyBraking for 4 but 8 Int, 8 steps,
3 StateLogEntry, 5 Command, 5 FeatureDecision, 3 Event,
1 DriverEvent, 2 SensorEvent

pred ScenarioAlarmEscape {
	some disj eEng, eResp: DriverEvent {
		eEng.eventType  = ENGAGE
		eResp.eventType = STEERING_FORCE
		eResp.force     = 1
		eEng.time < eResp.time
		Event = eEng + eResp
	}
	no SensorEvent
	eventually cs = Alarming
	eventually (cs = Alarming and after eventually cs = Engaged)
}

run ScenarioAlarmEscape for 4 but 8 Int, 20 steps,
6 StateLogEntry, 8 Command, 2 FeatureDecision, 2 Event,
2 DriverEvent, 0 SensorEvent


pred ScenarioTimeoutToAlarming {
	some e: DriverEvent {
		Event = e
		e.eventType = ENGAGE
	}
	no SensorEvent
	eventually cs = Engaged
	eventually cs = AwaitingResponse
	eventually cs = Alarming
	eventually (some c: SystemState.commandsLog | c.target = AlarmActuator)
}

run ScenarioTimeoutToAlarming for 4 but 8 Int, 15 steps,
5 StateLogEntry, 6 Command, 2 FeatureDecision, 1 Event,
1 DriverEvent, 0 SensorEvent
```

# 3. Operational envelope

## 3.1. Definitions
- Lidar - A remote sensing method that uses light in the form of a pulsed laser to measure ranges to the objects.
- Actuator - A component of a machine that is responsible for moving and controlling a mechanism or system.
- Attentiveness Check - A safety procedure where the system prompts the driver to confirm they are monitoring the road by applying a small force to the steering wheel.
- Emergency Braking - A safety feature that automatically applies the brakes to prevent a collision when an obstacle is detected at a critical distance.

## 3.2. I/O operations
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

## 3.3. CLI
Copilot operates exclusively through a command-line interface. The paths to input and output files shall be configurable via command-line arguments, eliminating the need for hardcoded file paths. The command syntax shall follow the form: *copilot --input <\dir> --output <\dir>*, where both argument are mandatory. 

The CLI shall provide clear, real-time status updates to the standard output. The paths to input and output files shall be configurable via command-line arguments, eliminating the need for hardcoded file paths.

## 3.4. System attributes
### Security
The system is designed to operate strictly offline on a single machine. No network-based data transmission is permitted. 

### Maintainbility
The system shall be designed to support automated unit testing. Moreover, the source code must include comprehensive inline documentation.

### Portability
The system must be capable of running on any POSIX-compliant operating system and Windows. The software shall not require any specialized hardware (e.g., GPU acceleration) or external database engines to function.

## 3.4. Non-functional requirements
The program shall be able to run on the reference machine with at least specification of:
- CPU: 4-core, 1.60 GHz base clock
- RAM: 16 GB
- Storage: SSD
- OS: Linux 64-bit

Considering latency, the system shall process each sensor reading and driver event within 50 milliseconds.

## 3.5. Verification approach
Verification of the Copilot system shall be performed by the evaluator through black_box assessment of program outputs against provided input files. No specific testing framework or automated test suite is prescribed. The delivered software shall be submitted to an authorized evaluator responsible for all testing and verification activities.

Each functional requirement shall be considered satisfied if the contents of the output files are consistent with the behaviour specified in Section 2.1. Verification of non-functional requirements shall be performed by manual measurement on the reference machine defined in Section 2.3.

# 4. Appendices

## 4.1. Domain assumptions
- **DA-01** - It is assumed that the input CSV files are well-formed and follow the predefined schema.
- **DA-02** - The system assumes that at any given time, at least one Lidar sensor and one camera sensor provide valid readings to allow for safe autonomous operation logic.
- **DA-03** - The simulation assumes that the vehicle's physical actuators respond instantly and perfectly to the electronic commands issued by the Copilot system.
- **DA-04** - Each event in the input streams has a unique timestamp; ties are assumed not to occur.
