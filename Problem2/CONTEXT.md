## Problem - SeatsReservation
An event management company operates a system for managing seat reservations for events such as concerts or conferences. Each event is scheduled for a specific date and consists of a rectangular seating layout defined by a fixed number of rows and columns. All seats within an event are either numbered or non-numbered; mixed configurations are not allowed. Seats are classified into one of three categories: Economy, Premium, or VIP. Each category has a predefined base price. The final seat price is dynamically computed at reservation time according to the following rules:
- An Early Bird discount of 20% applies if the reservation is made more than 30 days before the event date.
- A Last Minute increase of 20% applies if the reservation is made less than 48 hours before the event date and more than 80% of seats are already sold.
- At any time, the effective price of a VIP seat must not be lower than that of a Premium seat, and the price of a Premium seat must not be lower than that of an Economy seat.


For numbered events, if a user reserves N seats within a single reservation, all seats must be adjacent, meaning they are located in the same row and in consecutive columns. If this condition is not satisfied, the reservation request must be rejected. When a user selects seats, they enter a Pending state for exactly 15 minutes. If payment is not confirmed within this time, the seats are automatically released. A user may have at most two active Pending reservations at any given time. Each seat may belong to at most one active reservation (Pending or Confirmed). A reservation request is atomic: either all requested seats are successfully reserved, or none are. Users may create reservations for multiple events. Reservations may be cancelled prior to the event date, in which case the associated seats become available again.

## Input data
- desktop app for admin
- desktop app for user

## Output data
- summary view for admin
- summary view for user