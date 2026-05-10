// FleetRouter - Alloy6 model
// Time during day is modeled as Int - minutes since 8:00

open util/integer

//---ENUMS---
enum Bool { True, False }
enum ReasonCode { CAPACITY_WEIGHT, CAPACITY_VOLUME, TIME_WINDOW,
                  MAX_DRIVER_TIME, NO_VEHICLE, UNREACHABLE }

//---SIGNATURES---
sig Location {
    distances: one Distances
}

sig Depot in Location {}

sig Distances {
    distanceKm: Location -> lone Int,
    travelMin:  Location -> lone Int
}

sig Package {
    destination:  one Location,
    weightKg:     one Int,
    volumeM3:     one Int,
    twOpen:       one Int,
    twClose:      one Int,
    servicesTime: one Int,
    priority:     one Bool
}

sig Vehicle {
    maxWeightKg: one Int,
    maxVolumeM3: one Int,
    depot:       one Depot
}

abstract sig Stop {
    location:  one Location,
    arrival:   one Int,
    departure: one Int
}

sig DepotStart extends Stop {}

sig DepotEnd extends Stop {}

sig DeliveryStop extends Stop {
    position: one Int,
    delivers: one Package
}

sig Route {
    vehicle: one Vehicle,
    stops:   set DeliveryStop,
    start:   one DepotStart,
    end:     one DepotEnd
}

one sig Plan {
    routes:        set Route,
    undeliverable: Package -> lone ReasonCode
}

//---FACTS---
fact stopsBelongToOneRoute {
    all s: DepotStart   | one r: Route | r.start = s
    all s: DepotEnd     | one r: Route | r.end   = s
    all s: DeliveryStop | one r: Route | s in r.stops
}

fact routeStartsAndEndsAtSameDepot {
    all r: Route | {
        r.start.location = r.vehicle.depot
        r.end.location   = r.vehicle.depot
    }
}

fact oneRoutePerVehicle {
    all v: Vehicle | lone r: Plan.routes | r.vehicle = v
}

fact allRoutesInPlan {
    Route = Plan.routes
}

fact sequenceOfStops {
    all r: Route | {
        all disj s1, s2: r.stops | s1.position != s2.position
        all s: r.stops | s.position >= 1 and s.position <= #r.stops
    }
}

fact packageDeliveredAtMostOnce {
    all disj s1, s2: DeliveryStop | s1.delivers != s2.delivers
}

fact stopLocationMatchesPackageDestination {
    all s: DeliveryStop | s.location = s.delivers.destination
}

fact nonNegatives {
    all l1, l2: Location | {
        some l1.distances.distanceKm[l2] implies l1.distances.distanceKm[l2] >= 0
        some l1.distances.travelMin[l2]  implies l1.distances.travelMin[l2]  >= 0
    }
    all p: Package | {
        p.weightKg     >= 0
        p.volumeM3     >= 0
        p.twOpen       >= 0
        p.twClose      >= 0
        p.servicesTime >= 0
        p.twClose > p.twOpen
    }
    all v: Vehicle | {
        v.maxWeightKg >= 0
        v.maxVolumeM3 >= 0
    }
    all s: Stop | {
        s.arrival   >= 0
        s.departure >= s.arrival
    }
}

fact selfDistanceZero {
    all l: Location | {
        l.distances.distanceKm[l] = 0
        l.distances.travelMin[l]  = 0
    }
}

fact depotStartAtZero {
    all s: DepotStart | s.arrival = 0 and s.departure = 0
}

fact depotEndNoService {
    all s: DepotEnd | s.departure = s.arrival
}

fact departureTiming {
    all s: DeliveryStop | {
        s.arrival.gte[s.delivers.twOpen] implies
            s.departure = s.arrival.plus[s.delivers.servicesTime]
        s.arrival.lt[s.delivers.twOpen] implies
            s.departure = s.delivers.twOpen.plus[s.delivers.servicesTime]
    }
}

fact arrivalTimeChain {
    all r: Route | {
        all s: r.stops | s.position = 1 implies
            s.arrival = r.start.departure.plus[
                r.start.location.distances.travelMin[s.location]]

        all s: r.stops | s.position > 1 implies
            some prev: r.stops |
                prev.position = s.position.minus[1] and
                s.arrival = prev.departure.plus[
                    prev.location.distances.travelMin[s.location]]

        no r.stops implies
            r.end.arrival = r.start.departure.plus[
                r.start.location.distances.travelMin[r.end.location]]

        some r.stops implies
            some last: r.stops |
                last.position = #r.stops and
                r.end.arrival = last.departure.plus[
                    last.location.distances.travelMin[r.end.location]]
    }
}

//---PREDICATES---

pred packageIsReachable[p: Package, v: Vehicle] {
    some v.depot.distances.travelMin[p.destination]
    some p.destination.distances.travelMin[v.depot]
}

pred weightFits[v: Vehicle, P: set Package] {
    (sum p: P | p.weightKg) <= v.maxWeightKg
}

pred volumeFits[v: Vehicle, P: set Package] {
    (sum p: P | p.volumeM3) <= v.maxVolumeM3
}

pred timeWindowFits[s: DeliveryStop] {
    s.arrival <= s.delivers.twClose
}

pred driverTimeFits[r: Route] {
    r.end.arrival <= 480
}

pred routeReachable[r: Route] {
    no r.stops implies some r.start.location.distances.travelMin[r.end.location]
    some r.stops implies {
        all s: r.stops | s.position = 1 implies
            some r.start.location.distances.travelMin[s.location]
        all s: r.stops | s.position > 1 implies
            some prev: r.stops | prev.position = s.position.minus[1] and
            some prev.location.distances.travelMin[s.location]
        all last: r.stops | last.position = #r.stops implies
            some last.location.distances.travelMin[r.end.location]
    }
}

