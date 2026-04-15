// Copilot - Alloy6 model

//---Enumerated domains---
enum State {Disengaged, Engaged, AwaitingResponse, Alarming}
enum SensorType {Lidar, Camera}
enum DriverEventType {ENGAGE, DISENGAGE, STEERING_FORCE}
// Czym różni się lane control od cruise control???
enum FeatureDecisionKind {EmergencyBraking, LaneKeeping, CruiseControl}
enum DeciosionValue {BRAKE, NO_BRAKE, ADJUST}

//---Actuators---
abstract sig Actuator{}
one sig BrakingSystem extends Actuator{}
one sig SteeringMotor extends Actuator{}
one sig SpeedActuator extends Actuator{}
one sig AlarmnActuator extends Actuator{}

//---Constratins variables---
// Modelled as fun so they have named identity
fun LIDAR_DANGER : Int {5}
fun OVERRIDE_FORCE: Int {10}
fun VALID_RESPONSE_FORCE: Int {3}
fun PROMPT_INTERVAL: Int {120}
fun RESPONSE_WINDOW: Int {5}

//---Signatures---

sig StateLog {
	timestamp: Int,
	previous: State,
	current: State
}

sig Command {
	timestamp: Int,
	target: Actuator,
	//value:
}

sig FeatureDecision {
	timestamp: Int,
	feature: FeatureDecisionKind,
	decision: DecisionValue
}

var one sig SystemState {
	var currentState: one State,
	var time: one Int,
	var lastPrompt: one Int,
	var awaitingSince: one Int,

	// output buffers
	var stateLog: set StateLog,
	var commandsLog: set Command,
	var featureDecisionLog: set FeatureDecision
}

//---Facts---
fact DecisionValuesConsistent{
	all fc: FeatureDecision {
		// emergency braking decides about Brake/No brake
		fc.feature = EmergencyBraking implies fc.decision in BRAKE + NO_BRAKE
		// lane keeping and cruise control decides about adjustion



