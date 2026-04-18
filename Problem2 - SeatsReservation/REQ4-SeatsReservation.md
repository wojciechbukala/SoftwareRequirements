# 1. Purpose
SeatsReservation is a specialized management tool designed for event companies to automate seat booking for various events. The primary goals of the program are listed below:

- **G-01** - The system shall manage a rectangular seating grid for various events.
- **G-02** - The system should handle both numbered and non-numbered seating configurations.
- **G-03** - The system shall accurately calculate dynamic ticket prices based on timing and seat category.
- **G-04** - SeatsReservation system must ensure the integrity of the reservation process.

The SeatsReservation program is focused on the logic of event management and reservation handling. It provides an interface for both administrators and users. 

# 2. Alloy model
```
// SeatsReservation - Alloy6 model

//---ENUMS---
enum SeatCategory {VIP, Premium, Economy}
enum ReservationStatus {Pending, Confirmed, Cancelled, Expired}
enum PriceModifier {EarlyBird, Base, LastMinute}
enum CommandKind {ReleaseSeats, NotifyConfirmed, NotifyExpired, NotifyCancelled}

//---SIGNATURES---
abstract sig User {}

sig Customer extends User {}
sig Administrator extends User {}

sig Seat {
	event: one Event,
	category: one SeatCategory,
	row: lone Int,
	col: lone Int
}

sig Price {
	category: one SeatCategory,
	modifier: one PriceModifier,
	effectivePrice: one Int,
	forEvent: one Event
}

abstract sig Event {
	date: one Int,
	createdBy: one Administrator,
	seats: some Seat,
	basePrice: SeatCategory -> one Int
}

sig NumberedEvent extends Event {
	rightNeighbor : Seat -> lone Seat
}

sig NonNumberedEvent extends Event {}

sig Reservation {
	customer: one Customer,
	event: one Event,
	seats: some Seat,
	createdAt: one Int,
	price: one Price
}

sig ReservationLog {
	reservation    : one Reservation,
	previousStatus : one ReservationStatus,
	currentStatus  : one ReservationStatus,
	timestamp      : one Int
}

sig Command {
	kind: one CommandKind,
	reservation: one Reservation,
	issuedAt: one Int
}

fun MAX_PENDING_PER_USER : Int {2}

one sig SystemState {
	var clock : one Int,
	var pending   : set Reservation,
	var confirmed : set Reservation,
	var cancelled : set Reservation,
	var expired   : set Reservation,
	var earlyBirdEvents  : set Event,
	var lastMinuteEvents : set Event,
	var highOccupancy    : set Event,
	var lockExpired   : set Reservation,
	var cancelAllowed : set Reservation,
	var prices : set Price,
	var reservationLog : set ReservationLog,
	var commands       : set Command
}


//---FACTS---

fact PriceNonNegative {
	all p : Price | p.effectivePrice >= 0
}

fact NonNegativeDomains {
	all e : Event | e.date >= 0
	all s : Seat | (one s.row implies s.row >= 0) and (one s.col implies s.col >= 0)
	all r : Reservation | r.createdAt >= 0
	all l : ReservationLog | l.timestamp >= 0
	all c : Command | c.issuedAt >= 0
	all e : Event, k : SeatCategory | e.basePrice[k] >= 0
}

fact SeatEventConsistency {
	all s: Seat | s in s.event.seats
	all e: Event, s: e.seats | s.event = e
}

fact SeatGeometryWellTyped {
	all s : Seat |
		(s.event in NumberedEvent) iff (one s.row and one s.col)
}

fact NumberedSeatsUnique {
	all e : NumberedEvent, disj s1, s2 : e.seats |
		not (s1.row = s2.row and s1.col = s2.col)
}

fact RightNeighborScope {
	all e : NumberedEvent | {
		e.rightNeighbor in e.seats -> e.seats
		all s : e.seats, t : s.(e.rightNeighbor) | t.row = s.row
		all s : e.seats | lone (e.rightNeighbor).s
		no s : e.seats | s in s.^(e.rightNeighbor)
	}
}

fact ReservationConsistency {
	all r : Reservation | r.seats in r.event.seats
	all r : Reservation | r.price.forEvent = r.event
	all disj r1, r2 : Reservation | r1.price != r2.price
	all p : Price | some r : Reservation | r.price = p
}

fact NoOrphans {
	all l : ReservationLog | eventually l in SystemState.reservationLog
	all c : Command | eventually c in SystemState.commands
}

fact NumberedReservationAdjacency {
	all r : Reservation | r.event in NumberedEvent implies {
		let rn = r.event.rightNeighbor |
			some head : r.seats | {
				no (rn.head & r.seats)
				r.seats in head.*rn
				all s : r.seats - head | some (rn.s & r.seats)
			}
	}
}

fact BasePriceHierarchy {
	all e : Event |
		e.basePrice[VIP] > e.basePrice[Premium]
		and e.basePrice[Premium] > e.basePrice[Economy]
}

fact EffectivePriceCalculation {
	all p : Price | {
		let base = p.forEvent.basePrice[p.category] | {
			p.modifier = EarlyBird implies p.effectivePrice < base
			p.modifier = Base implies p.effectivePrice = base
			p.modifier = LastMinute implies p.effectivePrice > base
		}
	}
}

fact EffectivePriceHierarchy {
	all e : Event, pV, pP, pE : Price | {
		pV.forEvent = e and pV.category = VIP
		and pP.forEvent = e and pP.category = Premium
		and pE.forEvent = e and pE.category = Economy
	} implies {
		pV.effectivePrice >= pP.effectivePrice
		pP.effectivePrice >= pE.effectivePrice
	}
}

fact SetsDisjoint {
	always {
		no (SystemState.pending & SystemState.confirmed)
		no (SystemState.pending & SystemState.cancelled)
		no (SystemState.pending & SystemState.expired)
		no (SystemState.confirmed & SystemState.cancelled)
		no (SystemState.confirmed & SystemState.expired)
		no (SystemState.cancelled & SystemState.expired)
	}
}

fact LockExpiredSubsetOfPending {
	always SystemState.lockExpired in SystemState.pending
}

fact CancelAllowedSubsetOfConfirmed {
	always SystemState.cancelAllowed in SystemState.confirmed
}

fact ReservationLogConsistentWithStatus {
	always all r : Reservation | {
		r in SystemState.pending implies some l : SystemState.reservationLog |
			l.reservation = r and l.currentStatus = Pending
		r in SystemState.confirmed implies some l : SystemState.reservationLog |
			l.reservation = r and l.currentStatus = Confirmed
		r in SystemState.cancelled implies some l : SystemState.reservationLog |
			l.reservation = r and l.currentStatus = Cancelled
		r in SystemState.expired implies some l : SystemState.reservationLog |
			l.reservation = r and l.currentStatus = Expired
	}
}

fact HighOccupancyRelation {
	always all e : Event |
		(e in SystemState.highOccupancy) iff
		(mul[5, #confirmedSeatsOf[e]] > mul[4, #e.seats])
}

fact RealReservationTransition {
	all l : ReservationLog |
		l.previousStatus = l.currentStatus implies {
			l.previousStatus = Pending
			lone { l2 : ReservationLog |
				l2.reservation = l.reservation
				and l2.previousStatus = l2.currentStatus }
		}
}

fact PricesBufferMirror {
	always SystemState.prices =
		(SystemState.pending + SystemState.confirmed
		 + SystemState.cancelled + SystemState.expired).price
}


//---FUNCTIONS---

fun activeReservations : set Reservation {
	SystemState.pending + SystemState.confirmed
}

fun terminalReservations : set Reservation {
	SystemState.cancelled + SystemState.expired
}

fun occupiedSeats : set Seat {
	activeReservations.seats
}

fun confirmedSeatsOf [e : Event] : set Seat {
	(SystemState.confirmed & { r : Reservation | r.event = e }).seats
}

fun pendingCountOf [c : Customer] : Int {
	# (SystemState.pending & { r : Reservation | r.customer = c })
}

fun modifierFor [e : Event] : PriceModifier {
	(e in SystemState.earlyBirdEvents)
		implies EarlyBird
	else (e in SystemState.lastMinuteEvents and e in SystemState.highOccupancy)
		implies LastMinute
	else Base
}


//---PREDICATES---

pred init {
	SystemState.clock = 0
	no SystemState.pending
	no SystemState.confirmed
	no SystemState.cancelled
	no SystemState.expired
	no SystemState.earlyBirdEvents
	no SystemState.lastMinuteEvents
	no SystemState.highOccupancy
	no SystemState.lockExpired
	no SystemState.cancelAllowed
	no SystemState.prices
	no SystemState.reservationLog
	no SystemState.commands
}

pred tickClock {
	SystemState.clock' = plus[SystemState.clock, 1]
}

pred stepConfirmPayment[r : Reservation] {
	r in SystemState.pending
	r not in SystemState.lockExpired

	tickClock

	SystemState.pending' = SystemState.pending - r
	SystemState.confirmed' = SystemState.confirmed + r
	SystemState.cancelled' = SystemState.cancelled
	SystemState.expired' = SystemState.expired

	some log : ReservationLog |
		log not in SystemState.reservationLog
		and log.reservation = r
		and log.previousStatus = Pending
		and log.currentStatus = Confirmed
		and log.timestamp = SystemState.clock
		and SystemState.reservationLog' = SystemState.reservationLog + log

	some cmd : Command |
		cmd not in SystemState.commands
		and cmd.kind = NotifyConfirmed
		and cmd.reservation = r
		and cmd.issuedAt = SystemState.clock
		and SystemState.commands' = SystemState.commands + cmd
}

pred stepCancelReservation [c : Customer, r : Reservation] {
	r in SystemState.confirmed
	r in SystemState.cancelAllowed
	r.customer = c

	tickClock

	SystemState.pending' = SystemState.pending
	SystemState.confirmed' = SystemState.confirmed - r
	SystemState.cancelled' = SystemState.cancelled + r
	SystemState.expired' = SystemState.expired

	some log : ReservationLog |
		log not in SystemState.reservationLog
		and log.reservation = r
		and log.previousStatus = Confirmed
		and log.currentStatus = Cancelled
		and log.timestamp = SystemState.clock
		and SystemState.reservationLog' = SystemState.reservationLog + log

	some cmd1, cmd2 : Command | {
		cmd1 != cmd2
		cmd1 not in SystemState.commands
		cmd2 not in SystemState.commands
		cmd1.kind = NotifyCancelled
		cmd1.reservation = r
		cmd1.issuedAt = SystemState.clock
		cmd2.kind = ReleaseSeats
		cmd2.reservation = r
		cmd2.issuedAt = SystemState.clock
		SystemState.commands' = SystemState.commands + cmd1 + cmd2
	}
}

pred internalStep {
	some SystemState.lockExpired
	some r : SystemState.lockExpired | {
		tickClock

		SystemState.pending' = SystemState.pending - r
		SystemState.confirmed' = SystemState.confirmed
		SystemState.cancelled' = SystemState.cancelled
		SystemState.expired' = SystemState.expired + r

		some log : ReservationLog |
			log not in SystemState.reservationLog
			and log.reservation = r
			and log.previousStatus = Pending
			and log.currentStatus = Expired
			and log.timestamp = SystemState.clock
			and SystemState.reservationLog' = SystemState.reservationLog + log

		some cmd1, cmd2 : Command | {
			cmd1 != cmd2
			cmd1 not in SystemState.commands
			cmd2 not in SystemState.commands
			cmd1.kind = NotifyExpired
			cmd1.reservation = r
			cmd1.issuedAt = SystemState.clock
			cmd2.kind = ReleaseSeats
			cmd2.reservation = r
			cmd2.issuedAt = SystemState.clock
			SystemState.commands' = SystemState.commands + cmd1 + cmd2
		}
	}
}

pred isAdjacentChain [e : NumberedEvent, seats : set Seat] {
	let rn = e.rightNeighbor |
		some head : seats | {
			no (rn.head & seats)
			seats in head.*rn
			all s : seats - head | some (rn.s & seats)
		}
}

pred stepLockSeats [c : Customer, e : Event, chosen : set Seat] {
	chosen in e.seats
	no chosen & occupiedSeats
	pendingCountOf[c] < MAX_PENDING_PER_USER
	e in NumberedEvent implies isAdjacentChain[e, chosen]
	e in NonNumberedEvent implies (all disj s1, s2 : chosen | s1.category = s2.category)
	not (e in SystemState.earlyBirdEvents and e in SystemState.lastMinuteEvents)

	tickClock

	some r : Reservation | {
		r not in activeReservations
		r not in terminalReservations

		r.customer = c
		r.event = e
		r.seats = chosen
		r.createdAt = SystemState.clock

		r.price.modifier = modifierFor[e]
		r.price.category in chosen.category

		SystemState.pending' = SystemState.pending + r
		SystemState.confirmed' = SystemState.confirmed
		SystemState.cancelled' = SystemState.cancelled
		SystemState.expired' = SystemState.expired

		some log : ReservationLog |
			log not in SystemState.reservationLog
			and log.reservation = r
			and log.previousStatus = Pending
			and log.currentStatus = Pending
			and log.timestamp = SystemState.clock
			and SystemState.reservationLog' = SystemState.reservationLog + log

		SystemState.commands' = SystemState.commands
	}
}

pred keepAll {
	SystemState.clock' = SystemState.clock
	SystemState.pending' = SystemState.pending
	SystemState.confirmed' = SystemState.confirmed
	SystemState.cancelled' = SystemState.cancelled
	SystemState.expired' = SystemState.expired
	SystemState.earlyBirdEvents' = SystemState.earlyBirdEvents
	SystemState.lastMinuteEvents' = SystemState.lastMinuteEvents
	SystemState.highOccupancy' = SystemState.highOccupancy
	SystemState.lockExpired' = SystemState.lockExpired
	SystemState.cancelAllowed' = SystemState.cancelAllowed
	SystemState.prices' = SystemState.prices
	SystemState.reservationLog' = SystemState.reservationLog
	SystemState.commands' = SystemState.commands
}

pred quiescent {
	no SystemState.pending
	no SystemState.lockExpired
	no SystemState.cancelAllowed
	no r : Reservation | r not in activeReservations and r not in terminalReservations
}

pred anyStep {
	(some c : Customer, e : Event, chosen : set Seat | stepLockSeats[c, e, chosen])
	or (some r : Reservation | stepConfirmPayment[r])
	or (some c : Customer, r : Reservation | stepCancelReservation[c, r])
	or internalStep
	or keepAll
}


//---TRACE---

fact Trace {
	init
	always anyStep
}

fact MonotonicBehaviours {
	always SystemState.clock' >= SystemState.clock
	always SystemState.reservationLog in SystemState.reservationLog'
	always SystemState.commands in SystemState.commands'
	always SystemState.cancelled in SystemState.cancelled'
	always SystemState.expired in SystemState.expired'
}

fact Termination {
	always (quiescent implies keepAll)
}


//---ASSERTIONS---

assert SeatNeverDoubleBooked {
	always all s : Seat |
		lone {r : activeReservations | s in r.seats}
}

check SeatNeverDoubleBooked
	for 2 Event, 6 Seat, 3 Reservation, 2 Customer, 1 Administrator,
		6 ReservationLog, 6 Command, 3 Price, 8 Int, 12 steps

assert MaxPendingPerUserRespected {
	always all c : Customer |
		#{ r : SystemState.pending | r.customer = c } <= MAX_PENDING_PER_USER
}

check MaxPendingPerUserRespected
	for 2 Event, 6 Seat, 3 Reservation, 2 Customer, 1 Administrator,
		6 ReservationLog, 6 Command, 3 Price, 8 Int, 12 steps

assert ConfirmOnlyWhilePending {
	always all r : Reservation |
		(r not in SystemState.confirmed and r in SystemState.confirmed')
			implies r in SystemState.pending
}

check ConfirmOnlyWhilePending
	for 2 Event, 6 Seat, 3 Reservation, 2 Customer, 1 Administrator,
		6 ReservationLog, 6 Command, 3 Price, 8 Int, 12 steps

assert ExpiryAlwaysReleasesSeats {
	always all r : Reservation |
		(r not in SystemState.expired and r in SystemState.expired')
			implies (after no s : r.seats | s in occupiedSeats)
}

check ExpiryAlwaysReleasesSeats
	for 2 Event, 6 Seat, 3 Reservation, 2 Customer, 1 Administrator,
		6 ReservationLog, 6 Command, 3 Price, 8 Int, 12 steps


//---RUNS---

pred numberedEarlyBird {
	some disj s1, s2, s3 : Seat, c : Customer, e : NumberedEvent, r : Reservation | {
		e.seats = s1 + s2 + s3
		s2 in s1.(e.rightNeighbor)

		eventually e in SystemState.earlyBirdEvents
		r.customer = c
		r.event = e
		r.seats = s1 + s2
		r.price.modifier = EarlyBird

		eventually r in SystemState.pending
		eventually r in SystemState.confirmed
	}
}

run numberedEarlyBird
	for 1 Event, 3 Seat, 1 Reservation, 1 Customer, 1 Administrator,
		2 ReservationLog, 1 Command, 1 Price, 8 Int, 6 steps

pred nonNumberedBasePrice {
	some disj s1, s2, s3 : Seat, c : Customer, e : NonNumberedEvent, r : Reservation | {
		e.seats = s1 + s2 + s3
		s1.category = Economy
		s2.category = Economy

		eventually (e not in SystemState.earlyBirdEvents
			and e not in SystemState.lastMinuteEvents)

		r.customer = c
		r.event = e
		r.seats = s1 + s2
		r.price.modifier = Base

		eventually r in SystemState.pending
		eventually r in SystemState.confirmed
	}
}

run nonNumberedBasePrice
	for 1 Event, 3 Seat, 1 Reservation, 1 Customer, 1 Administrator,
		2 ReservationLog, 1 Command, 1 Price, 8 Int, 6 steps

pred fullLifecycle {
	some s : Seat, c : Customer, e : Event, r : Reservation | {
		s in e.seats
		r.customer = c
		r.event = e
		s in r.seats

		eventually r in SystemState.pending
		eventually r in SystemState.confirmed
		eventually r in SystemState.cancelled

		eventually (r in SystemState.pending
			and after eventually (r in SystemState.confirmed
				and after eventually r in SystemState.cancelled))

		eventually (r in SystemState.confirmed and r in SystemState.cancelAllowed)
	}
}

run fullLifecycle
	for 1 Event, 3 Seat, 1 Reservation, 1 Customer, 1 Administrator,
		3 ReservationLog, 3 Command, 1 Price, 8 Int, 8 stepssteps
```

