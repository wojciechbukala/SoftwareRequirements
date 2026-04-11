Implement a program that simulates a set reservation system for an event management company. The program must manage events, seats, and reservations through two desktop application interfaces - one for administrators and one for users - and enforces all pricing, availability, and booking rules described below. 

Each event has a unique identifier, a scheduled date, and a seating grid defined by the fixed number of rows and columns. All seats within a single event are
either numbered or non-numbered. Every seat has a category: Economy, Premium or VIP. 

The price for each seat class at each event is calculated dynamically. An Early Bird discount of 20% is applied for reservations made more than one moth before the event. A Last Minute surcharge of 30% is applied if the reservation is made less than 2 days befere the event, and more than 80% of all seats in that event is already sold. Allthough, the price of a VIP seat cannot be lower than a Premium seat, the same rule applies to Premium and Economy price dependence.

User has 15 minutes to confirm payment after locking seats, otherwise seats return to the available pool. User can hold maxium of 2 pending reservations at any given time. Each reservation is atomic, so either all requested seats are successfully reserved, or none of them are. For numbered events, all seats within a single reservation must be adjacent, to avoid single unsold places.

A confirmed reservation may be canceled at any time except 2 hours befeore the event. This way all seats from reservation retures to the pool.

The administrator interface must allow creating and configuring events, defining seating grides and categories, setting base prices, and viewing reservation summaries per event.

The user interface must allow browsing available events, selecting andreserving seats, completing or abandoning payment, and cancelling confirmed reservations.