pred routeFits[r: Route] {
    weightFits[r.vehicle, r.stops.delivers]
    volumeFits[r.vehicle, r.stops.delivers]
    all s: r.stops | timeWindowFits[s]
    driverTimeFits[r]
    routeReachable[r]
}

pred feasiblePlan {
    all r: Plan.routes | routeFits[r]
}

pred allPackagesProcessed {
    all p: Package |
        (one s: DeliveryStop | s.delivers = p) or
        (some Plan.undeliverable[p])
}

pred noDoubleStatus {
    all p: Package | (some s: DeliveryStop | s.delivers = p) implies no Plan.undeliverable[p]
}

fun earliestArrival[p: Package, v: Vehicle]: Int {
    v.depot.distances.travelMin[p.destination]
}

pred deservesCapacityWeight[p: Package] {
    all v: Vehicle | p.weightKg > v.maxWeightKg
}

pred deservesCapacityVolume[p: Package] {
    all v: Vehicle | p.volumeM3 > v.maxVolumeM3
}

pred deservesTimeWindow[p: Package] {
    all v: Vehicle |
        some earliestArrival[p, v] implies earliestArrival[p, v] > p.twClose
}

pred deservesMaxDriverTime[p: Package] {
    all v: Vehicle | {
        let outbound = v.depot.distances.travelMin[p.destination],
            inbound  = p.destination.distances.travelMin[v.depot] |
            (some outbound and some inbound) implies
                outbound.plus[p.servicesTime].plus[inbound] > 480
    }
}

pred deservesUnreachable[p: Package] {
    all v: Vehicle | {
        no v.depot.distances.travelMin[p.destination]
        or
        no p.destination.distances.travelMin[v.depot]
    }
}

pred deservesNoVehicle[p: Package] {
    no Vehicle
}

pred reasonPossible[p: Package, c: ReasonCode] {
    c = CAPACITY_WEIGHT implies deservesCapacityWeight[p]
    c = CAPACITY_VOLUME implies deservesCapacityVolume[p]
    c = TIME_WINDOW     implies deservesTimeWindow[p]
    c = MAX_DRIVER_TIME implies deservesMaxDriverTime[p]
    c = UNREACHABLE     implies deservesUnreachable[p]
    c = NO_VEHICLE      implies deservesNoVehicle[p]
}

pred allUndeliverableReasonsValid {
    all p: Package, c: ReasonCode |
        c in Plan.undeliverable[p] implies reasonPossible[p, c]
}

pred allDeservingAreUndeliverable {
    all p: Package | {
        (deservesCapacityWeight[p]
         or deservesCapacityVolume[p]
         or deservesTimeWindow[p]
         or deservesMaxDriverTime[p]
         or deservesUnreachable[p]
         or deservesNoVehicle[p])
        implies some Plan.undeliverable[p]
    }
}


pred validPlan {
    feasiblePlan
    allPackagesProcessed
    noDoubleStatus
    allUndeliverableReasonsValid
    allDeservingAreUndeliverable
}

//---ASSERTIONS---
assert deliveredPackagesAreTrulyDeliverable {
    validPlan implies
        all s: DeliveryStop | {
            not deservesCapacityWeight[s.delivers]
            not deservesCapacityVolume[s.delivers]
            not deservesTimeWindow[s.delivers]
            not deservesMaxDriverTime[s.delivers]
            not deservesUnreachable[s.delivers]
            not deservesNoVehicle[s.delivers]
        }
}
check deliveredPackagesAreTrulyDeliverable
    for 4 but 10 Int, exactly 2 Vehicle, exactly 3 Package, exactly 3 Location


assert routeConstraintsAlwaysHold {
    validPlan implies
        all r: Plan.routes | {
            (sum p: r.stops.delivers | p.weightKg) <= r.vehicle.maxWeightKg
            (sum p: r.stops.delivers | p.volumeM3) <= r.vehicle.maxVolumeM3
            r.end.arrival <= 480
        }
}

check routeConstraintsAlwaysHold
    for 4 but 10 Int, exactly 2 Vehicle, exactly 3 Package, exactly 3 Location

assert everyPackageHasExactlyOneStatus {
    validPlan implies
        all p: Package | {
            let delivered = (some s: DeliveryStop | s.delivers = p),
                undeliv   = (some Plan.undeliverable[p]) |
                (delivered and not undeliv) or (undeliv and not delivered)
        }
}

check everyPackageHasExactlyOneStatus
    for 4 but 10 Int, exactly 2 Vehicle, exactly 3 Package, exactly 3 Location

//---RUNS ---

run findValidPlan {
    validPlan
    some Package
    some Vehicle
    some Plan.routes
} for 4 but 10 Int, exactly 2 Vehicle, exactly 3 Package, exactly 3 Location

run findValidPlanMinimal {
    validPlan
    some Package
    some Vehicle
} for 3 but 8 Int, exactly 1 Vehicle, exactly 2 Package, exactly 2 Location

run findPlanWithDeliveries {
    validPlan
    some DeliveryStop
} for 4 but 10 Int, exactly 2 Vehicle, exactly 3 Package, exactly 3 Location

run findPlanWithUndeliverable {
    validPlan
    some Plan.undeliverable
} for 4 but 10 Int, exactly 1 Vehicle, exactly 2 Package, exactly 2 Location