# 3. Operational envelope

# 3.1. I/O operations
The SeatsReservation system is logically divided into three user interfaces, each accessible through the same single entry point:

1. **Login / Register panel** - the single entry point for all users. It allows authentication and account creation, and after successful login routes the user to the appropriate interface based on their role.
2. **User interface** - accessible after login as a Customer. It consists of the following views:
   - *Events* - a list of upcoming events; selecting an event initiates the "Reserve seats" use case (UC-01).
   - *Bookings* - a history of the user's reservations with their current status, used for tracking payments and performing cancellations.
   - *Profile* - personal account details.
   - *Settings* - application settings.
3. **Administrator interface** - accessible after login as an Administrator. It consists of the following views:
   - *Dashboard* - real-time summary of occupancy and revenue across managed events.
   - *Events* - a table of all managed events with their configuration options.
   - *Event Creator* - a form-based tool for event metadata entry, interactive grid or pool configuration, and base price setup; initiates the "Add event" use case (UC-03).


- **Platform** - the system shall be delivered as a web application compatible with modern web browsers (see 3.8 Portability).
- **Visual style** - the key views of the system (Login panel, User interface, and Administrator interface) are provided as mockups in the *UI_Mockups* folder (*LoginRegister.png*, *User.png*, *Admin.png*). All views not explicitly covered by the mockups shall follow the same graphical style — colour palette, typography, proportions, component shapes, and interaction patterns — as established by the mockups.
- **Single entry point** - authentication for both roles is handled by the same Login / Register panel; no separate admin login URL or credential store is permitted.


# 3.2. Non-functional requirements
- The program shall process reservation requests in under 200ms.
- It must maintain strict data integrity and prevent race conditions for at least 50 concurrent users per event.
- The system shall support the management of 100 active events with seating grids up to 250,000 units (500x500).
- The automated 15-minute expiration logic for Pending reservations must operate with a maximum drift of 5 seconds.

# 3.3. Verification approach

# 4. Appendices

## 4.1. Domain assumptions
- **DA-01** - The system clock on the host machine is considered the source of truth for all time-based calculations.
- **DA-02** - A month for the discounts is defined as exactly 30 calendar days.
- **DA-03** - Payment confirmation is provided by an external signal or simulated user action.